"""Deterministic beverage composition estimator.

This module is intentionally independent from the current nutrition pipeline.
It does not call LLMs, does not read/write the database, and returns a result
shape compatible with existing nutrition estimation responses.
"""

from __future__ import annotations

from typing import Any

from .ingredient_rules import (
    COCONUT_MILK_SUGAR_G_PER_100ML,
    COCONUT_WATER_SUGAR_G_PER_100ML,
    ESPRESSO_CAFFEINE_MG_PER_SHOT,
    FRUIT_BASE_SUGAR_G_PER_100ML,
    FRUIT_TEA_CAFFEINE_MG_PER_100ML,
    MILK_SUGAR_G_PER_100ML,
    MILK_TEA_CAFFEINE_MG_PER_100ML,
    OAT_MILK_SUGAR_G_PER_100ML,
    SUGAR_ALIASES,
    SWEETNESS_MULTIPLIERS,
    SYRUP_SUGAR_G_PER_PUMP,
    RangeEstimate,
    add_ranges,
    scale_range,
    zero_range,
)


ESPRESSO_SHOT_ML = 30.0


def decompose_drink(drink: dict) -> dict:
    """Infer a structured composition from a drink dictionary."""
    brand = str(drink.get("brand") or "").strip()
    name = str(drink.get("name") or "").strip()
    raw_type = str(drink.get("type") or "").strip().lower()
    volume = _safe_volume(drink.get("volume"))
    text = f"{brand} {name}".lower()
    sugar_level = _normalize_sugar_level(drink.get("sugar"))

    drink_type = _infer_drink_type(text, raw_type)
    assumptions: list[str] = []
    warnings: list[str] = []
    natural_sources: list[str] = []
    uncertainty_drivers: list[str] = []

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
        "uncertainty_drivers": uncertainty_drivers,
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
        uncertainty_drivers.append("Sweetness level is unknown, so added syrup is estimated from a half-sugar assumption.")
    if any(token in text for token in ["超燃", "能量", "energy"]):
        warnings.append("Functional or energy-style naming detected; extra caffeine sources are not modeled without product evidence.")
        uncertainty_drivers.append("Functional drink naming may imply extra active ingredients, but no verified product evidence was available.")

    if drink_type == "coconut_americano":
        shots = _coffee_shots(volume, style="americano")
        coconut_ml = _remaining_milk_volume(volume, shots, fill_ratio=0.78)
        composition.update({
            "coffee_base": "espresso",
            "espresso_shots": shots,
            "fruit_base": "coconut_water_base",
            "fruit_base_volume_ml": coconut_ml,
            "syrup_pumps": _syrup_pumps(volume, drink_type, sugar_level),
        })
        natural_sources.append("coconut_water_base")
        assumptions.append("Coconut americano is modeled as espresso plus coconut water or coconut beverage base.")
        uncertainty_drivers.append("Espresso caffeine varies by shot size and extraction.")
        uncertainty_drivers.append("Coconut beverage sugar varies by brand recipe and base volume.")
    elif drink_type == "fruit_americano":
        shots = _coffee_shots(volume, style="americano")
        fruit_ml = round(volume * 0.45, 1)
        composition.update({
            "coffee_base": "espresso",
            "espresso_shots": shots,
            "fruit_base": "fruit_or_juice_base",
            "fruit_base_volume_ml": fruit_ml,
            "syrup_pumps": _syrup_pumps(volume, drink_type, sugar_level),
        })
        natural_sources.append("fruit_or_juice_base")
        assumptions.append("Fruit americano is modeled as espresso plus a fruit or juice base.")
        uncertainty_drivers.append("Espresso caffeine varies by shot size and extraction.")
        uncertainty_drivers.append("Fruit or juice base sugar varies by fruit type, puree concentration, and brand recipe.")
    elif drink_type == "coconut_latte":
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
        uncertainty_drivers.append("Espresso caffeine varies by shot size and extraction.")
        uncertainty_drivers.append("Coconut milk sugar varies by brand recipe and milk volume.")
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
        uncertainty_drivers.append("Espresso caffeine varies by shot size and extraction.")
        uncertainty_drivers.append("Oat milk sugar varies by product formula and milk volume.")
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
        uncertainty_drivers.append("Espresso caffeine varies by shot size and extraction.")
        uncertainty_drivers.append("Milk volume is inferred from cup size, so natural milk sugar is a range.")
    elif drink_type == "americano":
        shots = _coffee_shots(volume, style="americano")
        composition.update({
            "coffee_base": "espresso",
            "espresso_shots": shots,
            "syrup_pumps": _syrup_pumps(volume, drink_type, sugar_level),
        })
        assumptions.append("Americano is modeled as espresso diluted with water.")
        uncertainty_drivers.append("Espresso caffeine varies by shot size and extraction.")
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
        uncertainty_drivers.append("Tea caffeine and milk ratio vary across milk tea recipes.")
        uncertainty_drivers.append("Sweetness labels map to brand-specific standard syrup amounts.")
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
        uncertainty_drivers.append("Fruit or juice base sugar varies by fruit mix and recipe concentration.")
        uncertainty_drivers.append("Tea caffeine is estimated from a light tea base range.")
    else:
        composition.update({
            "drink_type": "unknown",
            "syrup_pumps": _syrup_pumps(volume, "unknown", sugar_level),
            "fruit_base": "generic_beverage_base",
            "fruit_base_volume_ml": round(volume * 0.35, 1),
        })
        natural_sources.append("generic_beverage_base")
        warnings.append("Unknown drink style; using conservative generic beverage assumptions.")
        assumptions.append("Fallback composition uses a small generic sugar-containing base plus optional sweetener.")
        uncertainty_drivers.append("Drink style is unknown, so both composition and sugar density use broad generic assumptions.")

    return composition


