"""Deterministic beverage composition estimator.

This module is intentionally independent from the current nutrition pipeline.
It does not call LLMs, does not read/write the database, and returns a result
shape compatible with existing nutrition estimation responses.
"""

from __future__ import annotations

from typing import Any


ESPRESSO_CAFFEINE_MG = 70.0
ESPRESSO_SHOT_ML = 30.0
MILK_SUGAR_G_PER_100ML = 5.0
COCONUT_MILK_SUGAR_G_PER_100ML = 8.0
OAT_MILK_SUGAR_G_PER_100ML = 4.5
MILK_TEA_CAFFEINE_MG_PER_100ML = 25.0
FRUIT_TEA_CAFFEINE_MG_PER_100ML = 8.0
FRUIT_BASE_SUGAR_G_PER_100ML = 9.0
SYRUP_SUGAR_G_PER_PUMP = 6.0

SWEETNESS_MULTIPLIERS = {
    "none": 0.0,
    "three": 0.3,
    "half": 0.5,
    "seven": 0.7,
    "full": 1.0,
    "unknown": 0.5,
}

SUGAR_ALIASES = {
    "none": ["none", "no", "zero", "sugar-free", "sugar free", "unsweetened", "0", "0%", "无糖", "不加糖", "零糖"],
    "three": ["three", "3", "30%", "三分糖", "3分糖", "少糖"],
    "half": ["half", "50%", "半糖", "五分糖", "5分糖"],
    "seven": ["seven", "70%", "七分糖", "7分糖"],
    "full": ["full", "100%", "regular", "normal", "全糖", "正常糖", "满糖"],
}


