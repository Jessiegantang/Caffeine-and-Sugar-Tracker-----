import json
import os
from typing import List

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from .llm_config import llm, llm_enabled


class InsightItem(BaseModel):
    level: str = Field(description="Insight level: info, warning, success, danger.")
    icon: str = Field(description="A suitable short icon or emoji.")
    title: str = Field(description="Short Chinese insight title. Must be Chinese only.")
    message: str = Field(description="Warm Chinese companion-style insight message. Must be Chinese only.")


class ReportOutput(BaseModel):
    insights: List[InsightItem] = Field(description="A list of 1 to 3 report insights.")


def generate_health_report(logs: list, report_type: str) -> dict:
    if not logs:
        return {"insights": []}
    if not llm_enabled():
        return _generate_local_report(logs, report_type)

    system_prompt = f"""你是 DrinkMind Companion，一个温和、克制的饮品健康分析助手。
请根据用户的饮品记录生成{report_type}摄入分析报告。

语言要求：
- 必须只使用简体中文。
- title 和 message 都不要出现英文。
- 不要同时输出英文和中文两套内容。
- 饮品名可以保留用户原文，但解释、建议、标题必须是中文。

Tone:
- 友好、平静、不评判。
- 不要说教，不要像严格健身教练。

分析重点：
- 咖啡因摄入量和饮用时间，尤其是偏晚摄入。
- 糖分摄入量，以及是否需要温和提醒。
- 如果记录中看得出来，可观察多日重复摄入习惯。

返回要求：
- 返回 1 到 3 条核心 insight。
- 每条 insight 必须包含 level、title、message、icon。
- 严格兼容 structured output schema。"""

    user_prompt = "最近饮品记录：\n{logs_text}\n请只用简体中文生成分析报告 insights。"

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt),
    ])

    if _prefer_json_mode():
        try:
            return _normalize_report(_generate_report_json(prompt, logs), logs, report_type)
        except Exception as fallback_error:
            print(f"[Report Agent JSON Error] {fallback_error}", flush=True)
            return _generate_local_report(logs, report_type)

    try:
        structured_llm = llm.with_structured_output(ReportOutput, method="function_calling")
        chain = prompt | structured_llm
        result = chain.invoke({"logs_text": json.dumps(logs, ensure_ascii=False)})
        return _normalize_report(result.dict(), logs, report_type)
    except Exception as e:
        print(f"[Report Agent Error] {e}", flush=True)
        try:
            return _normalize_report(_generate_report_json(prompt, logs), logs, report_type)
        except Exception as fallback_error:
            print(f"[Report Agent JSON Fallback Error] {fallback_error}", flush=True)
            return _generate_local_report(logs, report_type)


def generate_report(logs: list, report_type: str) -> dict:
    return generate_health_report(logs, report_type)


def _generate_report_json(prompt: ChatPromptTemplate, logs: list) -> dict:
    response = (prompt | llm).invoke({"logs_text": json.dumps(logs, ensure_ascii=False)})
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
    return stripped


def _prefer_json_mode() -> bool:
    base_url = os.getenv("BASE_URL", "").lower()
    model_name = os.getenv("MODEL_NAME", "").lower()
    return "dashscope" in base_url or "qwen" in model_name


def _generate_local_report(logs: list, report_type: str) -> dict:
    caffeine_total = sum(float(log.get("caffeine") or 0) for log in logs)
    sugar_total = sum(float(log.get("sugarContent") or 0) for log in logs)
    insights = []

    if sugar_total > 50:
        insights.append({
            "level": "warning",
            "icon": "⚠️",
            "title": "糖分摄入已超过日建议量",
            "message": f"今天已记录约 {sugar_total:.1f}g 糖分，高于 50g 的日建议限量。后续饮品建议优先选择无糖茶、无糖美式或白水。"
        })
    elif sugar_total > 35:
        insights.append({
            "level": "info",
            "icon": "🍬",
            "title": "糖分接近上限",
            "message": f"今天糖分约 {sugar_total:.1f}g，已经接近日建议上限。后续可以尽量选择少糖或无糖。"
        })

    if caffeine_total > 400:
        insights.append({
            "level": "warning",
            "icon": "☕",
            "title": "咖啡因摄入已超过日建议量",
            "message": f"今天已记录约 {caffeine_total:.1f}mg 咖啡因，高于 400mg 的日建议限量。接下来建议避免继续摄入含咖啡因饮品。"
        })
    elif caffeine_total > 250:
        insights.append({
            "level": "info",
            "icon": "☕",
            "title": "咖啡因摄入需要留意",
            "message": f"今天咖啡因约 {caffeine_total:.1f}mg，仍在 400mg 以内，但如果已经接近下午或晚上，后续建议选择低咖啡因饮品。"
        })

    if not insights:
        insights.append({
            "level": "success",
            "icon": "✅",
            "title": f"{report_type}饮品摄入整体平稳",
            "message": f"当前记录约 {caffeine_total:.1f}mg 咖啡因、{sugar_total:.1f}g 糖分，仍在常用日建议范围内。"
        })

    return {"insights": insights[:3]}


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
    high_risk_items = [
        item for item in guarded
        if item.get("level") in {"warning", "danger"}
    ]
    if high_risk_items:
        existing_text = " ".join(
            f"{item.get('title', '')} {item.get('message', '')}" for item in normalized
        )
        for item in reversed(high_risk_items):
            keyword = "糖" if "糖" in item.get("title", "") else "咖啡因"
            if keyword not in existing_text or not any(
                insight.get("level") in {"warning", "danger"} and keyword in f"{insight.get('title', '')} {insight.get('message', '')}"
                for insight in normalized
            ):
                normalized.insert(0, item)

    if not normalized:
        normalized = guarded
    return {"insights": normalized[:3]}
