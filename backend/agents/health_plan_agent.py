import datetime
import json
import uuid

from database import DrinkLog, HealthPlan


def infer_plan_target(user_message: str) -> str:
    if any(word in user_message for word in ["糖", "奶茶", "控糖", "少糖"]):
        return "reduce_sugar"
    if any(word in user_message for word in ["咖啡因", "咖啡", "睡眠", "睡不着"]):
        return "reduce_caffeine"
    if any(word in user_message for word in ["考试", "加班"]):
        return "work_week_strategy"
    return "balanced_drink_routine"


def build_plan_days(target: str) -> list[dict]:
    templates = {
        "reduce_sugar": [
            "记录今天所有含糖饮品，建立基线。",
            "把最甜的一杯降到七分糖或半糖。",
            "选择一杯无额外加糖的咖啡或茶。",
            "把奶茶替换为三分糖或无糖茶饮。",
            "晚间避免高糖饮品，减少睡前波动。",
            "复盘本周最高糖分来源，准备替代选择。",
            "保持低糖选择，并总结最容易坚持的一种搭配。",
        ],
        "reduce_caffeine": [
            "记录今天咖啡因摄入和饮用时间。",
            "下午 3 点后避免高咖啡因饮品。",
            "把一杯咖啡替换为低因或茶饮。",
            "控制单杯咖啡因，优先小杯。",
            "如果睡眠不足，选择无咖啡因饮品。",
            "复盘最晚一杯咖啡对睡眠的影响。",
            "形成适合自己的咖啡因截止时间。",
        ],
        "work_week_strategy": [
            "为高强度日建立饮品预算。",
            "上午保留主要咖啡因摄入。",
            "下午改用低糖茶饮或气泡水。",
            "避免用高糖饮品补疲劳。",
            "记录睡眠和第二天精神状态。",
            "为考试或加班前一天降低晚间咖啡因。",
            "总结最稳定的提神组合。",
        ],
        "balanced_drink_routine": [
            "记录今天所有饮品。",
            "控制含糖饮品总量。",
            "下午减少高咖啡因选择。",
            "尝试一杯低糖替代饮品。",
            "关注睡眠和疲劳变化。",
            "复盘本周最常见饮品。",
            "保留最容易坚持的健康选择。",
        ],
    }
    suggestions = templates.get(target, templates["balanced_drink_routine"])
    return [
        {
            "day": index + 1,
            "goal": target,
            "suggestion": suggestion,
            "status": "pending",
        }
        for index, suggestion in enumerate(suggestions)
    ]


def create_health_plan(db, user_message: str, start_date: str) -> HealthPlan:
    target = infer_plan_target(user_message)
    plan = HealthPlan(
        id=f"plan_{uuid.uuid4().hex[:10]}",
        target=target,
        status="active",
        total_days=7,
        current_day=1,
        start_date=start_date,
        plan_content=json.dumps(build_plan_days(target), ensure_ascii=False),
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def serialize_plan(plan: HealthPlan | None) -> dict | None:
    if not plan:
        return None
    try:
        content = json.loads(plan.plan_content or "[]")
    except Exception:
        content = []
    return {
        "id": plan.id,
        "target": plan.target,
        "status": plan.status,
        "total_days": plan.total_days,
        "current_day": plan.current_day,
        "start_date": plan.start_date,
        "plan_content": content,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
    }


def get_active_plan(db) -> HealthPlan | None:
    return db.query(HealthPlan).filter(HealthPlan.status == "active").order_by(HealthPlan.created_at.desc()).first()


def update_plan_progress(db, plan: HealthPlan | None, current_date: str) -> dict | None:
    if not plan:
        return None
    try:
        start = datetime.datetime.strptime(plan.start_date, "%Y-%m-%d").date()
        today = datetime.datetime.strptime(current_date, "%Y-%m-%d").date()
    except Exception:
        return serialize_plan(plan)

    day_index = max(1, min(((today - start).days + 1), plan.total_days or 7))
    plan.current_day = day_index
    try:
        content = json.loads(plan.plan_content or "[]")
    except Exception:
        content = []

    logs = db.query(DrinkLog).filter(DrinkLog.date >= plan.start_date, DrinkLog.date <= current_date, DrinkLog.status == "active").all()
    for item in content:
        day = item.get("day", 1)
        if day < day_index:
            item["status"] = "completed"
        elif day == day_index:
            item["status"] = "in_progress" if logs else "pending"
        else:
            item["status"] = "pending"

    if day_index >= (plan.total_days or 7):
        plan.status = "completed"
    plan.plan_content = json.dumps(content, ensure_ascii=False)
    plan.updated_at = datetime.datetime.now().isoformat()
    db.commit()
    db.refresh(plan)
    return serialize_plan(plan)


def plan_progress_summary(plan: HealthPlan | None) -> str | None:
    data = serialize_plan(plan)
    if not data:
        return None
    return f"Active plan {data['target']} is on day {data['current_day']} of {data['total_days']}."
