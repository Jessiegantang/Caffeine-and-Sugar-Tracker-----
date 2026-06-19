import datetime

from agents.report_agent import generate_health_report
from db.database import DrinkLog


def serialize_drink_log(log: DrinkLog) -> dict:
    return {column.name: getattr(log, column.name) for column in log.__table__.columns}


def get_daily_report(db, date: str) -> dict:
    today_records_db = db.query(DrinkLog).filter(
        DrinkLog.date == date,
        DrinkLog.status == "active",
    ).all()
    logs = [serialize_drink_log(record) for record in today_records_db]
    return generate_health_report(logs, "日度")


def get_weekly_report(db, date: str) -> dict:
    try:
        end_date = datetime.datetime.strptime(date, "%Y-%m-%d")
        start_date = end_date - datetime.timedelta(days=6)
        start_str = start_date.strftime("%Y-%m-%d")
        records_db = db.query(DrinkLog).filter(
            DrinkLog.date >= start_str,
            DrinkLog.date <= date,
            DrinkLog.status == "active",
        ).all()
        logs = [serialize_drink_log(record) for record in records_db]
        return generate_health_report(logs, "周度")
    except Exception:
        return {"insights": []}
