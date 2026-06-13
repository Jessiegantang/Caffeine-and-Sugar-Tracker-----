import json
import uuid
from typing import Any, Dict

from sqlalchemy.orm import Session

from db.database import AgentTrace


def save_agent_trace(db: Session, trace_state: Dict[str, Any]) -> None:
    trace = AgentTrace(
        id=trace_state.get("trace_id") or f"trace_{uuid.uuid4().hex[:12]}",
        intent=trace_state.get("intent"),
        user_input=trace_state.get("user_message"),
        agents_called=json.dumps(trace_state.get("agents_called", []), ensure_ascii=False),
        tools_used=json.dumps(trace_state.get("tools_used", []), ensure_ascii=False),
        retrieved_docs=json.dumps(trace_state.get("retrieved_docs", []), ensure_ascii=False),
        model_name=trace_state.get("model_name"),
        latency_ms=trace_state.get("latency_ms"),
        confidence=trace_state.get("confidence"),
        final_action=trace_state.get("final_action"),
        error=trace_state.get("error"),
    )
    db.add(trace)
    db.commit()


def parse_json_list(value: str | None) -> list:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def list_agent_traces(db: Session, limit: int = 20) -> dict:
    limit = max(1, min(limit, 100))
    traces = db.query(AgentTrace).order_by(AgentTrace.created_at.desc()).limit(limit).all()
    return {
        "status": "success",
        "traces": [
            {
                "id": trace.id,
                "created_at": trace.created_at,
                "intent": trace.intent,
                "user_input": trace.user_input,
                "agents_called": parse_json_list(trace.agents_called),
                "tools_used": parse_json_list(trace.tools_used),
                "retrieved_docs": parse_json_list(trace.retrieved_docs),
                "model_name": trace.model_name,
                "latency_ms": trace.latency_ms,
                "confidence": trace.confidence,
                "final_action": trace.final_action,
                "error": trace.error,
            }
            for trace in traces
        ]
    }
