from services.drink_log_service import get_daily_insights as get_daily_insights_service


def get_daily_insights(db, date: str) -> dict:
    return get_daily_insights_service(db, date)
