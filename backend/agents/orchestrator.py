import datetime
import os
import time
import uuid
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from db.database import ChatLog, DrinkLog, SleepRecord
from services.memory_service import extract_memory_updates, read_user_memory
from services.nutrition_estimation_service import estimate_from_parsed_drink
from .companion_agent import generate_companion_response
from .intake_parser import parse_intake_with_fallback
from rules.risk_agent import evaluate_daily_risk


class DrinkMindAgentState(TypedDict, total=False):
    trace_id: str
    user_message: str
    date: str
    db: Any
    intent: str
    intake_provider: str
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
    final_action: str
    error: str | None


def run_agent_orchestrator(
    user_message: str,
    date: str,
    db,
    *,
    parsed_intake: dict | None = None,
    intake_provider: str | None = None,
) -> dict:
    started_at = time.perf_counter()
    state = _initial_state(
        user_message,
        date,
        db,
        parsed_intake=parsed_intake,
        intake_provider=intake_provider,
    )

    try:
        result = app_graph.invoke(state)
        return _finish_state(result, started_at)
    except Exception as e:
        state["error"] = str(e)
        state["final_action"] = "error"
        state["final_response"] = "\u8bf7\u6c42\u8fd8\u6ca1\u5904\u7406\u5b8c\u5c31\u5931\u8d25\u4e86\uff0c\u8bf7\u7a0d\u540e\u518d\u8bd5\u3002"
        return _finish_state(state, started_at)


def _initial_state(
    user_message: str,
    date: str,
    db,
    *,
    parsed_intake: dict | None = None,
    intake_provider: str | None = None,
) -> DrinkMindAgentState:
    parsed = dict(parsed_intake or {})
    provider = intake_provider or ""
    return {
        "trace_id": f"trace_{uuid.uuid4().hex[:12]}",
        "user_message": user_message,
        "date": date,
        "db": db,
        "intent": parsed.get("intent") or "",
        "intake_provider": provider,
        "parsed_drink": parsed,
        "nutrition_result": {},
        "risk_result": {},
        "memory_updates": {},
        "actions": [],
        "final_response": "",
        "agents_called": [provider] if provider else [],
        "tools_used": [],
        "retrieved_docs": [],
        "model_name": os.getenv("MODEL_NAME", "local"),
        "latency_ms": 0.0,
        "final_action": "",
        "error": None,
    }


def _parse_intake_node(state: DrinkMindAgentState) -> DrinkMindAgentState:
    parsed, provider = parse_intake_with_fallback(state["user_message"])
    state["parsed_drink"] = parsed
    state["intent"] = _route_intent(state["user_message"], parsed)
    state["intake_provider"] = provider
    state["agents_called"].append(provider)
    return state


def _log_follow_up_node(state: DrinkMindAgentState) -> DrinkMindAgentState:
    parsed = state["parsed_drink"]
    state["actions"].append("ask_follow_up")
    state["final_action"] = "ask_follow_up"
    state["final_response"] = parsed.get("follow_up") or "\u6211\u8fd8\u9700\u8981\u4e00\u70b9\u4fe1\u606f\uff0c\u624d\u80fd\u5e2e\u4f60\u8bb0\u5f55\u8fd9\u676f\u996e\u54c1\u3002"
    return state


def _log_drink_gate_node(state: DrinkMindAgentState) -> DrinkMindAgentState:
    return state


def _nutrition_log_node(state: DrinkMindAgentState) -> DrinkMindAgentState:
    parsed = state["parsed_drink"]
    nutrition = estimate_from_parsed_drink(parsed, state["date"], state["db"])

    state["tools_used"].extend([
        "nutrition_pipeline",
        nutrition.get("estimation_method") or "UNKNOWN_ESTIMATOR",
        "risk_rules",
        "memory_update",
    ])
    if nutrition.get("matched_knowledge_id"):
        state["retrieved_docs"].append(nutrition["matched_knowledge_id"])

    state["nutrition_result"] = nutrition
    state["risk_result"] = evaluate_daily_risk(state["date"], state["db"], nutrition)
    state["memory_updates"] = extract_memory_updates(state["user_message"], "log_drink", parsed, state["db"])
    state["actions"].extend(["parse_intake", "estimate_nutrition", "fill_log_form"])
    state["final_action"] = "fill_log_form"
    state["final_response"] = _format_log_drink_response(parsed, nutrition, state["risk_result"])
    return state