def decompose_drink(drink: dict) -> dict:
    """Infer a structured composition from a drink dictionary."""
    brand = str(drink.get("brand") or "").strip()
    name = str(drink.get("name") or "").strip()
    raw_type = str(drink.get("type") or "").strip().lower()
    volume = _safe_volume(drink.get("volume"))
    text = f"{brand} {name} {raw_type}".lower()
    sugar_level = _normalize_sugar_level(drink.get("sugar"))

    drink_type = _infer_drink_type(text, raw_type)
    assumptions: list[str] = []
    warnings: list[str] = []
    natural_sources: list[str] = []

    composition: dict[str, Any] = {
        "drink_type": drink_type,
        "coffee_base": None,
        "espresso_shots": 0.0,
        "tea_base": None,
        "tea_base_volume_ml": 0.0,
        "milk_base": None,
        "milk_volume_ml": 0.0,
        "fruit_base": None,
        "fruit_base_volume_ml": 0.0,
        "sweetener_type": "syrup",
        "sweetener_level": sugar_level,
        "syrup_pumps": 0.0,
        "natural_sugar_sources": natural_sources,
        "assumptions": assumptions,
        "warnings": warnings,
        "confidence": 0.75,
        "input": {
            "brand": brand,
            "name": name,
            "type": raw_type,
            "volume": volume,
            "sugar": drink.get("sugar"),
        },
    }

    if sugar_level == "unknown":
        warnings.append("Sweetness level is unknown; using half-sugar added sweetener assumption.")
        composition["confidence"] -= 0.12

    if drink_type == "coconut_latte":
        shots = _coffee_shots(volume, style="milk")
        milk_ml = _remaining_milk_volume(volume, shots, fill_ratio=0.72)
        composition.update({
            "coffee_base": "espresso",
            "espresso_shots": shots,
            "milk_base": "coconut_milk",
            "milk_volume_ml": milk_ml,
            "syrup_pumps": _syrup_pumps(volume, drink_type, sugar_level),
        })
        natural_sources.append("coconut_milk")
        assumptions.append("Coconut latte is modeled as espresso plus sweetened coconut milk base.")
    elif drink_type == "oat_latte":
        shots = _coffee_shots(volume, style="milk")
        milk_ml = _remaining_milk_volume(volume, shots, fill_ratio=0.68)
        composition.update({
            "coffee_base": "espresso",
            "espresso_shots": shots,
            "milk_base": "oat_milk",
            "milk_volume_ml": milk_ml,
            "syrup_pumps": _syrup_pumps(volume, drink_type, sugar_level),
        })
        natural_sources.append("oat_milk")
        assumptions.append("Oat latte is modeled as espresso plus oat milk.")
    elif drink_type == "latte":
        shots = _coffee_shots(volume, style="milk")
        milk_ml = _remaining_milk_volume(volume, shots, fill_ratio=0.68)
        composition.update({
            "coffee_base": "espresso",
            "espresso_shots": shots,
            "milk_base": "milk",
            "milk_volume_ml": milk_ml,
            "syrup_pumps": _syrup_pumps(volume, drink_type, sugar_level),
        })
        natural_sources.append("milk")
        assumptions.append("Latte is modeled as espresso plus milk.")
    elif drink_type == "americano":
        shots = _coffee_shots(volume, style="americano")
        composition.update({
            "coffee_base": "espresso",
            "espresso_shots": shots,
            "syrup_pumps": _syrup_pumps(volume, drink_type, sugar_level),
        })
        assumptions.append("Americano is modeled as espresso diluted with water.")
    elif drink_type == "milk_tea":
        tea_ml = round(volume * 0.62, 1)
        milk_ml = round(volume * 0.22, 1)
        composition.update({
            "tea_base": "black_or_oolong_tea",
            "tea_base_volume_ml": tea_ml,
            "milk_base": "milk",
            "milk_volume_ml": milk_ml,
            "syrup_pumps": _syrup_pumps(volume, drink_type, sugar_level),
        })
        natural_sources.append("milk")
        assumptions.append("Milk tea is modeled as tea base, milk, and adjustable added syrup.")
    elif drink_type == "fruit_tea":
        fruit_ml = round(volume * 0.58, 1)
        tea_ml = round(volume * 0.30, 1)
        composition.update({
            "tea_base": "light_tea",
            "tea_base_volume_ml": tea_ml,
            "fruit_base": "fruit_or_juice_base",
            "fruit_base_volume_ml": fruit_ml,
            "syrup_pumps": _syrup_pumps(volume, drink_type, sugar_level),
        })
        natural_sources.append("fruit_or_juice_base")
        assumptions.append("Fruit tea is modeled as tea plus fruit or juice base.")
    else:
        composition.update({
            "drink_type": "unknown",
            "syrup_pumps": _syrup_pumps(volume, "unknown", sugar_level),
            "fruit_base": "generic_beverage_base",
            "fruit_base_volume_ml": round(volume * 0.35, 1),
            "confidence": min(composition["confidence"], 0.45),
        })
        natural_sources.append("generic_beverage_base")
        warnings.append("Unknown drink style; using conservative generic beverage assumptions.")
        assumptions.append("Fallback composition uses a small generic sugar-containing base plus optional sweetener.")

    composition["confidence"] = _clamp_confidence(composition["confidence"])
    return composition


