import datetime
import hashlib
import json

from agents.report_agent import generate_health_report
from db.database import DrinkLog, ReportCache


REPORT_CACHE_VERSION = "report-v2-weekly-daily-average"

SIGNATURE_FIELDS = [
    "id",
    "date",
    "brand",
    "name",
    "type",
    "sugar",
    "volume",
    "startTime",
    "endTime",
    "caffeine",
    "sugarContent",
    "status",
]


def serialize_drink_log(log: DrinkLog) -> dict:
    return {column.name: getattr(log, column.name) for column in log.__table__.columns}


def get_daily_report(db, date: str) -> dict:
    records = db.query(DrinkLog).filter(
        DrinkLog.date == date,
        DrinkLog.status == "active",
    ).all()
    logs = [serialize_drink_log(record) for record in records]
    return get_report_with_cache(db, "daily", date, logs)


def get_weekly_report(db, date: str) -> dict:
    try:
        end_date = datetime.datetime.strptime(date, "%Y-%m-%d")
        start_date = end_date - datetime.timedelta(days=6)
        start_str = start_date.strftime("%Y-%m-%d")
        records = db.query(DrinkLog).filter(
            DrinkLog.date >= start_str,
            DrinkLog.date <= date,
            DrinkLog.status == "active",
        ).all()
        logs = [serialize_drink_log(record) for record in records]
        return get_report_with_cache(db, "weekly", date, logs)
    except Exception:
        return {"insights": []}


def get_report_with_cache(db, report_type: str, date: str, logs: list[dict]) -> dict:
    ensure_report_cache_table(db)
    logs_signature = build_logs_signature(logs)

    cached = db.query(ReportCache).filter(
        ReportCache.report_type == report_type,
        ReportCache.date == date,
        ReportCache.logs_signature == logs_signature,
    ).first()
    if cached:
        try:
            return json.loads(cached.result_json)
        except (TypeError, json.JSONDecodeError):
            db.delete(cached)
            db.commit()

    result = generate_health_report(logs, report_type)
    save_report_cache(db, report_type, date, logs_signature, result)
    return result


def ensure_report_cache_table(db) -> None:
    ReportCache.__table__.create(bind=db.get_bind(), checkfirst=True)


def save_report_cache(db, report_type: str, date: str, logs_signature: str, result: dict) -> None:
    now = datetime.datetime.now().isoformat()
    cache_id = f"{report_type}:{date}:{logs_signature[:16]}"
    existing = db.query(ReportCache).filter(ReportCache.id == cache_id).first()
    payload = json.dumps(result, ensure_ascii=False)

    if existing:
        existing.result_json = payload
        existing.updated_at = now
    else:
        db.add(ReportCache(
            id=cache_id,
            report_type=report_type,
            date=date,
            logs_signature=logs_signature,
            result_json=payload,
            created_at=now,
            updated_at=now,
        ))
    db.commit()


def build_logs_signature(logs: list[dict]) -> str:
    signature_payload = [{"cache_version": REPORT_CACHE_VERSION}]
    for log in logs:
        signature_payload.append({
            field: normalize_signature_value(log.get(field))
            for field in SIGNATURE_FIELDS
        })
    signature_payload.sort(key=lambda item: str(item.get("id") or ""))
    encoded = json.dumps(
        signature_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_signature_value(value):
    if isinstance(value, float):
        return round(value, 4)
    return value
