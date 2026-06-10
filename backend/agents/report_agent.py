import json
from typing import List

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from .llm_config import llm, llm_enabled


class InsightItem(BaseModel):
    level: str = Field(description="Insight level: info, warning, success, danger.")
    icon: str = Field(description="A suitable short icon or emoji.")
    title: str = Field(description="Short insight title.")
    message: str = Field(description="Warm companion-style insight message.")


class ReportOutput(BaseModel):
    insights: List[InsightItem] = Field(description="A list of 1 to 3 report insights.")


def generate_health_report(logs: list, report_type: str) -> dict:
    if not logs:
        return {"insights": []}
    if not llm_enabled():
        return {"insights": []}

    system_prompt = f"""You are DrinkMind Companion, a warm beverage health companion.
Create a {report_type} intake report from the user's drink logs.

Tone:
- Friendly, calm, and non-judgmental.
- Do not lecture, blame, or sound like a strict fitness coach.

Analyze:
- Caffeine amount and drinking time, especially late-day intake.
- Total sugar intake and whether the user may want to reduce sugar.
- Repeated caffeine use across days, if visible in the provided logs.

Return:
- 1 to 3 core insights.
- Each insight must include level, title, message, and icon.
- Keep the response compatible with the structured output schema."""

    user_prompt = "Recent drink logs:\n{logs_text}\nGenerate the report insights."

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt),
    ])

    structured_llm = llm.with_structured_output(ReportOutput, method="function_calling")
    chain = prompt | structured_llm

    result = chain.invoke({"logs_text": json.dumps(logs, ensure_ascii=False)})
    return result.dict()


def generate_report(logs: list, report_type: str) -> dict:
    return generate_health_report(logs, report_type)
