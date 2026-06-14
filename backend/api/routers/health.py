from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.database import get_db
from services import health_service, report_service


router = APIRouter()


@router.get("/api/agent/daily_insights")
def get_daily_insights(date: str, db: Session = Depends(get_db)):
    return health_service.get_daily_insights(db, date)


@router.get("/api/agent/reports/daily")
def get_daily_report(date: str, db: Session = Depends(get_db)):
    return report_service.get_daily_report(db, date)


@router.get("/api/agent/reports/weekly")
def get_weekly_report(date: str, db: Session = Depends(get_db)):
    return report_service.get_weekly_report(db, date)
