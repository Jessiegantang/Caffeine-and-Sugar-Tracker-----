import datetime
import json
from collections import Counter

from database import DrinkLog, UserPreference


def read_user_memory(db) -> dict:
    try:
        rows = db.query(UserPreference).all()
        memory = {}
        for row in rows:
            try:
                memory[row.key] = json.loads(row.value)
            except Exception:
                memory[row.key] = row.value
        return memory
    except Exception:
        return {}


def plan_memory_updates(intent: str, parsed_drink: dict | None) -> dict:
    if intent != "log_drink" or not parsed_drink:
        return {}
    updates = {}
    if parsed_drink.get("brand"):
        updates["last_brand_seen"] = parsed_drink["brand"]
    if parsed_drink.get("sugar"):
        updates["last_sugar_seen"] = parsed_drink["sugar"]
    if parsed_drink.get("time"):
        updates["last_drink_time_seen"] = parsed_drink["time"]
    return updates


def extract_memory_updates(user_message: str, intent: str, parsed_drink: dict | None, db) -> dict:
    updates = summarize_preferences_from_logs(db)
    updates.update(plan_memory_updates(intent, parsed_drink))
    lower_message = user_message.lower()

    if any(phrase in user_message for phrase in ["少喝糖", "少糖", "减少糖", "控糖", "戒糖"]):
        updates["goal"] = "reduce_sugar"
    if any(phrase in user_message for phrase in ["少喝咖啡", "减少咖啡因", "降低咖啡因", "睡眠"]):
        updates["goal"] = updates.get("goal") or "reduce_caffeine"
    if any(phrase in user_message for phrase in ["咖啡因敏感", "喝咖啡睡不着", "心慌"]):
        updates["caffeine_sensitivity"] = "high"
    if "three" in lower_message or "三分糖" in user_message:
        updates["preferred_sugar"] = "three"
    if "half" in lower_message or "半糖" in user_message:
        updates["preferred_sugar"] = "half"
    if "无糖" in user_message or "不加糖" in user_message:
        updates["preferred_sugar"] = "none"

    return updates


def summarize_preferences_from_logs(db) -> dict:
    try:
        logs = db.query(DrinkLog).filter(DrinkLog.status == "active").all()
    except Exception:
        return {}

    updates = {}
    brands = [log.brand for log in logs if log.brand]
    sugars = [log.sugar for log in logs if log.sugar]
    hours = []
    for log in logs:
        try:
            hours.append(int((log.startTime or "0:0").split(":")[0]))
        except Exception:
            pass

    if brands:
        updates["preferred_brands"] = [brand for brand, _ in Counter(brands).most_common(3)]
    if sugars:
        updates["preferred_sugar"] = Counter(sugars).most_common(1)[0][0]
    if hours:
        avg_hour = sum(hours) / len(hours)
        if avg_hour < 12:
            updates["common_drink_time"] = "morning"
        elif avg_hour < 18:
            updates["common_drink_time"] = "afternoon"
        else:
            updates["common_drink_time"] = "evening"
    return updates


def apply_memory_updates(db, updates: dict) -> dict:
    if not updates:
        return {}
    now = datetime.datetime.now().isoformat()
    saved = {}
    for key, value in updates.items():
        row = db.query(UserPreference).filter(UserPreference.key == key).first()
        serialized = json.dumps(value, ensure_ascii=False)
        if row:
            row.value = serialized
            row.updated_at = now
        else:
            row = UserPreference(key=key, value=serialized, updated_at=now)
            db.add(row)
        saved[key] = value
    db.commit()
    return saved


def clear_user_memory(db) -> int:
    deleted = db.query(UserPreference).delete()
    db.commit()
    return deleted