def estimate_from_composition(composition: dict) -> dict:
    """Estimate caffeine and sugar totals from a composition dictionary."""
    components: list[dict[str, Any]] = []
    reasoning: list[str] = []
    caffeine_ranges: list[RangeEstimate] = []
    sugar_ranges: list[RangeEstimate] = []

    shots = float(composition.get("espresso_shots") or 0)
    if shots > 0:
        caffeine_range = scale_range(ESPRESSO_CAFFEINE_MG_PER_SHOT, shots)
        caffeine_ranges.append(caffeine_range)
        sugar_range = zero_range("g")
        sugar_ranges.append(sugar_range)
        components.append(_component(
            name="espresso",
            category="coffee_base",
            amount=shots,
            unit="shot",
            caffeine_range_mg=caffeine_range,
            sugar_range_g=sugar_range,
            basis=(
                f"{ESPRESSO_CAFFEINE_MG_PER_SHOT['min']:g}-"
                f"{ESPRESSO_CAFFEINE_MG_PER_SHOT['max']:g}mg caffeine per espresso shot, "
                f"best {ESPRESSO_CAFFEINE_MG_PER_SHOT['best']:g}mg"
            ),
        ))
        reasoning.append(
            f"Estimated espresso caffeine range from {shots:g} shot(s): "
            f"{caffeine_range['min']:g}-{caffeine_range['max']:g}mg, best {caffeine_range['best']:g}mg."
        )

    tea_ml = float(composition.get("tea_base_volume_ml") or 0)
    tea_base = composition.get("tea_base")
    if tea_ml > 0:
        density = FRUIT_TEA_CAFFEINE_MG_PER_100ML if composition.get("drink_type") == "fruit_tea" else MILK_TEA_CAFFEINE_MG_PER_100ML
        caffeine_range = scale_range(density, tea_ml, divisor=100.0)
        caffeine_ranges.append(caffeine_range)
        sugar_range = zero_range("g")
        sugar_ranges.append(sugar_range)
        components.append(_component(
            name=str(tea_base or "tea_base"),
            category="tea_base",
            amount=tea_ml,
            unit="ml",
            caffeine_range_mg=caffeine_range,
            sugar_range_g=sugar_range,
            basis=(
                f"{density['min']:g}-{density['max']:g}mg caffeine per 100ml tea base, "
                f"best {density['best']:g}mg"
            ),
        ))
        reasoning.append(
            f"Estimated tea caffeine range from tea base volume: "
            f"{caffeine_range['min']:g}-{caffeine_range['max']:g}mg."
        )

    milk_ml = float(composition.get("milk_volume_ml") or 0)
    milk_base = composition.get("milk_base")
    if milk_ml > 0:
        sugar_density = _milk_sugar_density(str(milk_base or "milk"))
        caffeine_range = zero_range("mg")
        caffeine_ranges.append(caffeine_range)
        sugar_range = scale_range(sugar_density, milk_ml, divisor=100.0)
        sugar_ranges.append(sugar_range)
        components.append(_component(
            name=str(milk_base or "milk"),
            category="milk_base",
            amount=milk_ml,
            unit="ml",
            caffeine_range_mg=caffeine_range,
            sugar_range_g=sugar_range,
            basis=(
                f"{sugar_density['min']:g}-{sugar_density['max']:g}g sugar per 100ml "
                f"{milk_base or 'milk'}, best {sugar_density['best']:g}g"
            ),
        ))
        reasoning.append(
            f"Included natural sugar range from {milk_base or 'milk'}: "
            f"{sugar_range['min']:g}-{sugar_range['max']:g}g."
        )

    fruit_ml = float(composition.get("fruit_base_volume_ml") or 0)
    fruit_base = composition.get("fruit_base")
    if fruit_ml > 0:
        sugar_density = _fruit_sugar_density(str(fruit_base or "fruit_base"))
        caffeine_range = zero_range("mg")
        caffeine_ranges.append(caffeine_range)
        sugar_range = scale_range(sugar_density, fruit_ml, divisor=100.0)
        sugar_ranges.append(sugar_range)
        components.append(_component(
            name=str(fruit_base or "fruit_base"),
            category="fruit_base",
            amount=fruit_ml,
            unit="ml",
            caffeine_range_mg=caffeine_range,
            sugar_range_g=sugar_range,
            basis=(
                f"{sugar_density['min']:g}-{sugar_density['max']:g}g sugar per 100ml "
                f"{_fruit_basis_label(str(fruit_base or 'fruit_base'))}, best {sugar_density['best']:g}g"
            ),
        ))
        reasoning.append(
            f"Included natural sugar range from fruit or beverage base: "
            f"{sugar_range['min']:g}-{sugar_range['max']:g}g."
        )

    pumps = float(composition.get("syrup_pumps") or 0)
    level = str(composition.get("sweetener_level") or "unknown")
    multiplier = SWEETNESS_MULTIPLIERS.get(level, SWEETNESS_MULTIPLIERS["unknown"])
    if pumps > 0 and multiplier > 0:
        caffeine_range = zero_range("mg")
        caffeine_ranges.append(caffeine_range)
        sugar_range = scale_range(SYRUP_SUGAR_G_PER_PUMP, pumps * multiplier)
        sugar_ranges.append(sugar_range)
        components.append(_component(
            name="added_syrup",
            category="sweetener",
            amount=round(pumps * multiplier, 2),
            unit="pump_equivalent",
            caffeine_range_mg=caffeine_range,
            sugar_range_g=sugar_range,
            basis=(
                f"{SYRUP_SUGAR_G_PER_PUMP['min']:g}-{SYRUP_SUGAR_G_PER_PUMP['max']:g}g sugar per syrup pump "
                f"adjusted by sweetness level {level}, best {SYRUP_SUGAR_G_PER_PUMP['best']:g}g"
            ),
        ))
        reasoning.append(
            f"Added sugar range adjusted by sweetness level '{level}': "
            f"{sugar_range['min']:g}-{sugar_range['max']:g}g."
        )
    elif pumps > 0:
        reasoning.append("No added syrup sugar because sweetness level is none.")

    caffeine_total_range = add_ranges(caffeine_ranges, "mg")
    sugar_total_range = add_ranges(sugar_ranges, "g")
    caffeine_total = caffeine_total_range["best"]
    sugar_total = sugar_total_range["best"]

    if composition.get("warnings"):
        reasoning.extend([f"Warning: {warning}" for warning in composition["warnings"]])

    return {
        "caffeine": caffeine_total,
        "sugarContent": sugar_total,
        "caffeine_range": caffeine_total_range,
        "sugar_range": sugar_total_range,
        "components": components,
        "reasoning": reasoning,
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
        "caffeine_range": estimate["caffeine_range"],
        "sugar_range": estimate["sugar_range"],
        "data_source": "Composition Estimation Agent",
        "reasoning": estimate["reasoning"],
        "estimation_method": "COMPOSITION_ESTIMATION",
        "matched_knowledge_id": None,
        "retrieval_score": None,
        "composition": composition_with_components,
    }


