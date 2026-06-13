from db.database import DrinkLog


def evaluate_daily_risk(date: str, db, draft_drink: dict | None = None) -> dict:
    records = db.query(DrinkLog).filter(
        DrinkLog.date == date,
        DrinkLog.status == "active"
    ).all()
    caffeine_total = sum(record.caffeine or 0 for record in records)
    sugar_total = sum(record.sugarContent or 0 for record in records)

    if draft_drink:
        caffeine_total += draft_drink.get("caffeine") or 0
        sugar_total += draft_drink.get("sugarContent") or 0

    risk_level = "low"
    if caffeine_total > 400 or sugar_total > 50:
        risk_level = "high"
    elif caffeine_total > 200 or sugar_total > 25:
        risk_level = "medium"

    return {
        "caffeine_total": round(caffeine_total, 1),
        "sugar_total": round(sugar_total, 1),
        "budget_caffeine": 400.0,
        "budget_sugar": 50.0,
        "risk_level": risk_level,
    }
