"""Ingredient-level nutrition rules for deterministic composition estimates."""

from __future__ import annotations

from typing import TypedDict


class RangeEstimate(TypedDict):
    min: float
    max: float
    best: float
    unit: str


def make_range(min_value: float, max_value: float, best: float, unit: str) -> RangeEstimate:
    """Create a normalized range estimate."""
    low = float(min_value)
    high = float(max_value)
    best_value = float(best)
    if high < low:
        low, high = high, low
    best_value = max(low, min(best_value, high))
    return {
        "min": round(low, 1),
        "max": round(high, 1),
        "best": round(best_value, 1),
        "unit": unit,
    }


def zero_range(unit: str) -> RangeEstimate:
    return make_range(0.0, 0.0, 0.0, unit)


def scale_range(rule: RangeEstimate, amount: float, divisor: float = 1.0) -> RangeEstimate:
    factor = float(amount) / float(divisor)
    return make_range(
        rule["min"] * factor,
        rule["max"] * factor,
        rule["best"] * factor,
        rule["unit"],
    )


def add_ranges(ranges: list[RangeEstimate], unit: str) -> RangeEstimate:
    if not ranges:
        return zero_range(unit)
    return make_range(
        sum(item["min"] for item in ranges),
        sum(item["max"] for item in ranges),
        sum(item["best"] for item in ranges),
        unit,
    )


ESPRESSO_CAFFEINE_MG_PER_SHOT = make_range(55.0, 85.0, 70.0, "mg")
MILK_SUGAR_G_PER_100ML = make_range(4.5, 5.5, 5.0, "g")
COCONUT_MILK_SUGAR_G_PER_100ML = make_range(6.0, 10.0, 8.0, "g")
COCONUT_WATER_SUGAR_G_PER_100ML = make_range(3.5, 5.5, 4.5, "g")
OAT_MILK_SUGAR_G_PER_100ML = make_range(3.0, 6.0, 4.5, "g")
MILK_TEA_CAFFEINE_MG_PER_100ML = make_range(15.0, 35.0, 25.0, "mg")
FRUIT_TEA_CAFFEINE_MG_PER_100ML = make_range(4.0, 14.0, 8.0, "mg")
FRUIT_BASE_SUGAR_G_PER_100ML = make_range(6.0, 12.0, 9.0, "g")
SYRUP_SUGAR_G_PER_PUMP = make_range(5.0, 8.0, 6.0, "g")


SWEETNESS_MULTIPLIERS = {
    "none": 0.0,
    "three": 0.3,
    "half": 0.5,
    "seven": 0.7,
    "full": 1.0,
    "unknown": 0.5,
}


SUGAR_ALIASES = {
    "none": ["none", "no", "zero", "sugar-free", "sugar free", "unsweetened", "0", "0%", "wu tang", "no sugar"],
    "three": ["three", "3", "30%", "san fen", "san fen tang", "less sugar"],
    "half": ["half", "50%", "ban tang", "wu fen", "wu fen tang"],
    "seven": ["seven", "70%", "qi fen", "qi fen tang"],
    "full": ["full", "100%", "regular", "normal", "quan tang", "full sugar"],
}
