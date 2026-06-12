from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.schemas import DrinkInput, NutritionFeedbackInput, SleepInput
from database import get_db
from services import drink_log_service, nutrition_feedback_service


router = APIRouter()


@router.get("/api/logs")
def get_logs(db: Session = Depends(get_db)):
    return drink_log_service.list_active_logs(db)


@router.post("/api/sync_logs")
def sync_logs(logs: List[DrinkInput], db: Session = Depends(get_db)):
    return drink_log_service.sync_logs(db, logs)


@router.delete("/api/logs/{log_id}")
def delete_log(log_id: str, db: Session = Depends(get_db)):
    if drink_log_service.delete_log(db, log_id):
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Log not found")


@router.post("/api/logs/{log_id}/nutrition_feedback")
def submit_nutrition_feedback(log_id: str, input_data: NutritionFeedbackInput, db: Session = Depends(get_db)):
    return nutrition_feedback_service.submit_nutrition_feedback(db, log_id, input_data)


@router.post("/api/log_drink")
def log_drink(drink: DrinkInput, db: Session = Depends(get_db)):
    return drink_log_service.log_drink(db, drink)


@router.post("/api/sleep")
def log_sleep(sleep: SleepInput, db: Session = Depends(get_db)):
    return drink_log_service.log_sleep(db, sleep)