def _advice_node(state: DrinkMindAgentState) -> DrinkMindAgentState:
    state["intent"] = "ask_advice"
    state["tools_used"].extend(["risk_rules", "memory_read"])
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
    if state["intent"] == "log_drink":
        return "log_drink"
    return "ask_advice"


def _route_log_drink(state: DrinkMindAgentState) -> str:
    missing = state["parsed_drink"].get("missing_fields") or []
    return "ask_follow_up" if missing else "estimate_nutrition"


def _route_from_start(state: DrinkMindAgentState) -> str:
    if not state.get("parsed_drink"):
        return "parse_intake"
    return "log_drink" if state.get("intent") == "log_drink" else "ask_advice"


def _build_graph():
    graph = StateGraph(DrinkMindAgentState)
    graph.add_node("parse_intake", _parse_intake_node)
    graph.add_node("log_drink_gate", _log_drink_gate_node)
    graph.add_node("ask_follow_up", _log_follow_up_node)
    graph.add_node("estimate_nutrition", _nutrition_log_node)
    graph.add_node("ask_advice", _advice_node)

    graph.add_conditional_edges(
        START,
        _route_from_start,
        {
            "parse_intake": "parse_intake",
            "log_drink": "log_drink_gate",
            "ask_advice": "ask_advice",
        },
    )
    graph.add_conditional_edges(
        "parse_intake",
        _route_from_parse,
        {
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
    graph.add_edge("ask_follow_up", END)
    graph.add_edge("estimate_nutrition", END)
    graph.add_edge("ask_advice", END)
    return graph.compile()


app_graph = _build_graph()


def _format_log_drink_response(parsed: dict, nutrition: dict, risk: dict) -> str:
    brand = parsed.get("brand") or ""
    name = parsed.get("name") or "\u8fd9\u676f\u996e\u54c1"
    drink_label = " ".join(part for part in [brand, name] if part).strip()
    volume = parsed.get("volume") or nutrition.get("volume")
    caffeine = nutrition.get("caffeine", 0)
    sugar = nutrition.get("sugarContent", 0)
    return (
        f"\u5df2\u8bc6\u522b\uff1a{drink_label}\uff08{volume}ml\uff09\u3002"
        f"\u4f30\u7b97\u5496\u5561\u56e0 {caffeine}mg\uff0c\u7cd6\u5206 {sugar}g\u3002"
        f"\u9884\u8ba1\u4eca\u65e5\u98ce\u9669\uff1a{_risk_level_cn(risk.get('risk_level'))}\u3002"
    )


def _finish_state(state: dict, started_at: float) -> dict:
    state["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
    state.pop("db", None)
    return state


def _route_intent(user_message: str, parsed: dict) -> str:
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
        return "\u6309\u4eca\u5929\u5df2\u8bb0\u5f55\u7684\u6444\u5165\u91cf\u770b\uff0c\u5efa\u8bae\u6682\u65f6\u4e0d\u8981\u518d\u559d\u5496\u5561\u56e0\u6216\u9ad8\u7cd6\u996e\u54c1\u4e86\u3002"
    if risk.get("risk_level") == "medium":
        return "\u4eca\u5929\u8fd8\u6709\u4e00\u70b9\u7a7a\u95f4\uff0c\u4f46\u5efa\u8bae\u9009\u4f4e\u7cd6\u3001\u5496\u5561\u56e0\u9002\u4e2d\u7684\u996e\u54c1\u3002"
    return "\u76ee\u524d\u7684\u6444\u5165\u91cf\u8fd8\u7b97\u53ef\u63a7\uff0c\u5c11\u91cf\u4f4e\u7cd6\u996e\u54c1\u53ef\u4ee5\u7eb3\u5165\u4eca\u5929\u7684\u9884\u7b97\u3002"


def _risk_level_cn(value: str | None) -> str:
    return {
        "high": "\u9ad8",
        "medium": "\u4e2d",
        "low": "\u4f4e",
    }.get(value or "", "\u672a\u77e5")


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
