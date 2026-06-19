"""Optional LLM-assisted beverage composition decomposition.

The LLM is only allowed to infer a normalized ingredient structure. Nutrition
numbers are still calculated by ingredient rules in composition_agent.py.
"""

from __future__ import annotations

import json
import os
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from agents.llm_config import env_truthy, llm


COMPLEX_DRINK_MARKERS = [
    "杨枝甘露",
    "芒果甘露",
    "芒果西米",
    "西米露",
    "mango sago",
    "多肉",
    "芝芝",
    "奶盖",
    "厚乳",
    "厚椰",
    "麻薯",
    "芋泥",
    "小料",
    "波波",
    "珍珠",
]


class LLMCompositionResult(BaseModel):
    drink_type: str = Field(
        default="unknown",
        description=(
            "Normalized style. Prefer one of: americano, latte, coconut_latte, "
            "oat_latte, milk_tea, fruit_tea, fruit_americano, coconut_americano, "
            "mango_coconut_drink, unknown."
        ),
    )
    coffee_base: str | None = None
    espresso_shots: float | None = None
    tea_base: str | None = None
    tea_base_ratio: float | None = Field(default=None, description="0-1 share of cup volume")
    milk_base: str | None = None
    milk_ratio: float | None = Field(default=None, description="0-1 share of cup volume")
    fruit_base: str | None = None
    fruit_ratio: float | None = Field(default=None, description="0-1 share of cup volume")
    syrup_pumps: float | None = None
    natural_sugar_sources: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    uncertainty_drivers: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.55, ge=0.0, le=1.0)


def should_try_llm_decomposition(drink: dict, rule_composition: dict) -> bool:
    """Return whether the optional LLM decomposer should run."""
    if not composition_llm_enabled():
        return False

    text = _drink_text(drink)
    confidence = _safe_float(rule_composition.get("confidence"), default=0.0)
    if confidence < 0.65:
        return True
    return any(marker.lower() in text for marker in COMPLEX_DRINK_MARKERS)


def composition_llm_enabled() -> bool:
    """Composition-specific LLM gate.

    This intentionally does not require ENABLE_LLM=true because the general LLM
    switch also enables chat/report paths. Composition can be tested separately.
    """
    if env_truthy("DRINKMIND_OFFLINE"):
        return False
    if not env_truthy("ENABLE_LLM_COMPOSITION"):
        return False
    api_key = os.getenv("OPENAI_API_KEY", "")
    return bool(api_key and not api_key.startswith("dummy_"))


def decompose_with_optional_llm(drink: dict, rule_composition: dict) -> dict:
    """Use LLM output to refine a rule-based composition when enabled."""
    if not should_try_llm_decomposition(drink, rule_composition):
        return rule_composition

    result = _call_llm_decomposer(drink, rule_composition)
    return _merge_llm_composition(rule_composition, result)


def _call_llm_decomposer(drink: dict, rule_composition: dict) -> LLMCompositionResult:
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            (
                "你是 DrinkMind 成分拆解器。根据饮品名称、类型、容量和甜度推断可能的饮品组成。"
                "只返回结构化字段，不要估算咖啡因或糖分数值。"
                "assumptions、warnings、uncertainty_drivers 必须使用简体中文。"
                "drink_type、coffee_base、tea_base、milk_base、fruit_base 等枚举字段可以保留英文代码值。"
                "请保守推断，并说明不确定性。"
                "把成分映射到已知类别：espresso、tea_base、milk_base、fruit_base、added_syrup。"
                "小料或固体配料只放进中文提醒/不确定性，不要编造营养数值。"
            ),
        ),
        (
            "user",
            (
                "Drink: brand={brand}, name={name}, type={type}, volume={volume}ml, "
                "sweetness={sugar}. Rule composition: {rule_summary}"
            ),
        ),
    ])
    payload = {
        "brand": drink.get("brand") or "",
        "name": drink.get("name") or "",
        "type": drink.get("type") or "",
        "volume": drink.get("volume") or "",
        "sugar": drink.get("sugar") or "",
        "rule_summary": {
            "drink_type": rule_composition.get("drink_type"),
            "confidence": rule_composition.get("confidence"),
            "assumptions": rule_composition.get("assumptions"),
            "warnings": rule_composition.get("warnings"),
        },
    }
    if _prefer_json_mode():
        return _call_llm_json_fallback(drink, rule_composition)

    try:
        structured_llm = llm.with_structured_output(LLMCompositionResult, method="function_calling")
        return (prompt | structured_llm).invoke(payload)
    except Exception:
        return _call_llm_json_fallback(drink, rule_composition)


