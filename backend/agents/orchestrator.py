import datetime
import os
import time
import uuid

from agent import generate_companion_response
from database import ChatLog, DrinkLog, SleepRecord
from .health_plan_agent import build_plan_days, infer_plan_target
from .intake_parser import parse_intake
from .memory_agent import extract_memory_updates, read_user_memory
from .nutrition_agent import estimate_from_parsed_drink
from .risk_agent import evaluate_daily_risk


def run_agent_orchestrator(user_message: str, date: str, db) -> dict:
    started_at = time.perf_counter()
    trace_id = f"trace_{uuid.uuid4().hex[:12]}"
    state = {
        "trace_id": trace_id,
        "user_message": user_message,
        "intent": "",
        "parsed_drink": {},
        "nutrition_result": {},
        "risk_result": {},
        "memory_updates": {},
        "actions": [],
        "final_response": "",
        "agents_called": [],
        "tools_used": [],
        "retrieved_docs": [],
        "model_name": os.getenv("MODEL_NAME", "local"),
        "latency_ms": 0.0,
        "confidence": 0.0,
        "final_action": "",
        "error": None,
    }

    try:
        parsed = parse_intake(user_message)
        state["agents_called"].append("intake_parser")
        intent = _route_intent(user_message, parsed)
        state["intent"] = intent

        if intent == "create_health_plan":
            target = infer_plan_target(user_message)
            state["agents_called"].append("health_plan_agent")
            state["tools_used"].append("STRUCTURED_PLAN_GENERATOR")
            state["actions"].append("create_health_plan")
            state["final_action"] = "create_health_plan"
            state["memory_updates"] = {"goal": target}
            state["risk_result"] = evaluate_daily_risk(date, db)
            state["confidence"] = 0.8
            state["final_response"] = f"Generated a 7-day structured plan for {target}."
            state["health_plan_preview"] = build_plan_days(target)
            return _finish_state(state, started_at)

        if intent == "log_drink":
            state["parsed_drink"] = parsed
            state["confidence"] = parsed.get("confidence") or 0.0
            missing = parsed.get("missing_fields") or []
            if missing:
                state["actions"].append("ask_follow_up")
                state["final_action"] = "ask_follow_up"
                state["final_response"] = parsed.get("follow_up") or "I need one more detail before logging this drink."
                return _finish_state(state, started_at)

            nutrition = estimate_from_parsed_drink(parsed, date, db)
            state["agents_called"].extend(["nutrition_agent", "risk_agent", "memory_agent"])
            state["tools_used"].append(nutrition.get("estimation_method") or "UNKNOWN_ESTIMATOR")
            if nutrition.get("matched_knowledge_id"):
                state["retrieved_docs"].append(nutrition["matched_knowledge_id"])
            state["nutrition_result"] = nutrition
            state["risk_result"] = evaluate_daily_risk(date, db, nutrition)
            state["memory_updates"] = extract_memory_updates(user_message, intent, parsed, db)
            state["confidence"] = nutrition.get("confidence") or parsed.get("confidence") or 0.0
            state["actions"].extend(["parse_intake", "estimate_nutrition", "fill_log_form"])
            state["final_action"] = "fill_log_form"
            state["final_response"] = _format_log_drink_response(parsed, nutrition, state["risk_result"])
            return _finish_state(state, started_at)

        state["intent"] = "ask_advice"
        context = _build_chat_context(date, db)
        history = _load_chat_history(date, db)
        state["agents_called"].extend(["risk_agent", "memory_agent"])
        state["risk_result"] = evaluate_daily_risk(date, db)
        state["memory_updates"] = {}
        state["actions"].append("answer_advice")
        state["final_action"] = "answer_advice"
        if _has_real_llm_key():
            state["tools_used"].append("LLM_CHAT")
            state["agents_called"].append("companion_agent")
            state["final_response"] = generate_companion_response(user_message, history, context)
        else:
            state["tools_used"].append("LOCAL_ADVICE")
            state["final_response"] = _local_advice_response(state["risk_result"])
        return _finish_state(state, started_at)
    except Exception as e:
        state["error"] = str(e)
        state["final_action"] = "error"
        state["final_response"] = "Agent failed before completing the request."
        return _finish_state(state, started_at)


def _format_log_drink_response(parsed: dict, nutrition: dict, risk: dict) -> str:
    brand = parsed.get("brand") or ""
    name = parsed.get("name") or "this drink"
    volume = parsed.get("volume") or nutrition.get("volume")
    caffeine = nutrition.get("caffeine", 0)
    sugar = nutrition.get("sugarContent", 0)
    return (
        f"Parsed {brand} {name} ({volume}ml). "
        f"Estimated caffeine {caffeine}mg and sugar {sugar}g. "
        f"Projected daily risk: {risk.get('risk_level')}."
    )


def _finish_state(state: dict, started_at: float) -> dict:
    state["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
    return state


def _route_intent(user_message: str, parsed: dict) -> str:
    plan_markers = ["计划", "7天", "七天", "一周", "目标"]
    plan_goal_markers = ["减少", "降低", "少喝", "控糖", "睡眠", "考试", "加班"]
    if any(marker in user_message for marker in plan_markers) and any(marker in user_message for marker in plan_goal_markers):
        return "create_health_plan"
    advice_markers = ["能喝", "还能", "可以喝", "建议", "怎么办", "吗", "?"]
    has_advice_marker = any(marker in user_message for marker in advice_markers)
    has_concrete_drink = bool(parsed.get("brand") or parsed.get("volume") or parsed.get("sugar"))
    if has_advice_marker and not has_concrete_drink:
        return "ask_advice"
    return parsed.get("intent") or "ask_advice"


def _has_real_llm_key() -> bool:
    api_key = os.getenv("OPENAI_API_KEY", "")
    return bool(api_key and not api_key.startswith("dummy_"))


def _local_advice_response(risk: dict) -> str:
    if risk.get("risk_level") == "high":
        return "Based on today's totals, I would pause caffeine or sugar-heavy drinks for now."
    if risk.get("risk_level") == "medium":
        return "You can still choose a lighter drink, but I would keep it low sugar and moderate caffeine."
    return "Your current totals look manageable, so a small low-sugar drink should fit today's budget."


def _build_chat_context(date: str, db) -> dict:
    records = db.query(DrinkLog).filter(
        DrinkLog.date == date,
        DrinkLog.status == "active"
    ).all()
    sleep_record = db.query(SleepRecord).filter(SleepRecord.date == date).first()
    return {
        "today_caffeine_mg": sum(record.caffeine or 0 for record in records),
        "today_sugar_g": sum(record.sugarContent or 0 for record in records),
        "last_night_sleep_hours": sleep_record.sleep_hours if sleep_record else "unknown",
        "user_preferences": read_user_memory(db),
    }


def _load_chat_history(date: str, db) -> list[dict]:
    rows = db.query(ChatLog).filter(ChatLog.date == date).order_by(ChatLog.timestamp).all()
    return [{"role": row.role, "content": row.content} for row in rows]


def save_chat_turn(date: str, user_message: str, assistant_message: str, db) -> None:
    now = datetime.datetime.now().isoformat()
    db.add(ChatLog(date=date, role="user", content=user_message, timestamp=now))
    db.add(ChatLog(date=date, role="assistant", content=assistant_message, timestamp=now))
    db.commit()