def estimate_from_composition(composition: dict) -> dict:
    """Estimate caffeine and sugar totals from a composition dictionary."""
    components: list[dict[str, Any]] = []
    reasoning: list[str] = []

    shots = float(composition.get("espresso_shots") or 0)
    if shots > 0:
        caffeine = shots * ESPRESSO_CAFFEINE_MG
        components.append(_component(
            name="espresso",
            category="coffee_base",
            amount=shots,
            unit="shot",
            caffeine_mg=caffeine,
            sugar_g=0.0,
            basis=f"{ESPRESSO_CAFFEINE_MG:g}mg caffeine per espresso shot",
            confidence=0.82,
        ))
        reasoning.append(f"Estimated espresso caffeine from {shots:g} shot(s).")

    tea_ml = float(composition.get("tea_base_volume_ml") or 0)
    tea_base = composition.get("tea_base")
    if tea_ml > 0:
        density = FRUIT_TEA_CAFFEINE_MG_PER_100ML if composition.get("drink_type") == "fruit_tea" else MILK_TEA_CAFFEINE_MG_PER_100ML
        caffeine = tea_ml * density / 100.0
        components.append(_component(
            name=str(tea_base or "tea_base"),
            category="tea_base",
            amount=tea_ml,
            unit="ml",
            caffeine_mg=caffeine,
            sugar_g=0.0,
            basis=f"{density:g}mg caffeine per 100ml tea base",
            confidence=0.68,
        ))
        reasoning.append("Estimated tea caffeine from tea base volume.")

    milk_ml = float(composition.get("milk_volume_ml") or 0)
    milk_base = composition.get("milk_base")
    if milk_ml > 0:
        sugar_density = _milk_sugar_density(str(milk_base or "milk"))
        sugar = milk_ml * sugar_density / 100.0
        components.append(_component(
            name=str(milk_base or "milk"),
            category="milk_base",
            amount=milk_ml,
            unit="ml",
            caffeine_mg=0.0,
            sugar_g=sugar,
            basis=f"{sugar_density:g}g sugar per 100ml {milk_base or 'milk'}",
            confidence=0.72,
        ))
        reasoning.append(f"Included natural sugar from {milk_base or 'milk'}.")

    fruit_ml = float(composition.get("fruit_base_volume_ml") or 0)
    fruit_base = composition.get("fruit_base")
    if fruit_ml > 0:
        sugar_density = FRUIT_BASE_SUGAR_G_PER_100ML
        sugar = fruit_ml * sugar_density / 100.0
        components.append(_component(
            name=str(fruit_base or "fruit_base"),
            category="fruit_base",
            amount=fruit_ml,
            unit="ml",
            caffeine_mg=0.0,
            sugar_g=sugar,
            basis=f"{sugar_density:g}g sugar per 100ml fruit or juice base",
            confidence=0.62 if composition.get("drink_type") == "unknown" else 0.70,
        ))
        reasoning.append("Included natural sugar from fruit or beverage base.")

    pumps = float(composition.get("syrup_pumps") or 0)
    level = str(composition.get("sweetener_level") or "unknown")
    multiplier = SWEETNESS_MULTIPLIERS.get(level, SWEETNESS_MULTIPLIERS["unknown"])
    if pumps > 0 and multiplier > 0:
        sugar = pumps * SYRUP_SUGAR_G_PER_PUMP * multiplier
        components.append(_component(
            name="added_syrup",
            category="sweetener",
            amount=round(pumps * multiplier, 2),
            unit="pump_equivalent",
            caffeine_mg=0.0,
            sugar_g=sugar,
            basis=f"{SYRUP_SUGAR_G_PER_PUMP:g}g sugar per syrup pump adjusted by sweetness level {level}",
            confidence=0.66 if level == "unknown" else 0.74,
        ))
        reasoning.append(f"Added sugar adjusted by sweetness level '{level}'.")
    elif pumps > 0:
        reasoning.append("No added syrup sugar because sweetness level is none.")

    caffeine_total = round(sum(item["caffeine_mg"] for item in components), 1)
    sugar_total = round(sum(item["sugar_g"] for item in components), 1)
    component_confidence = _average([item["confidence"] for item in components], default=0.5)
    confidence = min(float(composition.get("confidence") or 0.5), component_confidence)

    if composition.get("warnings"):
        reasoning.extend([f"Warning: {warning}" for warning in composition["warnings"]])

    return {
        "caffeine": caffeine_total,
        "sugarContent": sugar_total,
        "components": components,
        "reasoning": reasoning,
        "confidence": _clamp_confidence(confidence),
    }


def estimate_composition_nutrition(drink: dict) -> dict:
    """Public API for composition-based nutrition estimation."""
    composition = decompose_drink(drink)
    estimate = estimate_from_composition(composition)
    composition_with_components = {
        **composition,
        "components": estimate["components"],
    }

    return {
        "caffeine": estimate["caffeine"],
        "sugarContent": estimate["sugarContent"],
        "data_source": "Composition Estimation Agent",
        "confidence": estimate["confidence"],
        "reasoning": estimate["reasoning"],
        "estimation_method": "COMPOSITION_ESTIMATION",
        "matched_knowledge_id": None,
        "retrieval_score": None,
        "composition": composition_with_components,
    }