def _infer_drink_type(text: str, raw_type: str) -> str:
    has_coconut = _has_any(text, [
        "生椰", "椰青", "椰子", "椰乳", "椰水", "椰",
        "sheng ye", "raw coconut", "coconut",
    ])
    has_fruit = _has_any(text, [
        "果咖", "果汁", "果萃", "鲜果", "水果",
        "橙", "橙子", "橙c", "橙C", "柚", "西柚", "葡萄柚", "柠", "柠檬",
        "桑葚", "桑椹", "桑果", "葡萄", "莓", "草莓", "蓝莓", "树莓", "覆盆子",
        "桃", "黄桃", "白桃", "芒果", "百香果", "杨梅", "荔枝", "苹果",
        "凤梨", "菠萝", "青提", "红提",
        "orange", "grapefruit", "lemon", "lime", "mulberry", "grape",
        "berry", "strawberry", "blueberry", "raspberry", "peach", "mango",
        "passion fruit", "pineapple", "apple", "juice", "fruit",
    ])
    has_americano = _has_any(text, ["美式", "americano", "cold brew", "coldbrew", "mei shi"])
    has_latte = _has_any(text, ["拿铁", "拿鐵", "latte", "na tie"])
    has_coffee = _has_any(text, ["咖啡", "coffee"])
    if has_coconut and has_americano:
        return "coconut_americano"
    if has_coconut:
        return "coconut_latte"
    if has_fruit and (has_americano or has_coffee or raw_type == "coffee"):
        return "fruit_americano"
    if any(token in text for token in ["yan mai", "oat latte", "oatmilk", "oat milk"]):
        return "oat_latte"
    if has_americano:
        return "americano"
    if has_latte:
        return "latte"
    if raw_type in {"milktea", "milk_tea"} or any(token in text for token in ["nai cha", "milk tea"]):
        return "milk_tea"
    if raw_type == "fruittea" or any(token in text for token in ["shui guo cha", "guo cha", "ning meng cha", "fruit tea", "juice tea"]):
        return "fruit_tea"
    if raw_type == "coffee":
        return "americano" if has_americano else "latte"
    if raw_type == "tea":
        return "fruit_tea" if "fruit" in text else "milk_tea"
    return "unknown"


