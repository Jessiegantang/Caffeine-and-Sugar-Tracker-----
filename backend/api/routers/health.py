import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.schemas import HealthPlanInput
from agents.health_plan_agent import (
    create_health_plan,
    get_active_plan,
    plan_progress_summary,
    serialize_plan,
    update_plan_progress,
)
from agents.report_agent import generate_health_report
from database import DrinkLog, get_db
from services.drink_log_service import get_daily_insights as get_daily_insights_service


router = APIRouter()


@router.get("/api/agent/daily_insights")
def get_daily_insights(date: str, db: Session = Depends(get_db)):
    return get_daily_insights_service(db, date)


@router.post("/api/health/plans")
def create_plan(input_data: HealthPlanInput, db: Session = Depends(get_db)):
    plan = create_health_plan(db, input_data.goal, input_data.date)
    return {"status": "success", "plan": serialize_plan(plan)}


@router.get("/api/health/plans/active")
def get_active_health_plan(db: Session = Depends(get_db)):
    return {"status": "success", "plan": serialize_plan(get_active_plan(db))}


@router.post("/api/health/plans/active/progress")
def refresh_active_health_plan(date: str, db: Session = Depends(get_db)):
    plan = update_plan_progress(db, get_active_plan(db), date)
    return {"status": "success", "plan": plan}


@router.get("/api/agent/reports/daily")
def get_daily_report(date: str, db: Session = Depends(get_db)):
    today_records_db = db.query(DrinkLog).filter(DrinkLog.date == date, DrinkLog.status == 'active').all()
    logs = [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in today_records_db]
    report = generate_health_report(logs, "日度")
    return report


@router.get("/api/agent/reports/weekly")
def get_weekly_report(date: str, db: Session = Depends(get_db)):
    try:
        end_date = datetime.datetime.strptime(date, "%Y-%m-%d")
        start_date = end_date - datetime.timedelta(days=6)
        start_str = start_date.strftime("%Y-%m-%d")
        records_db = db.query(DrinkLog).filter(DrinkLog.date >= start_str, DrinkLog.date <= date, DrinkLog.status == 'active').all()
        logs = [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in records_db]
        report = generate_health_report(logs, "周度")
        active_plan = get_active_plan(db)
        report["active_plan_progress"] = plan_progress_summary(active_plan)
        return report
    except Exception as e:
        return {"insights": []}
