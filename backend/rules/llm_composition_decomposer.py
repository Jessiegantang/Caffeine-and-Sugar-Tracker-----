"""LLM-first beverage composition decomposition.

The LLM only infers a normalized ingredient structure. Caffeine and sugar
numbers are always calculated by ingredient rules in composition_agent.py.
"""

from __future__ import annotations

import json
import os
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from agents.llm_config import env_truthy, llm


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


def decompose_with_llm(drink: dict) -> dict:
    """Infer components with the LLM before any name-based rule decomposition."""
    if not composition_llm_enabled():
        raise RuntimeError("LLM composition decomposition is disabled")

    result = _call_llm_decomposer(drink)
    composition = _build_llm_composition(drink, result)
    _validate_llm_composition(composition)
    return composition


def _call_llm_decomposer(drink: dict) -> LLMCompositionResult:
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
                "设置某个液体基底时必须同时给出对应 ratio，所有 ratio 为 0-1 且总和不得超过 1。"
                "含咖啡时必须给出 espresso_shots；不含咖啡时必须为 0。"
                "小料或固体配料只放进中文提醒/不确定性，不要编造营养数值。"
            ),
        ),
        (
            "user",
            (
                "Drink: brand={brand}, name={name}, user_selected_type={type}, "
                "volume={volume}ml, sweetness={sugar}. "
                "Treat user_selected_type as authoritative unless the name contains explicit contradictory evidence."
            ),
        ),
    ])
    payload = {
        "brand": drink.get("brand") or "",
        "name": drink.get("name") or "",
        "type": drink.get("type") or "",
        "volume": drink.get("volume") or "",
        "sugar": drink.get("sugar") or "",
    }
    if _prefer_json_mode():
        return _call_llm_json_fallback(drink)

    try:
        structured_llm = llm.with_structured_output(LLMCompositionResult, method="function_calling")
        return (prompt | structured_llm).invoke(payload)
    except Exception:
        return _call_llm_json_fallback(drink)


def _call_llm_json_fallback(drink: dict) -> LLMCompositionResult:
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            (
                "你是 DrinkMind 成分拆解器。只返回合法 JSON，不要包裹 markdown。"
                "不要估算咖啡因或糖分数值。"
                "assumptions、warnings、uncertainty_drivers 必须使用简体中文。"
                "drink_type、coffee_base、tea_base、milk_base、fruit_base 等枚举字段可以保留英文代码值。"
                "设置某个液体基底时必须同时给出对应 ratio，所有 ratio 为 0-1 且总和不得超过 1。"
                "含咖啡时必须给出 espresso_shots；不含咖啡时必须为 0。"
                "允许的 keys: drink_type, coffee_base, espresso_shots, tea_base, "
                "tea_base_ratio, milk_base, milk_ratio, fruit_base, fruit_ratio, "
                "syrup_pumps, natural_sugar_sources, assumptions, warnings, "
                "uncertainty_drivers."
            ),
        ),
        (
            "user",
            (
                "请推断这杯饮品的组成。中文字段请用简体中文。"
                "用户选择的 type 应视为权威输入，除非名称中有明确矛盾证据。"
                "Drink JSON: {drink_json}."
            ),
        ),
    ])
    response = (prompt | llm).invoke({
        "drink_json": json.dumps(drink, ensure_ascii=False),
    })
    content = getattr(response, "content", response)
    if isinstance(content, list):
        content = "".join(str(item) for item in content)
    data = json.loads(_strip_json_fence(str(content)))
    return LLMCompositionResult(**data)


def _build_llm_composition(drink: dict, result: LLMCompositionResult) -> dict:
    volume = _safe_float(drink.get("volume"), default=500.0)
    composition = {
        "drink_type": result.drink_type or "unknown",
        "coffee_base": result.coffee_base,
        "espresso_shots": _clamp(result.espresso_shots or 0.0, 0.0, 4.0),
        "tea_base": result.tea_base,
        "tea_base_volume_ml": 0.0,
        "milk_base": result.milk_base,
        "milk_volume_ml": 0.0,
        "fruit_base": result.fruit_base,
        "fruit_base_volume_ml": 0.0,
        "sweetener_type": "syrup",
        "sweetener_level": str(drink.get("sugar") or "unknown"),
        "syrup_pumps": _clamp(result.syrup_pumps or 0.0, 0.0, 8.0),
        "natural_sugar_sources": _dedupe(result.natural_sugar_sources),
        "assumptions": _dedupe(result.assumptions),
        "warnings": _dedupe(result.warnings),
        "uncertainty_drivers": _dedupe(result.uncertainty_drivers),
        "input": {
            "brand": drink.get("brand") or "",
            "name": drink.get("name") or "",
            "type": drink.get("type") or "",
            "volume": int(volume),
            "sugar": drink.get("sugar"),
        },
        "decomposition_source": "llm_primary",
        "llm_decomposition_used": True,
    }

    if result.tea_base_ratio is not None:
        composition["tea_base_volume_ml"] = round(volume * _clamp(result.tea_base_ratio, 0.0, 1.0), 1)
    if result.milk_ratio is not None:
        composition["milk_volume_ml"] = round(volume * _clamp(result.milk_ratio, 0.0, 1.0), 1)
    if result.fruit_ratio is not None:
        composition["fruit_base_volume_ml"] = round(volume * _clamp(result.fruit_ratio, 0.0, 1.0), 1)
    return composition


def _validate_llm_composition(composition: dict) -> None:
    base_volume_pairs = (
        ("tea_base", "tea_base_volume_ml"),
        ("milk_base", "milk_volume_ml"),
        ("fruit_base", "fruit_base_volume_ml"),
    )
    for base_field, volume_field in base_volume_pairs:
        if composition.get(base_field) and _safe_float(composition.get(volume_field), 0.0) <= 0:
            raise ValueError(f"LLM returned {base_field} without a usable ratio")
    if composition.get("coffee_base") and _safe_float(composition.get("espresso_shots"), 0.0) <= 0:
        raise ValueError("LLM returned a coffee base without espresso shots")

    input_volume = _safe_float((composition.get("input") or {}).get("volume"), 500.0)
    liquid_volume = sum(
        _safe_float(composition.get(volume_field), 0.0)
        for _, volume_field in base_volume_pairs
    )
    if liquid_volume > input_volume * 1.01:
        raise ValueError("LLM component ratios exceed the drink volume")

    quantified = any(
        _safe_float(composition.get(field), 0.0) > 0
        for field in (
            "espresso_shots",
            "tea_base_volume_ml",
            "milk_volume_ml",
            "fruit_base_volume_ml",
            "syrup_pumps",
        )
    )
    if composition.get("drink_type") == "unknown" or not quantified:
        raise ValueError("LLM returned no usable quantified beverage composition")


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
