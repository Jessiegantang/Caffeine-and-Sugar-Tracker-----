import datetime
import os
import time
import uuid
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from agent import generate_companion_response
from database import ChatLog, DrinkLog, SleepRecord
from .health_plan_agent import build_plan_days, infer_plan_target
from .intake_parser import parse_intake
from .memory_agent import extract_memory_updates, read_user_memory
from .nutrition_agent import estimate_from_parsed_drink
from .risk_agent import evaluate_daily_risk


class DrinkMindAgentState(TypedDict, total=False):
    trace_id: str
    user_message: str
    date: str
    db: Any
    intent: str
    parsed_drink: dict
    nutrition_result: dict
    risk_result: dict
    memory_updates: dict
    actions: list[str]
    final_response: str
    agents_called: list[str]
    tools_used: list[str]
    retrieved_docs: list[str]
    model_name: str
    latency_ms: float
    confidence: float
    final_action: str
    error: str | None
    health_plan_preview: list[dict]


def run_agent_orchestrator(user_message: str, date: str, db) -> dict:
    started_at = time.perf_counter()
    state = _initial_state(user_message, date, db)

    try:
        result = app_graph.invoke(state)
        return _finish_state(result, started_at)
    except Exception as e:
        state["error"] = str(e)
        state["final_action"] = "error"
        state["final_response"] = "Agent failed before completing the request."
        return _finish_state(state, started_at)


def _initial_state(user_message: str, date: str, db) -> DrinkMindAgentState:
    return {
        "trace_id": f"trace_{uuid.uuid4().hex[:12]}",
        "user_message": user_message,
        "date": date,
        "db": db,
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


def _parse_intake_node(state: DrinkMindAgentState) -> DrinkMindAgentState:
    parsed = parse_intake(state["user_message"])
    state["parsed_drink"] = parsed
    state["intent"] = _route_intent(state["user_message"], parsed)
    state["agents_called"].append("intake_parser")
    return state


def _health_plan_node(state: DrinkMindAgentState) -> DrinkMindAgentState:
    target = infer_plan_target(state["user_message"])
    state["agents_called"].append("health_plan_agent")
    state["tools_used"].append("STRUCTURED_PLAN_GENERATOR")
    state["actions"].append("create_health_plan")
    state["final_action"] = "create_health_plan"
    state["memory_updates"] = {"goal": target}
    state["risk_result"] = evaluate_daily_risk(state["date"], state["db"])
    state["confidence"] = 0.8
    state["final_response"] = f"Generated a 7-day structured plan for {target}."
    state["health_plan_preview"] = build_plan_days(target)
    return state


def _log_follow_up_node(state: DrinkMindAgentState) -> DrinkMindAgentState:
    parsed = state["parsed_drink"]
    state["confidence"] = parsed.get("confidence") or 0.0
    state["actions"].append("ask_follow_up")
    state["final_action"] = "ask_follow_up"
    state["final_response"] = parsed.get("follow_up") or "I need one more detail before logging this drink."
    return state


def _log_drink_gate_node(state: DrinkMindAgentState) -> DrinkMindAgentState:
    return state


def _nutrition_log_node(state: DrinkMindAgentState) -> DrinkMindAgentState:
    parsed = state["parsed_drink"]
    nutrition = estimate_from_parsed_drink(parsed, state["date"], state["db"])

    state["agents_called"].extend(["nutrition_agent", "risk_agent", "memory_agent"])
    state["tools_used"].append(nutrition.get("estimation_method") or "UNKNOWN_ESTIMATOR")
    if nutrition.get("matched_knowledge_id"):
        state["retrieved_docs"].append(nutrition["matched_knowledge_id"])

    state["nutrition_result"] = nutrition
    state["risk_result"] = evaluate_daily_risk(state["date"], state["db"], nutrition)
    state["memory_updates"] = extract_memory_updates(state["user_message"], "log_drink", parsed, state["db"])
    state["confidence"] = nutrition.get("confidence") or parsed.get("confidence") or 0.0
    state["actions"].extend(["parse_intake", "estimate_nutrition", "fill_log_form"])
    state["final_action"] = "fill_log_form"
    state["final_response"] = _format_log_drink_response(parsed, nutrition, state["risk_result"])
    return state


def _advice_node(state: DrinkMindAgentState) -> DrinkMindAgentState:
    state["intent"] = "ask_advice"
    state["agents_called"].extend(["risk_agent", "memory_agent"])
    state["risk_result"] = evaluate_daily_risk(state["date"], state["db"])
    state["memory_updates"] = {}
    state["actions"].append("answer_advice")
    state["final_action"] = "answer_advice"

    if _has_real_llm_key():
        context = _build_chat_context(state["date"], state["db"])
        history = _load_chat_history(state["date"], state["db"])
        state["tools_used"].append("LLM_CHAT")
        state["agents_called"].append("companion_agent")
        state["final_response"] = generate_companion_response(state["user_message"], history, context)
    else:
        state["tools_used"].append("LOCAL_ADVICE")
        state["final_response"] = _local_advice_response(state["risk_result"])
    return state


def _route_from_parse(state: DrinkMindAgentState) -> str:
    if state["intent"] == "create_health_plan":
        return "health_plan"
    if state["intent"] == "log_drink":
        return "log_drink"
    return "ask_advice"


def _route_log_drink(state: DrinkMindAgentState) -> str:
    missing = state["parsed_drink"].get("missing_fields") or []
    return "ask_follow_up" if missing else "estimate_nutrition"


def _build_graph():
    graph = StateGraph(DrinkMindAgentState)
    graph.add_node("parse_intake", _parse_intake_node)
    graph.add_node("health_plan", _health_plan_node)
    graph.add_node("log_drink_gate", _log_drink_gate_node)
    graph.add_node("ask_follow_up", _log_follow_up_node)
    graph.add_node("estimate_nutrition", _nutrition_log_node)
    graph.add_node("ask_advice", _advice_node)

    graph.add_edge(START, "parse_intake")
    graph.add_conditional_edges(
        "parse_intake",
        _route_from_parse,
        {
            "health_plan": "health_plan",
            "log_drink": "log_drink_gate",
            "ask_advice": "ask_advice",
        },
    )
    graph.add_conditional_edges(
        "log_drink_gate",
        _route_log_drink,
        {
            "ask_follow_up": "ask_follow_up",
            "estimate_nutrition": "estimate_nutrition",
        },
    )
    graph.add_edge("health_plan", END)
    graph.add_edge("ask_follow_up", END)
    graph.add_edge("estimate_nutrition", END)
    graph.add_edge("ask_advice", END)
    return graph.compile()


app_graph = _build_graph()


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
    state.pop("db", None)
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
