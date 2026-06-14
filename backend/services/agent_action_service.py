import uuid

from agents.intake_parser import parse_intake_message
from agents.orchestrator import run_agent_orchestrator
from services.memory_service import apply_memory_updates
from services.trace_service import save_agent_trace


def parse_intake(db, input_data) -> dict:
    parsed = parse_intake_message(input_data.message)
    trace_state = {
        "trace_id": f"trace_{uuid.uuid4().hex[:12]}",
        "user_message": input_data.message,
        "intent": parsed.get("intent"),
        "agents_called": ["intake_parser"],
        "tools_used": ["LOCAL_INTAKE_PARSER"],
        "retrieved_docs": [],
        "model_name": "local",
        "latency_ms": 0.0,
        "confidence": parsed.get("confidence"),
        "final_action": "parse_intake",
        "error": None,
    }
    save_agent_trace(db, trace_state)
    return {"status": "success", "parsed_intake": parsed, "trace_id": trace_state["trace_id"]}


def act(db, input_data) -> dict:
    agent_state = run_agent_orchestrator(input_data.message, input_data.date, db)
    agent_state["memory_updates"] = apply_memory_updates(db, agent_state.get("memory_updates", {}))
    save_agent_trace(db, agent_state)
    return {"status": "success", "agent_state": agent_state}
