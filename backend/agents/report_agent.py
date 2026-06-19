import json
import os
from collections import defaultdict
from typing import List

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from .llm_config import llm, llm_enabled


CAFFEINE_LIMIT_MG = 400.0
SUGAR_LIMIT_G = 50.0


class InsightItem(BaseModel):
    level: str = Field(description="One of: info, warning, success, danger.")
    icon: str = Field(description="A short icon.")
    title: str = Field(description="Short Simplified Chinese insight title.")
    message: str = Field(description="Concrete Simplified Chinese insight message.")


class ReportOutput(BaseModel):
    insights: List[InsightItem] = Field(description="A list of 1 to 3 report insights.")


def generate_health_report(logs: list, report_type: str) -> dict:
    if not logs:
        return {"insights": []}

    local_report = _generate_local_report(logs, report_type)
    if not llm_enabled():
        return local_report

    prompt = ChatPromptTemplate.from_messages([
        ("system", _build_system_prompt(report_type)),
        ("user", "饮品记录 JSON:\n{logs_text}\n\n统计摘要 JSON:\n{stats_text}\n\n请生成报告。"),
    ])
    payload = {
        "logs_text": json.dumps(_compact_logs(logs), ensure_ascii=False),
        "stats_text": json.dumps(_build_stats(logs), ensure_ascii=False),
    }

    try:
        if _prefer_json_mode():
            report = _generate_report_json(prompt, payload)
        else:
            structured_llm = llm.with_structured_output(ReportOutput, method="function_calling")
            report = (prompt | structured_llm).invoke(payload).dict()
        return _normalize_report(report, logs, report_type)
    except Exception as error:
        print(f"[Report Agent Error] {error}", flush=True)
        return local_report


def generate_report(logs: list, report_type: str) -> dict:
    return generate_health_report(logs, report_type)


def _build_system_prompt(report_type: str) -> str:
    scope = "当天" if report_type == "日度" else "近 7 天"
    return f"""你是 DrinkMind 的饮品摄入分析 Agent。
任务：根据用户的{report_type}饮品记录，生成{scope}咖啡因和糖分分析。

必须遵守：
- 只输出合法 JSON，不要 markdown。
- JSON 顶层必须只有 insights 字段，insights 是对象数组。
- 每个 insight 对象必须包含 level、icon、title、message 四个字段。
- insights 数量 1 到 3 条。
- level 只能是 info、warning、success、danger。
- title 和 message 必须是简体中文。
- 不要空泛夸奖，不要在超标时说“优秀/完美/理想”。

分析要求：
- 必须同时考虑咖啡因总量、糖分总量、饮用时间、饮品类型和主要贡献饮品。
- 如果糖分 > 50g，至少一条 warning/danger 必须明确说糖分超出日建议量。
- 如果咖啡因 > 400mg，至少一条 warning/danger 必须明确说咖啡因超出日建议量。
- 如果没有超标，也要说明距离上限还剩多少，而不是只说“很好”。
- 建议必须具体，例如“下一杯选无糖茶/白水/无糖美式”，不要泛泛说“注意健康”。
"""


def _generate_report_json(prompt: ChatPromptTemplate, payload: dict) -> dict:
    response = (prompt | llm).invoke(payload)
    content = getattr(response, "content", response)
    if isinstance(content, list):
        content = "".join(str(item) for item in content)
    data = json.loads(_strip_json_fence(str(content)))
    if isinstance(data, list):
        data = {"insights": data}
    return ReportOutput(**data).dict()


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").strip()
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start:end + 1]
    return stripped


def _prefer_json_mode() -> bool:
    base_url = os.getenv("BASE_URL", "").lower()
    model_name = os.getenv("MODEL_NAME", "").lower()
    return "dashscope" in base_url or "qwen" in model_name


def _compact_logs(logs: list) -> list:
    keys = ["date", "brand", "name", "type", "sugar", "volume", "startTime", "caffeine", "sugarContent"]
    return [{key: log.get(key) for key in keys} for log in logs]


def _build_stats(logs: list) -> dict:
    caffeine_total = sum(float(log.get("caffeine") or 0) for log in logs)
    sugar_total = sum(float(log.get("sugarContent") or 0) for log in logs)
    dates = sorted({log.get("date") for log in logs if log.get("date")})
    top_caffeine = sorted(logs, key=lambda item: float(item.get("caffeine") or 0), reverse=True)[:3]
    top_sugar = sorted(logs, key=lambda item: float(item.get("sugarContent") or 0), reverse=True)[:3]
    return {
        "caffeine_total_mg": round(caffeine_total, 1),
        "sugar_total_g": round(sugar_total, 1),
        "caffeine_limit_mg": CAFFEINE_LIMIT_MG,
        "sugar_limit_g": SUGAR_LIMIT_G,
        "caffeine_remaining_mg": round(CAFFEINE_LIMIT_MG - caffeine_total, 1),
        "sugar_remaining_g": round(SUGAR_LIMIT_G - sugar_total, 1),
        "record_count": len(logs),
        "active_days": len(dates),
        "top_caffeine_drinks": [_drink_label(log) for log in top_caffeine],
        "top_sugar_drinks": [_drink_label(log) for log in top_sugar],
        "daily_totals": _daily_totals(logs),
    }