def _has_any(text: str, tokens: list[str]) -> bool:
    return any(token.lower() in text for token in tokens)


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
    if drink_type in {"americano", "coconut_americano", "fruit_americano"}:
        return 1.0 if sugar_level not in {"unknown", "none"} else 0.0
    if drink_type in {"latte", "oat_latte", "coconut_latte"}:
        return 2.0 if volume >= 450 else 1.0
    if drink_type == "milk_tea":
        return 5.0 if volume >= 450 else 3.0
    if drink_type == "fruit_tea":
        return 4.0 if volume >= 450 else 2.5
    return 2.0


def _milk_sugar_density(milk_base: str) -> RangeEstimate:
    if "coconut" in milk_base:
        return COCONUT_MILK_SUGAR_G_PER_100ML
    if "oat" in milk_base:
        return OAT_MILK_SUGAR_G_PER_100ML
    return MILK_SUGAR_G_PER_100ML


def _fruit_sugar_density(fruit_base: str) -> RangeEstimate:
    if "coconut" in fruit_base:
        return COCONUT_WATER_SUGAR_G_PER_100ML
    return FRUIT_BASE_SUGAR_G_PER_100ML


def _fruit_basis_label(fruit_base: str) -> str:
    if "coconut" in fruit_base:
        return "coconut water or coconut beverage base"
    return "fruit or juice base"


def _component(
    *,
    name: str,
    category: str,
    amount: float,
    unit: str,
    caffeine_range_mg: RangeEstimate,
    sugar_range_g: RangeEstimate,
    basis: str,
) -> dict:
    return {
        "name": name,
        "category": category,
        "amount": round(amount, 2),
        "unit": unit,
        "caffeine_mg": caffeine_range_mg["best"],
        "sugar_g": sugar_range_g["best"],
        "caffeine_range_mg": caffeine_range_mg,
        "sugar_range_g": sugar_range_g,
        "basis": basis,
    }