def _call_llm_json_fallback(drink: dict, rule_composition: dict) -> LLMCompositionResult:
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            (
                "你是 DrinkMind 成分拆解器。只返回合法 JSON，不要包裹 markdown。"
                "不要估算咖啡因或糖分数值。"
                "assumptions、warnings、uncertainty_drivers 必须使用简体中文。"
                "drink_type、coffee_base、tea_base、milk_base、fruit_base 等枚举字段可以保留英文代码值。"
                "允许的 keys: drink_type, coffee_base, espresso_shots, tea_base, "
                "tea_base_ratio, milk_base, milk_ratio, fruit_base, fruit_ratio, "
                "syrup_pumps, natural_sugar_sources, assumptions, warnings, "
                "uncertainty_drivers, confidence."
            ),
        ),
        (
            "user",
            (
                "请推断这杯饮品的组成。中文字段请用简体中文。"
                "Drink JSON: {drink_json}. Rule composition JSON: {rule_json}"
            ),
        ),
    ])
    response = (prompt | llm).invoke({
        "drink_json": json.dumps(drink, ensure_ascii=False),
        "rule_json": json.dumps({
            "drink_type": rule_composition.get("drink_type"),
            "confidence": rule_composition.get("confidence"),
            "assumptions": rule_composition.get("assumptions"),
            "warnings": rule_composition.get("warnings"),
        }, ensure_ascii=False),
    })
    content = getattr(response, "content", response)
    if isinstance(content, list):
        content = "".join(str(item) for item in content)
    data = json.loads(_strip_json_fence(str(content)))
    return LLMCompositionResult(**data)


def _merge_llm_composition(rule_composition: dict, result: LLMCompositionResult) -> dict:
    composition = dict(rule_composition)
    volume = _safe_float((composition.get("input") or {}).get("volume"), default=500.0)

    if result.drink_type:
        composition["drink_type"] = result.drink_type
    if result.coffee_base:
        composition["coffee_base"] = result.coffee_base
    if result.espresso_shots is not None:
        composition["espresso_shots"] = _clamp(result.espresso_shots, 0.0, 4.0)
    if result.tea_base:
        composition["tea_base"] = result.tea_base
    if result.tea_base_ratio is not None:
        composition["tea_base_volume_ml"] = round(volume * _clamp(result.tea_base_ratio, 0.0, 1.0), 1)
    if result.milk_base:
        composition["milk_base"] = result.milk_base
    if result.milk_ratio is not None:
        composition["milk_volume_ml"] = round(volume * _clamp(result.milk_ratio, 0.0, 1.0), 1)
    if result.fruit_base:
        composition["fruit_base"] = result.fruit_base
    if result.fruit_ratio is not None:
        composition["fruit_base_volume_ml"] = round(volume * _clamp(result.fruit_ratio, 0.0, 1.0), 1)
    if result.syrup_pumps is not None:
        composition["syrup_pumps"] = _clamp(result.syrup_pumps, 0.0, 8.0)

    composition["natural_sugar_sources"] = _dedupe(
        list(composition.get("natural_sugar_sources") or []) + result.natural_sugar_sources
    )
    composition["assumptions"] = _dedupe(
        list(composition.get("assumptions") or []) + result.assumptions
    )
    composition["warnings"] = _dedupe(
        list(composition.get("warnings") or []) + result.warnings
    )
    composition["uncertainty_drivers"] = _dedupe(
        list(composition.get("uncertainty_drivers") or []) + result.uncertainty_drivers
    )
    composition["confidence"] = round(min(_safe_float(composition.get("confidence"), 0.5), result.confidence), 2)
    composition["decomposition_source"] = "llm_assisted"
    composition["llm_decomposition_used"] = True
    return composition


def _drink_text(drink: dict) -> str:
    return f"{drink.get('brand') or ''} {drink.get('name') or ''} {drink.get('type') or ''}".lower()


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(float(value), high))


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


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
    if "dashscope" in base_url or "qwen" in model_name:
        return True
    return env_truthy("LLM_COMPOSITION_JSON_MODE")
