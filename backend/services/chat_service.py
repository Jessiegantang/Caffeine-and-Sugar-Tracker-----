import datetime
import uuid

from agents.intake_parser import parse_intake_with_fallback
from agents.orchestrator import run_agent_orchestrator
from db.database import ChatLog, DrinkLog, SleepRecord
from services.dify_companion_service import (
    DifyCompanionError,
    dify_available,
    generate_dify_turn,
    stream_dify_companion_turn,
)
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
    today_records = db.query(DrinkLog).filter(
        DrinkLog.date == date,
        DrinkLog.status == "active",
    ).all()
    today_caffeine = sum(record.caffeine or 0 for record in today_records)
    today_sugar = sum(record.sugarContent or 0 for record in today_records)

    sleep_record = db.query(SleepRecord).filter(SleepRecord.date == date).first()
    sleep_hours = sleep_record.sleep_hours if sleep_record else "未知"

    from db.database import UserPreference

    preferences = {preference.key: preference.value for preference in db.query(UserPreference).all()}
    return {
        "today_caffeine_mg": today_caffeine,
        "today_sugar_g": today_sugar,
        "last_night_sleep_hours": sleep_hours,
        "user_preferences": preferences,
    }


def complete_pending_intake(
    history: list[dict],
    message: str,
    parsed_intake: dict,
    intake_provider: str,
) -> tuple[dict, str]:
    if parsed_intake.get("intent") == "log_drink" or not history:
        return parsed_intake, intake_provider

    latest_message = history[-1]
    if latest_message.get("role") != "assistant":
        return parsed_intake, intake_provider
    if not any(marker in latest_message.get("content", "") for marker in INTAKE_FOLLOW_UP_MARKERS):
        return parsed_intake, intake_provider

    user_messages = [item["content"] for item in history[-8:] if item.get("role") == "user"]
    for index in range(len(user_messages) - 1, -1, -1):
        pending, _ = parse_intake_with_fallback(user_messages[index])
        if pending.get("intent") != "log_drink":
            continue
        if not pending.get("missing_fields"):
            break

        combined_message = "。补充：".join(user_messages[index:] + [message])
        completed, completed_provider = parse_intake_with_fallback(combined_message)
        if completed.get("intent") != "log_drink":
            break
        if len(completed.get("missing_fields") or []) < len(pending.get("missing_fields") or []):
            return completed, completed_provider
        break

    return parsed_intake, intake_provider


def _begin_chat_turn(db, input_data) -> tuple[list[dict], dict]:
    user_log = ChatLog(
        date=input_data.date,
        role="user",
        content=input_data.message,
        timestamp=datetime.datetime.now().isoformat(),
    )
    db.add(user_log)
    db.commit()

    logs = db.query(ChatLog).filter(ChatLog.date == input_data.date).order_by(ChatLog.timestamp).all()
    history = [serialize_chat_log(log) for log in logs[:-1]]
    context = build_companion_context(db, input_data.date)
    return history, context


def _complete_chat_turn(db, input_data, dify_turn, fallback_reason) -> dict:
    agent_state = None
    nutrition_result = None
    risk_result = None

    if dify_turn is not None:
        provider = "dify"
        intake_provider = "dify_assistant"
        parsed_intake = dify_turn.get("parsed_intake")
        ai_response_text = dify_turn["text"]
        if parsed_intake:
            agent_state = run_agent_orchestrator(
                input_data.message,
                input_data.date,
                db,
                parsed_intake=parsed_intake,
                intake_provider="dify_assistant",
            )
            nutrition_result = agent_state.get("nutrition_result") or None
            risk_result = agent_state.get("risk_result") or None
            memory_updates = agent_state.get("memory_updates") or {}
        else:
            memory_updates = extract_memory_updates(input_data.message, "ask_advice", None, db)
    else:
        provider = "local"
        logs = db.query(ChatLog).filter(ChatLog.date == input_data.date).order_by(ChatLog.timestamp).all()
        history = [serialize_chat_log(log) for log in logs[:-1]]
        parsed_intake, intake_provider = parse_intake_with_fallback(input_data.message)
        parsed_intake, intake_provider = complete_pending_intake(
            history,
            input_data.message,
            parsed_intake,
            intake_provider,
        )
        agent_state = run_agent_orchestrator(
            input_data.message,
            input_data.date,
            db,
            parsed_intake=parsed_intake,
            intake_provider=intake_provider,
        )
        ai_response_text = agent_state["final_response"]
        nutrition_result = agent_state.get("nutrition_result") or None
        risk_result = agent_state.get("risk_result") or None
        memory_updates = agent_state.get("memory_updates") or {}

    memory_updates = apply_memory_updates(db, memory_updates)

    ai_log = ChatLog(
        date=input_data.date,
        role="assistant",
        content=ai_response_text,
        timestamp=datetime.datetime.now().isoformat(),
    )
    db.add(ai_log)
    db.commit()

    if agent_state is not None:
        trace_state = agent_state
        trace_state["memory_updates"] = memory_updates
        trace_state["error"] = trace_state.get("error") or fallback_reason
        if provider == "dify":
            trace_state["final_response"] = ai_response_text
            trace_state["model_name"] = "dify"
            trace_state.setdefault("tools_used", []).insert(0, "DIFY_CHATFLOW")
    else:
        trace_state = {
            "trace_id": f"trace_{uuid.uuid4().hex[:12]}",
            "user_message": input_data.message,
            "intent": "ask_advice",
            "intake_provider": "dify_assistant",
            "agents_called": ["dify_assistant"],
            "tools_used": ["DIFY_CHATFLOW"],
            "retrieved_docs": [],
            "model_name": "dify",
            "latency_ms": 0.0,
            "memory_updates": memory_updates,
            "final_action": "answer_advice",
            "error": fallback_reason,
        }
    save_agent_trace(db, trace_state)

    return {
        "status": "success",
        "response": ai_response_text,
        "provider": provider,
        "intake_provider": intake_provider,
        "fallback_reason": fallback_reason,
        "parsed_intake": parsed_intake,
        "nutrition_result": nutrition_result,
        "risk_result": risk_result,
        "trace_id": trace_state["trace_id"],
    }


def send_chat_message(db, input_data) -> dict:
    history, context = _begin_chat_turn(db, input_data)

    dify_turn = None
    fallback_reason = None
    if dify_available():
        try:
            dify_turn = generate_dify_turn(input_data.message, history, context)
        except DifyCompanionError as error:
            fallback_reason = error.code

    return _complete_chat_turn(db, input_data, dify_turn, fallback_reason)


def stream_chat_message(db, input_data):
    history, context = _begin_chat_turn(db, input_data)
    dify_turn = None
    fallback_reason = None
    emitted_answer = False

    if dify_available():
        try:
            for event in stream_dify_companion_turn(input_data.message, history, context):
                if event["type"] == "complete":
                    dify_turn = event["turn"]
                    continue
                emitted_answer = True
                yield event
        except DifyCompanionError as error:
            fallback_reason = error.code

    result = _complete_chat_turn(db, input_data, dify_turn, fallback_reason)
    if dify_turn is None or not emitted_answer:
        yield {"type": "replace", "text": result["response"]}
    yield {"type": "done", "data": result}
