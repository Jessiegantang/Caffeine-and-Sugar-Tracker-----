import datetime
import uuid

from workflows.nutrition_pipeline import estimate_drink_nutrition


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
        "baseSugarDensity": None,
        "status": "draft",
        "data_source": "用户录入",
        "confidence": parsed_drink.get("confidence") or 0.0,
    }
    return estimate_drink_nutrition(drink, db)


def _is_time(value: str | None) -> bool:
    if not value:
        return False
    parts = value.split(":")
    return len(parts) == 2 and all(part.isdigit() for part in parts)
