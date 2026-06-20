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
    if _is_weekly_report_type(report_type):
        scope_rules = (
            "这是周度报告。不要把 7 天总摄入量直接和单日建议上限比较。"
            "你必须优先判断 daily_average 与 max_daily。"
            "只有 max_daily_caffeine_mg > 400 时，才可以说某一天咖啡因超过单日建议量。"
            "只有 max_daily_sugar_g > 50 时，才可以说某一天糖分超过单日建议量。"
            "weekly_total 只能作为趋势背景，不能写成“本周总量超过日建议量”。"
        )
    else:
        scope_rules = (
            "这是日度报告。可以把当天总咖啡因与 400mg、当天总糖分与 50g 比较。"
        )

    return f"""你是 DrinkMind 的饮品摄入分析 Agent。
任务：根据用户的饮品记录，生成咖啡因和糖分分析。

必须遵守：
- 只输出合法 JSON，不要 markdown。
- JSON 顶层必须只有 insights 字段，insights 是对象数组。
- 每个 insight 对象必须包含 level、icon、title、message 四个字段。
- insights 数量 1 到 3 条。
- level 只能是 info、warning、success、danger。
- title 和 message 必须是简体中文。
- 建议必须具体，不要泛泛地说“注意健康”。

判断规则：
- 单日咖啡因参考上限是 400mg；单日糖分参考上限是 50g。
- {scope_rules}
- 如果没有超标，也要说明距离上限或平均水平，而不是只说“很好”。
- 必须结合主要贡献饮品、饮用时间和饮品类型。
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
    daily_totals = _daily_totals(logs)
    active_days = len(daily_totals)
    top_caffeine = sorted(logs, key=lambda item: float(item.get("caffeine") or 0), reverse=True)[:3]
    top_sugar = sorted(logs, key=lambda item: float(item.get("sugarContent") or 0), reverse=True)[:3]
    max_caffeine_day = max(daily_totals, key=lambda item: item["caffeine"], default=None)
    max_sugar_day = max(daily_totals, key=lambda item: item["sugar"], default=None)

    avg_caffeine = caffeine_total / active_days if active_days else 0.0
    avg_sugar = sugar_total / active_days if active_days else 0.0

    return {
        "caffeine_total_mg": round(caffeine_total, 1),
        "sugar_total_g": round(sugar_total, 1),
        "caffeine_limit_mg": CAFFEINE_LIMIT_MG,
        "sugar_limit_g": SUGAR_LIMIT_G,
        "caffeine_remaining_mg": round(CAFFEINE_LIMIT_MG - caffeine_total, 1),
        "sugar_remaining_g": round(SUGAR_LIMIT_G - sugar_total, 1),
        "daily_average_caffeine_mg": round(avg_caffeine, 1),
        "daily_average_sugar_g": round(avg_sugar, 1),
        "max_daily_caffeine_mg": round((max_caffeine_day or {}).get("caffeine", 0.0), 1),
        "max_daily_caffeine_date": (max_caffeine_day or {}).get("date"),
        "max_daily_sugar_g": round((max_sugar_day or {}).get("sugar", 0.0), 1),
        "max_daily_sugar_date": (max_sugar_day or {}).get("date"),
        "record_count": len(logs),
        "active_days": active_days,
        "top_caffeine_drinks": [_drink_label(log) for log in top_caffeine],
        "top_sugar_drinks": [_drink_label(log) for log in top_sugar],
        "daily_totals": daily_totals,
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
    if _is_weekly_report(report_type, stats):
        return _generate_weekly_local_report(stats)
    return _generate_daily_local_report(stats)


def _generate_daily_local_report(stats: dict) -> dict:
    caffeine_total = stats["caffeine_total_mg"]
    sugar_total = stats["sugar_total_g"]
    insights = []

    if sugar_total > SUGAR_LIMIT_G:
        over = sugar_total - SUGAR_LIMIT_G
        top = stats["top_sugar_drinks"][0] if stats["top_sugar_drinks"] else {}
        insights.append({
            "level": "warning",
            "icon": "⚠️",
            "title": "糖分摄入已超过日建议量",
            "message": (
                f"今天已记录约 {sugar_total:.1f}g 糖分，比 {SUGAR_LIMIT_G:.0f}g 建议上限高 {over:.1f}g。"
                f"主要来源包括 {top.get('name') or '当前记录中的高糖饮品'}，后续饮品建议优先选择无糖茶、无糖美式或白水。"
            ),
        })
    elif sugar_total > SUGAR_LIMIT_G * 0.75:
        insights.append({
            "level": "info",
            "icon": "🍬",
            "title": "糖分接近日建议上限",
            "message": f"今天已记录约 {sugar_total:.1f}g 糖分，距离 {SUGAR_LIMIT_G:.0f}g 上限还剩 {SUGAR_LIMIT_G - sugar_total:.1f}g。",
        })

    if caffeine_total > CAFFEINE_LIMIT_MG:
        over = caffeine_total - CAFFEINE_LIMIT_MG
        top = stats["top_caffeine_drinks"][0] if stats["top_caffeine_drinks"] else {}
        insights.append({
            "level": "warning",
            "icon": "☕",
            "title": "咖啡因摄入已超过日建议量",
            "message": (
                f"今天已记录约 {caffeine_total:.1f}mg 咖啡因，比 {CAFFEINE_LIMIT_MG:.0f}mg 建议上限高 {over:.1f}mg。"
                f"主要来源包括 {top.get('name') or '当前记录中的高咖啡因饮品'}，接下来建议避免继续摄入含咖啡因饮品。"
            ),
        })
    elif caffeine_total > CAFFEINE_LIMIT_MG * 0.7:
        insights.append({
            "level": "info",
            "icon": "☕",
            "title": "咖啡因摄入需要留意",
            "message": f"今天已记录约 {caffeine_total:.1f}mg 咖啡因，仍低于 {CAFFEINE_LIMIT_MG:.0f}mg 上限，但后续饮品可以选择低咖啡因或无咖啡因。",
        })

    if not insights:
        insights.append({
            "level": "success",
            "icon": "✅",
            "title": "今天饮品摄入整体平稳",
            "message": f"今天已记录约 {caffeine_total:.1f}mg 咖啡因、{sugar_total:.1f}g 糖分，仍在常用建议范围内。",
        })

    return {"insights": insights[:3]}


def _generate_weekly_local_report(stats: dict) -> dict:
    active_days = stats["active_days"] or 1
    avg_caffeine = stats["daily_average_caffeine_mg"]
    avg_sugar = stats["daily_average_sugar_g"]
    max_caffeine = stats["max_daily_caffeine_mg"]
    max_sugar = stats["max_daily_sugar_g"]
    insights = []

    if max_sugar > SUGAR_LIMIT_G:
        insights.append({
            "level": "warning",
            "icon": "⚠️",
            "title": "本周有单日糖分超过建议量",
            "message": (
                f"本周记录的 {active_days} 天里，最高单日糖分为 {max_sugar:.1f}g"
                f"（{stats['max_daily_sugar_date'] or '日期未知'}），高于 {SUGAR_LIMIT_G:.0f}g 单日建议量。"
                f"本周记录日均约 {avg_sugar:.1f}g，后续可优先选择无糖茶、无糖美式或不另外加糖。"
            ),
        })
    elif avg_sugar > SUGAR_LIMIT_G * 0.75:
        insights.append({
            "level": "info",
            "icon": "🍬",
            "title": "本周日均糖分偏高",
            "message": f"本周记录日均糖分约 {avg_sugar:.1f}g，接近 {SUGAR_LIMIT_G:.0f}g 单日建议上限，甜饮可以适当减少频率。",
        })

    if max_caffeine > CAFFEINE_LIMIT_MG:
        insights.append({
            "level": "warning",
            "icon": "☕",
            "title": "本周有单日咖啡因超过建议量",
            "message": (
                f"本周记录的 {active_days} 天里，最高单日咖啡因为 {max_caffeine:.1f}mg"
                f"（{stats['max_daily_caffeine_date'] or '日期未知'}），高于 {CAFFEINE_LIMIT_MG:.0f}mg 单日建议量。"
                f"本周记录日均约 {avg_caffeine:.1f}mg，建议把高咖啡因饮品集中在上午，并避免连续叠加。"
            ),
        })
    elif avg_caffeine > CAFFEINE_LIMIT_MG * 0.7:
        insights.append({
            "level": "info",
            "icon": "☕",
            "title": "本周日均咖啡因需要留意",
            "message": f"本周记录日均咖啡因约 {avg_caffeine:.1f}mg，仍低于 {CAFFEINE_LIMIT_MG:.0f}mg 单日上限，但已经接近需要留意的范围。",
        })

    insights.append({
        "level": "info",
        "icon": "📊",
        "title": "本周摄入节奏",
        "message": (
            f"本周共有 {active_days} 天记录饮品，合计约 {stats['caffeine_total_mg']:.1f}mg 咖啡因、"
            f"{stats['sugar_total_g']:.1f}g 糖分；更适合看日均和最高单日，而不是直接用周总量对比单日限量。"
        ),
    })

    return {"insights": insights[:3]}


def _is_weekly_report(report_type: str, stats: dict) -> bool:
    return _is_weekly_report_type(report_type) or stats.get("active_days", 0) > 1


def _is_weekly_report_type(report_type: str) -> bool:
    return report_type in {"weekly", "周度"}


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

    local = _generate_local_report(logs, report_type)["insights"]
    if _is_weekly_report(report_type, _build_stats(logs)):
        normalized = _drop_weekly_total_vs_daily_limit_claims(normalized)

    for local_item in reversed([item for item in local if item.get("level") in {"warning", "danger"}]):
        keyword = "糖" if "糖" in local_item.get("title", "") else "咖啡因"
        has_warning = any(
            item.get("level") in {"warning", "danger"}
            and keyword in f"{item.get('title', '')} {item.get('message', '')}"
            for item in normalized
        )
        if not has_warning:
            normalized.insert(0, local_item)

    if not normalized:
        normalized = local
    return {"insights": normalized[:3]}


def _drop_weekly_total_vs_daily_limit_claims(insights: list[dict]) -> list[dict]:
    cleaned = []
    bad_patterns = [
        "本周咖啡因总摄入",
        "本周糖分总摄入",
        "本周总摄入",
        "周总量超过日建议",
        "总摄入超过日建议",
        "总摄入量超过日建议",
    ]
    for item in insights:
        text = f"{item.get('title', '')} {item.get('message', '')}"
        if any(pattern in text for pattern in bad_patterns):
            continue
        cleaned.append(item)
    return cleaned