def _daily_totals(logs: list) -> list:
    totals = defaultdict(lambda: {"caffeine": 0.0, "sugar": 0.0, "count": 0})
    for log in logs:
        date = log.get("date") or "unknown"
        totals[date]["caffeine"] += float(log.get("caffeine") or 0)
        totals[date]["sugar"] += float(log.get("sugarContent") or 0)
        totals[date]["count"] += 1
    return [
        {
            "date": date,
            "caffeine": round(value["caffeine"], 1),
            "sugar": round(value["sugar"], 1),
            "count": value["count"],
        }
        for date, value in sorted(totals.items())
    ]


def _drink_label(log: dict) -> dict:
    return {
        "date": log.get("date"),
        "name": " ".join(part for part in [log.get("brand"), log.get("name")] if part),
        "time": log.get("startTime"),
        "caffeine": round(float(log.get("caffeine") or 0), 1),
        "sugar": round(float(log.get("sugarContent") or 0), 1),
    }


def _generate_local_report(logs: list, report_type: str) -> dict:
    stats = _build_stats(logs)
    caffeine_total = stats["caffeine_total_mg"]
    sugar_total = stats["sugar_total_g"]
    scope_label = "近 7 天" if _is_weekly_report(report_type, stats) else "今天"
    insights = []

    if sugar_total > SUGAR_LIMIT_G:
        over = sugar_total - SUGAR_LIMIT_G
        top = stats["top_sugar_drinks"][0] if stats["top_sugar_drinks"] else {}
        insights.append({
            "level": "warning",
            "icon": "⚠️",
            "title": "糖分摄入已超过日建议量",
            "message": (
                f"{scope_label}记录糖分约 {sugar_total:.1f}g，比 {SUGAR_LIMIT_G:.0f}g 建议上限高 {over:.1f}g。"
                f"主要贡献饮品包括 {top.get('name') or '当前记录中的高糖饮品'}。后续建议优先选择无糖茶、白水或无糖美式。"
            ),
        })
    elif sugar_total > SUGAR_LIMIT_G * 0.75:
        insights.append({
            "level": "info",
            "icon": "🍬",
            "title": "糖分接近建议上限",
            "message": f"{scope_label}记录糖分约 {sugar_total:.1f}g，距离 {SUGAR_LIMIT_G:.0f}g 上限还剩 {SUGAR_LIMIT_G - sugar_total:.1f}g。",
        })

    if caffeine_total > CAFFEINE_LIMIT_MG:
        over = caffeine_total - CAFFEINE_LIMIT_MG
        top = stats["top_caffeine_drinks"][0] if stats["top_caffeine_drinks"] else {}
        insights.append({
            "level": "warning",
            "icon": "☕",
            "title": "咖啡因摄入已超过日建议量",
            "message": (
                f"{scope_label}记录咖啡因约 {caffeine_total:.1f}mg，比 {CAFFEINE_LIMIT_MG:.0f}mg 建议上限高 {over:.1f}mg。"
                f"主要贡献饮品包括 {top.get('name') or '当前记录中的高咖啡因饮品'}。接下来建议避免继续摄入含咖啡因饮品。"
            ),
        })
    elif caffeine_total > CAFFEINE_LIMIT_MG * 0.7:
        insights.append({
            "level": "info",
            "icon": "☕",
            "title": "咖啡因摄入需要留意",
            "message": f"{scope_label}记录咖啡因约 {caffeine_total:.1f}mg，仍低于 {CAFFEINE_LIMIT_MG:.0f}mg 上限，但后续饮品可以选择低咖啡因或无咖啡因。",
        })

    if _is_weekly_report(report_type, stats) and stats["active_days"] > 0:
        avg_sugar = sugar_total / stats["active_days"]
        avg_caffeine = caffeine_total / stats["active_days"]
        insights.append({
            "level": "info",
            "icon": "📊",
            "title": "近 7 天摄入节奏",
            "message": f"近 7 天有 {stats['active_days']} 天记录饮品，平均每天约 {avg_caffeine:.1f}mg 咖啡因、{avg_sugar:.1f}g 糖分。",
        })

    if not insights:
        insights.append({
            "level": "success",
            "icon": "✅",
            "title": f"{scope_label}饮品摄入整体平稳",
            "message": f"{scope_label}记录约 {caffeine_total:.1f}mg 咖啡因、{sugar_total:.1f}g 糖分，仍在常用建议范围内。",
        })

    return {"insights": insights[:3]}


def _is_weekly_report(report_type: str, stats: dict) -> bool:
    return report_type == "周度" or stats.get("active_days", 0) > 1


def _normalize_report(report: dict, logs: list, report_type: str) -> dict:
    insights = report.get("insights") if isinstance(report, dict) else []
    if not isinstance(insights, list):
        insights = []

    level_map = {
        "positive": "success",
        "gentle_reminder": "info",
        "reminder": "info",
        "caution": "warning",
        "alert": "warning",
    }
    normalized = []
    for item in insights:
        if not isinstance(item, dict):
            continue
        item = dict(item)
        item["level"] = level_map.get(str(item.get("level", "")).strip(), item.get("level", "info"))
        if item["level"] not in {"info", "warning", "success", "danger"}:
            item["level"] = "info"
        normalized.append(item)

    guarded = _generate_local_report(logs, report_type)["insights"]
    for guarded_item in reversed([item for item in guarded if item.get("level") in {"warning", "danger"}]):
        keyword = "糖" if "糖" in guarded_item.get("title", "") else "咖啡因"
        has_warning = any(
            item.get("level") in {"warning", "danger"}
            and keyword in f"{item.get('title', '')} {item.get('message', '')}"
            for item in normalized
        )
        if not has_warning:
            normalized.insert(0, guarded_item)

    if not normalized:
        normalized = guarded
    return {"insights": normalized[:3]}
