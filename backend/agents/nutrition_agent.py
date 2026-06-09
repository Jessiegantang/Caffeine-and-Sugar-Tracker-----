import datetime
import uuid

from agent import enrich_drink_data
from .composition_agent import estimate_composition_nutrition


KNOWLEDGE_METHODS_TO_KEEP = {"SQL_EXACT_MATCH", "RAG_MATCH"}
FALLBACK_METHODS_TO_REPLACE = {"LLM_ESTIMATION", "LOCAL_ESTIMATOR"}


def estimate_from_parsed_drink(parsed_drink: dict, date: str, db) -> dict:
    now_time = datetime.datetime.now().strftime("%H:%M")
    drink = {
        "id": f"draft_{uuid.uuid4().hex[:10]}",
        "date": date,
        "brand": parsed_drink.get("brand") or "",
        "name": parsed_drink.get("name") or "",
        "type": parsed_drink.get("type") or "coffee",
        "sugar": parsed_drink.get("sugar") or "unknown",
        "volume": parsed_drink.get("volume") or 500,
        "startTime": parsed_drink.get("time") if _is_time(parsed_drink.get("time")) else now_time,
        "endTime": parsed_drink.get("time") if _is_time(parsed_drink.get("time")) else now_time,
        "caffeine": 0.0,
        "sugarContent": 0.0,
        "alcoholContent": 0.0,
        "abv": 0.0,
        "baseSugarDensity": None,
        "status": "draft",
        "data_source": "用户录入",
        "confidence": parsed_drink.get("confidence") or 0.0,
    }
    enriched = enrich_drink_data(drink, db)
    if not _should_use_composition(enriched):
        return enriched

    try:
        composition_result = estimate_composition_nutrition(drink)
    except Exception as e:
        print(f"[Composition Estimation Error] {e}", flush=True)
        return enriched

    return {
        **enriched,
        **composition_result,
        "id": enriched.get("id", drink["id"]),
        "date": enriched.get("date", drink["date"]),
        "brand": enriched.get("brand", drink["brand"]),
        "name": enriched.get("name", drink["name"]),
        "type": enriched.get("type", drink["type"]),
        "sugar": enriched.get("sugar", drink["sugar"]),
        "volume": enriched.get("volume", drink["volume"]),
        "startTime": enriched.get("startTime", drink["startTime"]),
        "endTime": enriched.get("endTime", drink["endTime"]),
        "status": enriched.get("status", drink["status"]),
        "agent_trace_id": enriched.get("agent_trace_id"),
    }


def _should_use_composition(enriched: dict) -> bool:
    method = enriched.get("estimation_method")
    if method in KNOWLEDGE_METHODS_TO_KEEP:
        return False
    if method in FALLBACK_METHODS_TO_REPLACE:
        return True
    if not enriched.get("matched_knowledge_id") and float(enriched.get("confidence") or 0.0) < 0.7:
        return True
    return False


def _is_time(value: str | None) -> bool:
    if not value:
        return False
    parts = value.split(":")
    return len(parts) == 2 and all(part.isdigit() for part in parts)
