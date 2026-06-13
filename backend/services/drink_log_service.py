import datetime
import json
from typing import Any, Dict, List

from workflows.nutrition_pipeline import estimate_drink_nutrition
from db.database import ChatLog, DrinkLog, SleepRecord


def safe_json_loads(value: str | None, default=None):
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def serialize_drink_log(log: DrinkLog) -> Dict[str, Any]:
    row = {c.name: getattr(log, c.name) for c in log.__table__.columns}
    row["composition"] = safe_json_loads(row.get("composition_json"), None)
    row["explainability"] = safe_json_loads(row.get("explainability_json"), None)
    return row


def drink_log_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    allowed_columns = {column.name for column in DrinkLog.__table__.columns}
    payload = {key: value for key, value in data.items() if key in allowed_columns}
    if isinstance(payload.get("reasoning"), (list, dict)):
        payload["reasoning"] = json.dumps(payload["reasoning"], ensure_ascii=False)
    if data.get("composition") is not None:
        payload["composition_json"] = json.dumps(data.get("composition"), ensure_ascii=False)
    if data.get("explainability") is not None:
        payload["explainability_json"] = json.dumps(data.get("explainability"), ensure_ascii=False)
    return payload


def nutrition_result_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    keys = [
        "caffeine",
        "sugarContent",
        "confidence",
        "estimation_method",
        "data_source",
        "matched_knowledge_id",
        "retrieval_score",
        "reasoning",
        "composition",
        "explainability",
    ]
    return {key: data.get(key) for key in keys}


def list_active_logs(db) -> List[Dict[str, Any]]:
    logs = db.query(DrinkLog).filter(DrinkLog.status == 'active').all()
    return [serialize_drink_log(log) for log in logs]


def sync_logs(db, logs) -> Dict[str, Any]:
    db.query(DrinkLog).delete()
    for log in logs:
        db_log = DrinkLog(**log.dict())
        db.add(db_log)
    db.commit()
    return {"status": "success", "count": len(logs)}


def delete_log(db, log_id: str) -> bool:
    db_log = db.query(DrinkLog).filter(DrinkLog.id == log_id).first()
    if not db_log:
        return False
    db_log.status = 'deleted'
    db.commit()
    return True


def log_drink(db, drink) -> Dict[str, Any]:
    drink_dict = drink.dict()
    drink_dict["data_source"] = "用户录入"

    enriched_drink = estimate_drink_nutrition(drink_dict, db)
    db_payload = drink_log_payload(enriched_drink)

    db_log = db.query(DrinkLog).filter(DrinkLog.id == drink.id).first()
    if not db_log:
        db_log = DrinkLog(**db_payload)
        db.add(db_log)
        db.commit()
    else:
        for k, v in db_payload.items():
            setattr(db_log, k, v)
        db.commit()

    insights = get_daily_insights(db, drink.date)
    return {
        "status": "success",
        "nutrition_result": nutrition_result_payload(enriched_drink),
        "agent_analysis": insights
    }


def log_sleep(db, sleep) -> Dict[str, str]:
    db_sleep = db.query(SleepRecord).filter(SleepRecord.date == sleep.date).first()
    if db_sleep:
        db_sleep.sleep_hours = sleep.sleep_hours
    else:
        db_sleep = SleepRecord(date=sleep.date, sleep_hours=sleep.sleep_hours)
        db.add(db_sleep)
    db.commit()
    return {"status": "success"}


def get_daily_insights(db, date: str) -> Dict[str, Any]:
    # 纯统计，不再走 LLM
    today_records_db = db.query(DrinkLog).filter(DrinkLog.date == date, DrinkLog.status == 'active').all()
    caffeine_total = sum(r.caffeine or 0 for r in today_records_db)
    sugar_total = sum(r.sugarContent or 0 for r in today_records_db)

    # 简单规则计算 risk_level
    risk_level = "低风险"
    if caffeine_total > 400 or sugar_total > 50:
        risk_level = "高风险"
    elif caffeine_total > 200 or sugar_total > 25:
        risk_level = "中等风险"

    advice = "你好！我是 DrinkMind Companion。今天想喝点什么？"

    # Save the initial insights to chat log if empty
    existing_log = db.query(ChatLog).filter(ChatLog.date == date).first()
    if not existing_log and advice:
        now_str = datetime.datetime.now().isoformat()
        init_log = ChatLog(date=date, role="assistant", content=advice, timestamp=now_str)
        db.add(init_log)
        db.commit()

    return {
        "caffeine_total": caffeine_total,
        "sugar_total": sugar_total,
        "budget_caffeine": 400.0,
        "budget_sugar": 50.0,
        "risk_level": risk_level,
        "advice": advice
    }
