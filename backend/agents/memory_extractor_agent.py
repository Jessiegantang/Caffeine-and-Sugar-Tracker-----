import json

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from .llm_config import llm, llm_enabled


ALLOWED_MEMORY_KEYS = {
    "goal",
    "preferred_sugar",
    "caffeine_sensitivity",
    "health_context",
}

ALLOWED_GOALS = {"reduce_sugar", "reduce_caffeine", "balanced_drink_routine", "work_week_strategy"}
ALLOWED_SUGAR_LEVELS = {"none", "three", "half", "seven", "full"}
ALLOWED_CAFFEINE_SENSITIVITY = {"high", "medium", "low"}
ALLOWED_HEALTH_CONTEXTS = {
    "blood_sugar_attention",
    "doctor_advice",
    "sleep_attention",
    "caffeine_sensitivity",
    "stress_attention",
}


class MemoryExtractionResult(BaseModel):
    updates: dict = Field(default_factory=dict, description="Memory updates inferred from the message.")
    reason: str | None = Field(default=None, description="Short reason for the inferred memory updates.")


def infer_memory_updates_with_llm(user_message: str, local_updates: dict | None = None) -> dict:
    if not llm_enabled():
        return {}
    try:
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You extract stable beverage-health memory from Chinese user messages. "
                "Return only structured fields. Do not infer from vague medical wording alone. "
                "For example, 'doctor told me to pay attention' is not enough by itself. "
                "Only set reduce_sugar when the message mentions sugar, blood glucose, HbA1c, diabetes, insulin, or sweet drinks. "
                "Only set reduce_caffeine or caffeine_sensitivity when the message mentions caffeine, coffee, sleep, palpitations, anxiety, or tremor. "
                "Allowed update keys: goal, preferred_sugar, caffeine_sensitivity, health_context. "
                "Allowed goal values: reduce_sugar, reduce_caffeine, balanced_drink_routine, work_week_strategy. "
                "Allowed preferred_sugar values: none, three, half, seven, full. "
                "Allowed caffeine_sensitivity values: high, medium, low. "
                "Allowed health_context values can be a comma-separated subset of: blood_sugar_attention, doctor_advice, sleep_attention, caffeine_sensitivity, stress_attention. "
                "Return empty updates when the message is only casual chat or too ambiguous.",
            ),
            ("user", "message: {message}\nlocal_updates: {local_updates}"),
        ])
        structured_llm = llm.with_structured_output(MemoryExtractionResult, method="function_calling")
        parsed = (prompt | structured_llm).invoke({
            "message": user_message,
            "local_updates": json.dumps(local_updates or {}, ensure_ascii=False),
        })
        data = parsed.model_dump() if hasattr(parsed, "model_dump") else parsed.dict()
        return _sanitize_llm_updates(data.get("updates") or {})
    except Exception as e:
        print(f"[Memory Extractor] Falling back to local memory rules: {e}", flush=True)
        return {}


def _sanitize_llm_updates(raw_updates: dict) -> dict:
    clean = {}
    for key, value in (raw_updates or {}).items():
        if key not in ALLOWED_MEMORY_KEYS or value in [None, "", "unknown"]:
            continue
        if key == "goal" and value in ALLOWED_GOALS:
            clean[key] = value
        elif key == "preferred_sugar" and value in ALLOWED_SUGAR_LEVELS:
            clean[key] = value
        elif key == "caffeine_sensitivity" and value in ALLOWED_CAFFEINE_SENSITIVITY:
            clean[key] = value
        elif key == "health_context":
            contexts = [
                item.strip()
                for item in str(value).split(",")
                if item.strip() in ALLOWED_HEALTH_CONTEXTS
            ]
            if "doctor_advice" in contexts and len(contexts) == 1:
                contexts.remove("doctor_advice")
            if contexts:
                clean[key] = ",".join(dict.fromkeys(contexts))
    return clean
