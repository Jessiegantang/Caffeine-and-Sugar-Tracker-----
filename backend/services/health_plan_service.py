from agents.health_plan_agent import (
    create_health_plan,
    get_active_plan,
    serialize_plan,
    update_plan_progress,
)


def create_plan(db, input_data) -> dict:
    plan = create_health_plan(db, input_data.goal, input_data.date)
    return {"status": "success", "plan": serialize_plan(plan)}


def get_active_health_plan(db) -> dict:
    return {"status": "success", "plan": serialize_plan(get_active_plan(db))}


def refresh_active_health_plan(db, date: str) -> dict:
    plan = update_plan_progress(db, get_active_plan(db), date)
    return {"status": "success", "plan": plan}