def _infer_drink_type(text: str, raw_type: str) -> str:
    if any(token in text for token in ["生椰", "coconut latte", "coconut milk latte", "coconut"]):
        return "coconut_latte"
    if any(token in text for token in ["燕麦", "oat latte", "oatmilk", "oat milk"]):
        return "oat_latte"
    if any(token in text for token in ["美式", "americano", "cold brew", "coldbrew"]):
        return "americano"
    if any(token in text for token in ["拿铁", "latte"]):
        return "latte"
    if raw_type in {"milktea", "milk_tea"} or any(token in text for token in ["奶茶", "milk tea"]):
        return "milk_tea"
    if raw_type == "fruittea" or any(token in text for token in ["水果茶", "果茶", "柠檬茶", "fruit tea", "juice tea"]):
        return "fruit_tea"
    if raw_type == "coffee":
        return "americano" if "coffee" in text else "latte"
    if raw_type == "tea":
        return "fruit_tea" if "fruit" in text else "milk_tea"
    return "unknown"


def _normalize_sugar_level(value: Any) -> str:
    if value is None:
        return "unknown"
    normalized = str(value).strip().lower()
    if not normalized:
        return "unknown"
    if normalized in SWEETNESS_MULTIPLIERS:
        return normalized
    for level, aliases in SUGAR_ALIASES.items():
        if normalized in aliases:
            return level
        if any(alias in normalized for alias in aliases if len(alias) >= 2):
            return level
    return "unknown"


def _safe_volume(value: Any) -> int:
    try:
        volume = int(float(value))
    except (TypeError, ValueError):
        return 500
    return min(max(volume, 100), 1000)


def _coffee_shots(volume: int, style: str) -> float:
    if style == "americano":
        if volume >= 600:
            return 3.0
        if volume >= 350:
            return 2.0
        return 1.0
    if volume >= 600:
        return 2.5
    if volume >= 450:
        return 2.0
    return 1.0


def _remaining_milk_volume(volume: int, shots: float, fill_ratio: float) -> float:
    espresso_ml = shots * ESPRESSO_SHOT_ML
    return round(max(volume * fill_ratio - espresso_ml, 0.0), 1)


def _syrup_pumps(volume: int, drink_type: str, sugar_level: str) -> float:
    if sugar_level == "none":
        return 0.0
    if drink_type == "americano":
        return 1.0 if sugar_level not in {"unknown", "none"} else 0.0
    if drink_type in {"latte", "oat_latte", "coconut_latte"}:
        return 2.0 if volume >= 450 else 1.0
    if drink_type == "milk_tea":
        return 5.0 if volume >= 450 else 3.0
    if drink_type == "fruit_tea":
        return 4.0 if volume >= 450 else 2.5
    return 2.0


def _milk_sugar_density(milk_base: str) -> float:
    if "coconut" in milk_base:
        return COCONUT_MILK_SUGAR_G_PER_100ML
    if "oat" in milk_base:
        return OAT_MILK_SUGAR_G_PER_100ML
    return MILK_SUGAR_G_PER_100ML


def _component(
    *,
    name: str,
    category: str,
    amount: float,
    unit: str,
    caffeine_mg: float,
    sugar_g: float,
    basis: str,
    confidence: float,
) -> dict:
    return {
        "name": name,
        "category": category,
        "amount": round(amount, 2),
        "unit": unit,
        "caffeine_mg": round(caffeine_mg, 1),
        "sugar_g": round(sugar_g, 1),
        "basis": basis,
        "confidence": _clamp_confidence(confidence),
    }


def _average(values: list[float], default: float) -> float:
    return sum(values) / len(values) if values else default


def _clamp_confidence(value: float) -> float:
    return round(max(0.1, min(float(value), 0.95)), 2)
