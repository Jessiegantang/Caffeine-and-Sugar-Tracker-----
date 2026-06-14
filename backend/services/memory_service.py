import datetime
import json
from collections import Counter

from agents.memory_extractor_agent import infer_memory_updates_with_llm
from db.database import DrinkLog, UserPreference


SUGAR_GOAL_PATTERNS = [
    "\u5c11\u559d\u7cd6", "\u5c11\u7cd6", "\u51cf\u5c11\u7cd6", "\u63a7\u7cd6", "\u6212\u7cd6",
    "\u8840\u7cd6\u504f\u9ad8", "\u8840\u7cd6\u9ad8", "\u4f53\u68c0\u8840\u7cd6",
    "\u533b\u751f\u8ba9\u6211\u63a7\u7cd6", "\u7cd6\u5316\u8840\u7ea2\u86cb\u767d", "\u80f0\u5c9b\u7d20", "\u7cd6\u5c3f",
    "\u63a7\u5236\u751c\u98df", "\u5c11\u559d\u751c", "\u4e0d\u60f3\u6444\u5165\u592a\u591a\u7cd6",
]

CAFFEINE_GOAL_PATTERNS = [
    "\u5c11\u559d\u5496\u5561", "\u51cf\u5c11\u5496\u5561\u56e0", "\u964d\u4f4e\u5496\u5561\u56e0", "\u5c11\u559d\u5496\u5561\u56e0",
    "\u7761\u4e0d\u597d", "\u5931\u7720", "\u7761\u7720", "\u7761\u89c9\u53d7\u5f71\u54cd", "\u665a\u4e0a\u7761\u4e0d\u7740",
]

CAFFEINE_SENSITIVITY_PATTERNS = [
    "\u5496\u5561\u56e0\u654f\u611f", "\u559d\u5496\u5561\u7761\u4e0d\u7740", "\u559d\u5b8c\u5fc3\u614c",
    "\u5fc3\u614c", "\u5fc3\u8df3\u5feb", "\u7126\u8651", "\u624b\u6296",
]

SUGAR_PREFERENCE_PATTERNS = [
    ("three", ["three", "\u4e09\u5206\u7cd6", "3\u5206\u7cd6", "\u5fae\u7cd6"]),
    ("half", ["half", "\u534a\u7cd6", "\u4e94\u5206\u7cd6", "5\u5206\u7cd6"]),
    ("none", ["none", "\u65e0\u7cd6", "\u4e0d\u52a0\u7cd6", "\u96f6\u7cd6", "0\u7cd6"]),
]

HEALTH_CONTEXT_PATTERNS = [
    ("blood_sugar_attention", ["\u8840\u7cd6", "\u7cd6\u5316\u8840\u7ea2\u86cb\u767d", "\u80f0\u5c9b\u7d20", "\u7cd6\u5c3f"]),
    ("doctor_advice", ["\u533b\u751f", "\u533b\u5631", "\u4f53\u68c0"]),
    ("sleep_attention", ["\u7761\u7720", "\u7761\u4e0d\u597d", "\u5931\u7720", "\u7761\u4e0d\u7740"]),
    ("caffeine_sensitivity", ["\u5fc3\u614c", "\u5fc3\u8df3\u5feb", "\u7126\u8651", "\u624b\u6296", "\u5496\u5561\u56e0\u654f\u611f"]),
]

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
    local_updates = infer_memory_updates_from_text(user_message)
    updates.update(local_updates)
    updates.update(infer_memory_updates_with_llm(user_message, local_updates))
    return updates


def infer_memory_updates_from_text(user_message: str) -> dict:
    text = _normalize_text(user_message)
    updates: dict = {}

    if _contains_any(text, SUGAR_GOAL_PATTERNS):
        updates["goal"] = "reduce_sugar"
    if _contains_any(text, CAFFEINE_GOAL_PATTERNS):
        updates["goal"] = updates.get("goal") or "reduce_caffeine"
    if _contains_any(text, CAFFEINE_SENSITIVITY_PATTERNS):
        updates["caffeine_sensitivity"] = "high"
        updates["goal"] = updates.get("goal") or "reduce_caffeine"

    preferred_sugar = _infer_preferred_sugar(text)
    if preferred_sugar:
        updates["preferred_sugar"] = preferred_sugar

    health_context = _infer_health_context(text)
    if health_context:
        updates["health_context"] = health_context

    return updates


def _normalize_text(value: str) -> str:
    return (value or "").strip().lower().replace(" ", "")


def _contains_any(text: str, patterns: list[str]) -> bool:
    return any(pattern.lower().replace(" ", "") in text for pattern in patterns)


def _infer_preferred_sugar(text: str) -> str | None:
    matches: list[tuple[int, str]] = []
    for value, aliases in SUGAR_PREFERENCE_PATTERNS:
        for alias in aliases:
            normalized_alias = alias.lower().replace(" ", "")
            index = text.rfind(normalized_alias)
            if index >= 0:
                matches.append((index, value))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0])
    return matches[-1][1]


def _infer_health_context(text: str) -> str | None:
    contexts = []
    for context, patterns in HEALTH_CONTEXT_PATTERNS:
        if _contains_any(text, patterns):
            contexts.append(context)
    if "doctor_advice" in contexts and len(contexts) == 1:
        contexts.remove("doctor_advice")
    if not contexts:
        return None
    return contexts[0] if len(contexts) == 1 else ",".join(contexts)


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
