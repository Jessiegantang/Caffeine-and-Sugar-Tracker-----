from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.schemas import HealthPlanInput
from db.database import get_db
from services import health_plan_service, health_service, report_service


router = APIRouter()


@router.get("/api/agent/daily_insights")
def get_daily_insights(date: str, db: Session = Depends(get_db)):
    return health_service.get_daily_insights(db, date)


@router.post("/api/health/plans")
def create_plan(input_data: HealthPlanInput, db: Session = Depends(get_db)):
    return health_plan_service.create_plan(db, input_data)


@router.get("/api/health/plans/active")
def get_active_health_plan(db: Session = Depends(get_db)):
    return health_plan_service.get_active_health_plan(db)


@router.post("/api/health/plans/active/progress")
def refresh_active_health_plan(date: str, db: Session = Depends(get_db)):
    return health_plan_service.refresh_active_health_plan(db, date)


@router.get("/api/agent/reports/daily")
def get_daily_report(date: str, db: Session = Depends(get_db)):
    return report_service.get_daily_report(db, date)


@router.get("/api/agent/reports/weekly")
def get_weekly_report(date: str, db: Session = Depends(get_db)):
    return report_service.get_weekly_report(db, date)
