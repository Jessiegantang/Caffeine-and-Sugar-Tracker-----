import datetime
import uuid

from agents.companion_agent import generate_companion_response as generate_local_companion_response
from agents.intake_parser import parse_intake_message
from db.database import ChatLog, DrinkLog, SleepRecord
from services.dify_companion_service import DifyCompanionError, dify_available, generate_dify_turn
from services.memory_service import apply_memory_updates, extract_memory_updates
from services.trace_service import save_agent_trace


INTAKE_FOLLOW_UP_MARKERS = (
    "甜度是",
    "大概多少 ml",
    "饮品叫什么名字",
    "还需要一点信息",
)


def serialize_chat_log(log: ChatLog) -> dict:
    return {"role": log.role, "content": log.content}


def get_chat_history(db, date: str) -> dict:
    logs = db.query(ChatLog).filter(ChatLog.date == date).order_by(ChatLog.timestamp).all()
    return {"status": "success", "history": [serialize_chat_log(log) for log in logs]}


def build_companion_context(db, date: str) -> dict:
    today_records_db = db.query(DrinkLog).filter(DrinkLog.date == date, DrinkLog.status == 'active').all()
    today_caffeine = sum(r.caffeine or 0 for r in today_records_db)
    today_sugar = sum(r.sugarContent or 0 for r in today_records_db)

    sleep_record = db.query(SleepRecord).filter(SleepRecord.date == date).first()
    sleep_hours = sleep_record.sleep_hours if sleep_record else "未知"

    # 获取偏好记忆
    from db.database import UserPreference
    prefs_db = db.query(UserPreference).all()
    preferences = {p.key: p.value for p in prefs_db}

    return {
        "today_caffeine_mg": today_caffeine,
        "today_sugar_g": today_sugar,
        "last_night_sleep_hours": sleep_hours,
        "user_preferences": preferences
    }


def complete_pending_intake(history: list[dict], message: str, parsed_intake: dict) -> dict:
    if parsed_intake.get("intent") == "log_drink" or not history:
        return parsed_intake

    latest_message = history[-1]
    if latest_message.get("role") != "assistant":
        return parsed_intake
    if not any(marker in latest_message.get("content", "") for marker in INTAKE_FOLLOW_UP_MARKERS):
        return parsed_intake

    user_messages = [item["content"] for item in history[-8:] if item.get("role") == "user"]
    for index in range(len(user_messages) - 1, -1, -1):
        pending = parse_intake_message(user_messages[index])
        if pending.get("intent") != "log_drink":
            continue
        if not pending.get("missing_fields"):
            break

        combined_message = "。补充：".join(user_messages[index:] + [message])
        completed = parse_intake_message(combined_message)
        if completed.get("intent") != "log_drink":
            break
        if len(completed.get("missing_fields") or []) < len(pending.get("missing_fields") or []):
            return completed
        break

    return parsed_intake


def send_chat_message(db, input_data) -> dict:
    # 1. Save user message
    now_str = datetime.datetime.now().isoformat()
    user_log = ChatLog(date=input_data.date, role="user", content=input_data.message, timestamp=now_str)
    db.add(user_log)
    db.commit()

    # 2. Get history
    logs = db.query(ChatLog).filter(ChatLog.date == input_data.date).order_by(ChatLog.timestamp).all()
    history = [serialize_chat_log(log) for log in logs[:-1]] # exclude current msg

    # 3. Get context
    context = build_companion_context(db, input_data.date)

    # 4. Let Dify orchestrate the whole chat first. Restore the complete local
    # route when Dify is unavailable or returns an invalid structured form.
    dify_turn = None
    fallback_reason = None
    if dify_available():
        try:
            dify_turn = generate_dify_turn(input_data.message, history, context)
        except DifyCompanionError as exc:
            fallback_reason = exc.code

    if dify_turn is not None:
        parsed_intake = dify_turn.get("parsed_intake")
        ai_response_text = dify_turn["text"]
        if parsed_intake:
            memory_updates = extract_memory_updates(input_data.message, "log_drink", parsed_intake, db)
        else:
            memory_updates = extract_memory_updates(input_data.message, "ask_advice", None, db)
        provider = "dify"
    else:
        parsed_intake = parse_intake_message(input_data.message)
        parsed_intake = complete_pending_intake(history, input_data.message, parsed_intake)
        provider = "local"

    if dify_turn is None and parsed_intake.get("intent") == "log_drink":
        memory_updates = extract_memory_updates(input_data.message, "log_drink", parsed_intake, db)
        if parsed_intake.get("missing_fields"):
            ai_response_text = parsed_intake.get("follow_up") or "我还需要一点信息才能帮你记录这杯饮品。"
        else:
            ai_response_text = (
                f"我识别到这是一杯 {parsed_intake.get('brand') or ''} "
                f"{parsed_intake.get('name')}，{parsed_intake.get('volume')}ml，"
                f"甜度 {parsed_intake.get('sugar')}。我已经整理成结构化饮品对象。"
            )
    elif dify_turn is None:
        parsed_intake = None
        memory_updates = extract_memory_updates(input_data.message, "ask_advice", None, db)
        ai_response_text = generate_local_companion_response(input_data.message, history, context)
    memory_updates = apply_memory_updates(db, memory_updates)

    # 5. Save AI response
    now_str2 = datetime.datetime.now().isoformat()
    ai_log = ChatLog(date=input_data.date, role="assistant", content=ai_response_text, timestamp=now_str2)
    db.add(ai_log)
    db.commit()

    trace_state = {
        "trace_id": f"trace_{uuid.uuid4().hex[:12]}",
        "user_message": input_data.message,
        "intent": parsed_intake.get("intent") if parsed_intake else "ask_advice",
        "agents_called": ["dify_assistant"] if provider == "dify" else (
            ["intake_parser"] if parsed_intake else ["intake_parser", "companion_agent"]
        ),
        "tools_used": ["DIFY_CHATFLOW"] if provider == "dify" else (
            ["LOCAL_INTAKE_PARSER"] if parsed_intake else ["LOCAL_COMPANION"]
        ),
        "retrieved_docs": [],
        "model_name": "dify" if provider == "dify" else ("local" if parsed_intake else None),
        "latency_ms": 0.0,
        "memory_updates": memory_updates,
        "final_action": "ask_follow_up" if parsed_intake and parsed_intake.get("missing_fields") else ("fill_log_form" if parsed_intake else "answer_advice"),
        "error": fallback_reason,
    }
    save_agent_trace(db, trace_state)

    return {"status": "success", "response": ai_response_text, "parsed_intake": parsed_intake, "trace_id": trace_state["trace_id"]}
