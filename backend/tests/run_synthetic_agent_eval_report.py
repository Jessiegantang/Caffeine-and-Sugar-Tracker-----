"""Run deterministic synthetic evals for DrinkMind intake and agent flow.

This suite is intentionally separate from production metrics. It uses a fixed
100-case simulated input set so parser and workflow changes can be compared
against a stable baseline.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import agents.intake_parser as intake_parser
from agents.orchestrator import run_agent_orchestrator
from db.database import DrinkLog, SessionLocal, UserPreference


ROOT_DIR = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT_DIR / "docs" / "synthetic_agent_eval_report.md"


def build_synthetic_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    cases.extend(_complete_log_cases())
    cases.extend(_missing_field_cases())
    cases.extend(_advice_cases())
    if len(cases) != 100:
        raise RuntimeError(f"Synthetic case count changed unexpectedly: {len(cases)}")
    return cases


def _complete_log_cases() -> list[dict[str, Any]]:
    specs = [
        ("luckin_coconut_latte_large_three", "我刚喝了一杯瑞幸生椰拿铁，大杯，三分糖。", "瑞幸咖啡", "生椰拿铁", 500, "three", "coffee"),
        ("luckin_coconut_latte_large_half", "我喝了一杯瑞幸生椰拿铁大杯，不是全糖是半糖", "瑞幸咖啡", "生椰拿铁", 500, "half", "coffee"),
        ("cotti_coconut_americano_650_none", "记录一杯库迪超燃生椰美式650ml不另外加糖", "库迪咖啡", "超燃生椰美式", 650, "none", "coffee"),
        ("starbucks_americano_500_none", "我喝了星巴克美式500ml无糖", "星巴克", "美式", 500, "none", "coffee"),
        ("manner_yuzu_americano_large_three", "刚喝了 Manner 柚子美式 大杯 三分糖", "Manner Coffee", "柚子美式", 500, "three", "coffee"),
        ("moli_orchid_latte_large_half", "我刚喝了一杯茉莉奶白的白兰拿铁，大杯，半糖", "茉莉奶白", "白兰拿铁", 500, "half", "coffee"),
        ("classic_milk_tea_500_half", "我喝了一杯经典奶茶500ml半糖", None, "经典奶茶", 500, "half", "milktea"),
        ("fruit_tea_500_none", "记录一杯水果茶500ml无糖", None, "水果茶", 500, "none", "fruittea"),
        ("americano_500_full", "记录一杯美式500ml全糖", None, "美式", 500, "full", "coffee"),
        ("oat_latte_500_half", "刚喝燕麦拿铁500ml半糖", None, "燕麦拿铁", 500, "half", "coffee"),
        ("coke_can_none", "刚刚喝了一罐可乐无糖", "可口可乐", "可乐", 330, "none", "soda"),
        ("nayuki_lemon_tea_large_seven", "我点了奈雪的茶柠檬茶大杯七分糖", "奈雪的茶", "柠檬茶", 500, "seven", "fruittea"),
        ("heytea_yangzhi_large_half", "记录喜茶杨枝甘露大杯半糖", "喜茶", "杨枝甘露", 500, "half", "milktea"),
        ("chabaidao_milk_tea_medium_three", "我刚才喝了茶百道奶茶中杯三分糖", "茶百道", "奶茶", 330, "three", "milktea"),
        ("guming_fruit_tea_large_full", "加一条古茗果茶大杯正常糖", "古茗", "果茶", 500, "full", "fruittea"),
        ("mixue_lemon_tea_large_none", "刚才买了蜜雪冰城柠檬茶大杯零糖", "蜜雪冰城", "柠檬茶", 500, "none", "fruittea"),
        ("pepsi_can_full", "记录一罐百事可乐正常糖", "百事可乐", "可乐", 330, "full", "soda"),
        ("tims_coffee_standard_none", "我刚喝了天好咖啡标准杯不加糖", "Tims", "咖啡", 350, "none", "coffee"),
        ("costa_latte_small_half", "刚刚喝了 costa 拿铁小杯五分糖", "Costa", "拿铁", 250, "half", "coffee"),
        ("yidiandian_milk_tea_large_seven", "我喝了一点点奶茶大杯少糖", "一点点", "奶茶", 500, "seven", "milktea"),
        ("luckin_americano_medium_none", "记录瑞幸咖啡美式中杯无糖", "瑞幸咖啡", "美式", 330, "none", "coffee"),
        ("cotti_latte_small_three", "我买了库迪拿铁小杯微糖", "库迪咖啡", "拿铁", 250, "three", "coffee"),
        ("starbucks_latte_standard_half", "记录星巴克拿铁标准杯半糖", "星巴克", "拿铁", 350, "half", "coffee"),
        ("manner_coffee_large_none", "刚喝了manner coffee咖啡大杯no sugar", "Manner Coffee", "咖啡", 500, "none", "coffee"),
        ("moli_milk_tea_500_seven", "记录茉莉奶白奶茶500ml少糖", "茉莉奶白", "奶茶", 500, "seven", "milktea"),
        ("heytea_fruit_tea_650_half", "喝了喜茶果茶650ml五分糖", "喜茶", "果茶", 650, "half", "fruittea"),
        ("nayuki_yangzhi_500_full", "加一条奈雪杨枝甘露500ml标准糖", "奈雪的茶", "杨枝甘露", 500, "full", "milktea"),
        ("chabaidao_lemon_tea_330_none", "茶百道柠檬茶中杯不加糖，帮我记一下", "茶百道", "柠檬茶", 330, "none", "fruittea"),
        ("guming_milk_tea_250_half", "刚喝古茗奶茶小杯半糖", "古茗", "奶茶", 250, "half", "milktea"),
        ("mixue_fruit_tea_500_three", "蜜雪冰城水果茶大杯三分糖记录一下", "蜜雪冰城", "水果茶", 500, "three", "fruittea"),
        ("coke_500_full", "我喝了可口可乐500ml正常糖", "可口可乐", "可乐", 500, "full", "soda"),
        ("pepsi_500_none", "刚喝了百事可乐500ml零糖", "百事可乐", "可乐", 500, "none", "soda"),
        ("tims_latte_500_half", "记录Tims拿铁大杯半糖", "Tims", "拿铁", 500, "half", "coffee"),
        ("costa_americano_350_none", "costa 美式标准杯无糖，记一下", "Costa", "美式", 350, "none", "coffee"),
        ("yidiandian_fruit_tea_500_full", "一点点果茶大杯全糖", "一点点", "果茶", 500, "full", "fruittea"),
        ("luckin_raw_coconut_latte_650_half", "瑞幸生椰拿铁超大杯五分糖", "瑞幸咖啡", "生椰拿铁", 650, "half", "coffee"),
        ("cotti_americano_500_none", "库迪美式大杯sugar free", "库迪咖啡", "美式", 500, "none", "coffee"),
        ("starbucks_oat_latte_500_three", "我喝了星巴克燕麦拿铁大杯三分糖", "星巴克", "燕麦拿铁", 500, "three", "coffee"),
        ("manner_latte_250_half", "manner 拿铁小杯半糖", "Manner Coffee", "拿铁", 250, "half", "coffee"),
        ("moli_lemon_tea_500_none", "茉莉奶白柠檬茶大杯无糖", "茉莉奶白", "柠檬茶", 500, "none", "fruittea"),
        ("heytea_milk_tea_330_seven", "喜茶奶茶中杯七分糖", "喜茶", "奶茶", 330, "seven", "milktea"),
        ("nayuki_fruit_tea_650_three", "记录奈雪果茶650ml微糖", "奈雪的茶", "果茶", 650, "three", "fruittea"),
        ("chabaidao_yangzhi_500_half", "刚喝茶百道杨枝甘露大杯半糖", "茶百道", "杨枝甘露", 500, "half", "milktea"),
        ("guming_lemon_tea_500_none", "古茗柠檬茶大杯不另外加糖", "古茗", "柠檬茶", 500, "none", "fruittea"),
        ("mixue_milk_tea_330_full", "蜜雪冰城奶茶中杯正常糖", "蜜雪冰城", "奶茶", 330, "full", "milktea"),
        ("plain_coffee_250_none", "刚喝咖啡小杯无糖", None, "咖啡", 250, "none", "coffee"),
        ("plain_latte_500_half", "记录拿铁500ml半糖", None, "拿铁", 500, "half", "coffee"),
        ("plain_lemon_tea_330_three", "柠檬茶中杯三分糖", None, "柠檬茶", 330, "three", "fruittea"),
        ("plain_milk_tea_650_seven", "奶茶超大杯少糖", None, "奶茶", 650, "seven", "milktea"),
        ("plain_fruit_tea_350_none", "水果茶标准杯零糖", None, "水果茶", 350, "none", "fruittea"),
        ("plain_coke_330_full", "可乐一罐全糖", "可口可乐", "可乐", 330, "full", "soda"),
        ("english_luckin_500_none", "luckin americano 500ml no sugar", "瑞幸咖啡", "americano", 500, "none", "coffee"),
        ("english_cotti_latte_350_half", "cotti latte 标准杯 50%糖", "库迪咖啡", "latte", 350, "half", "coffee"),
        ("mixed_star_latte_500_three", "starbucks latte 大杯 30%糖", "星巴克", "latte", 500, "three", "coffee"),
        ("mixed_manner_americano_250_none", "manner americano 小杯 sugar free", "Manner Coffee", "americano", 250, "none", "coffee"),
        ("time_morning_coffee", "早上喝了咖啡250ml无糖", None, "咖啡", 250, "none", "coffee"),
        ("time_afternoon_latte", "下午喝了拿铁大杯半糖", None, "拿铁", 500, "half", "coffee"),
        ("time_evening_milk_tea", "晚上喝了奶茶中杯三分糖", None, "奶茶", 330, "three", "milktea"),
        ("punctuated_fruit_tea", "刚刚，记录一下：水果茶，500ml，无糖！", None, "水果茶", 500, "none", "fruittea"),
        ("punctuated_latte", "我喝了：拿铁，350ml，半糖。", None, "拿铁", 350, "half", "coffee"),
    ]
    return [
        _log_case(i, "log_" + case_id, message, brand, name, volume, sugar, drink_type)
        for i, (case_id, message, brand, name, volume, sugar, drink_type) in enumerate(specs, start=1)
    ]


def _missing_field_cases() -> list[dict[str, Any]]:
    specs = [
        ("missing_sugar_luckin", "我刚喝了一杯瑞幸生椰拿铁，大杯。", {"brand": "瑞幸咖啡", "name": "生椰拿铁", "volume": 500, "type": "coffee"}, ["sugar"]),
        ("missing_volume_and_sugar_milk_tea", "刚喝了点奶茶", {"name": "奶茶", "type": "milktea"}, ["volume", "sugar"]),
        ("missing_volume_fruit_tea", "记录水果茶无糖", {"name": "水果茶", "sugar": "none", "type": "fruittea"}, ["volume"]),
        ("missing_sugar_starbucks", "刚喝了星巴克美式500ml", {"brand": "星巴克", "name": "美式", "volume": 500, "type": "coffee"}, ["sugar"]),
        ("missing_sugar_pepsi", "记录百事可乐500ml", {"brand": "百事可乐", "name": "可乐", "volume": 500, "type": "soda"}, ["sugar"]),
        ("missing_volume_cotti", "我喝了库迪拿铁无糖", {"brand": "库迪咖啡", "name": "拿铁", "sugar": "none", "type": "coffee"}, ["volume"]),
        ("missing_volume_luckin", "瑞幸生椰拿铁半糖", {"brand": "瑞幸咖啡", "name": "生椰拿铁", "sugar": "half", "type": "coffee"}, ["volume"]),
        ("missing_sugar_guming", "古茗果茶大杯", {"brand": "古茗", "name": "果茶", "volume": 500, "type": "fruittea"}, ["sugar"]),
        ("missing_sugar_manner", "manner 美式标准杯", {"brand": "Manner Coffee", "name": "美式", "volume": 350, "type": "coffee"}, ["sugar"]),
        ("missing_volume_manner", "manner 美式无糖", {"brand": "Manner Coffee", "name": "美式", "sugar": "none", "type": "coffee"}, ["volume"]),
        ("missing_volume_sugar_coffee", "刚喝了点咖啡", {"name": "咖啡", "type": "coffee"}, ["volume", "sugar"]),
        ("missing_volume_sugar_lemon_tea", "刚喝了点柠檬茶", {"name": "柠檬茶", "type": "fruittea"}, ["volume", "sugar"]),
        ("missing_sugar_tims", "天好咖啡大杯", {"brand": "Tims", "name": "咖啡", "volume": 500, "type": "coffee"}, ["sugar"]),
        ("missing_sugar_coke", "可乐一罐", {"brand": "可口可乐", "name": "可乐", "volume": 330, "type": "soda"}, ["sugar"]),
        ("missing_volume_mixue", "蜜雪柠檬茶无糖", {"brand": "蜜雪冰城", "name": "柠檬茶", "sugar": "none", "type": "fruittea"}, ["volume"]),
        ("missing_sugar_yidiandian", "一点点奶茶中杯", {"brand": "一点点", "name": "奶茶", "volume": 330, "type": "milktea"}, ["sugar"]),
        ("missing_volume_nayuki", "奈雪果茶半糖", {"brand": "奈雪的茶", "name": "果茶", "sugar": "half", "type": "fruittea"}, ["volume"]),
        ("missing_sugar_costa", "costa 拿铁小杯", {"brand": "Costa", "name": "拿铁", "volume": 250, "type": "coffee"}, ["sugar"]),
        ("missing_volume_sugar_yangzhi", "喝了点杨枝甘露", {"name": "杨枝甘露", "type": "milktea"}, ["volume", "sugar"]),
        ("missing_volume_plain_americano", "记录美式无糖", {"name": "美式", "sugar": "none", "type": "coffee"}, ["volume"]),
    ]
    return [_followup_case(61 + i, case_id, message, fields, missing) for i, (case_id, message, fields, missing) in enumerate(specs)]


def _advice_cases() -> list[dict[str, Any]]:
    messages = [
        ("can_drink_coffee", "我现在还能喝咖啡吗？"),
        ("milk_tea_afternoon", "下午还能喝奶茶吗"),
        ("today_budget", "今天饮品预算还安全吗"),
        ("recommend_drink", "给我一个今天饮品建议"),
        ("symptom_nausea", "我今天这杯生椰美式喝得有点久，一直想干呕"),
        ("after_three_no_caffeine", "我下午三点后不喝咖啡因，现在饮品预算还安全吗"),
        ("too_much_sugar", "今天糖分是不是有点高？"),
        ("low_sugar_choice", "推荐一个低糖饮品可以吗"),
        ("sleep_sensitive", "我晚上容易睡不着，现在适合喝咖啡吗"),
        ("heart_racing", "喝完咖啡有点心慌怎么办"),
        ("healthy_today", "今天喝饮品健康吗"),
        ("can_have_soda", "我还可以喝可乐吗？"),
        ("choose_milk_tea", "现在适合点奶茶还是茶？"),
        ("caffeine_budget", "咖啡因额度还够吗"),
        ("sugar_budget", "糖分额度还够吗"),
        ("evening_recommendation", "晚上想喝点东西，有建议吗"),
        ("after_latte", "刚喝完拿铁还能再喝美式吗"),
        ("risk_check", "帮我看一下今天风险高不高"),
        ("drink_plan", "今天饮品怎么安排比较好"),
        ("avoid_caffeine", "不想摄入咖啡因，有什么建议"),
    ]
    return [
        {
            "id": f"advice_{case_id}",
            "message": message,
            "date": _date_for(81 + i),
            "expected": {"intent": "ask_advice", "final_action": "answer_advice"},
        }
        for i, (case_id, message) in enumerate(messages)
    ]


def _log_case(
    index: int,
    case_id: str,
    message: str,
    brand: str | None,
    name: str,
    volume: int,
    sugar: str,
    drink_type: str,
) -> dict[str, Any]:
    fields: dict[str, Any] = {"name": name, "volume": volume, "sugar": sugar, "type": drink_type}
    if brand:
        fields["brand"] = brand
    return {
        "id": case_id,
        "message": message,
        "date": _date_for(index),
        "expected": {
            "intent": "log_drink",
            "final_action": "fill_log_form",
            "parsed_fields": fields,
        },
    }


def _followup_case(
    index: int,
    case_id: str,
    message: str,
    fields: dict[str, Any],
    missing_fields: list[str],
) -> dict[str, Any]:
    return {
        "id": f"followup_{case_id}",
        "message": message,
        "date": _date_for(index),
        "expected": {
            "intent": "log_drink",
            "final_action": "ask_follow_up",
            "parsed_fields": fields,
            "required_missing_fields": missing_fields,
        },
    }


def _date_for(index: int) -> str:
    return f"2026-08-{index:02d}" if index <= 99 else "2026-09-01"


SYNTHETIC_CASES = build_synthetic_cases()


@contextlib.contextmanager
def legacy_parser_baseline() -> Iterator[None]:
    """Temporarily emulate parser behavior before the latest rule fixes."""

    original_infer_brand = intake_parser._infer_brand
    original_infer_name = intake_parser._infer_name
    original_remove_context = intake_parser._remove_known_context

    def legacy_infer_brand(text: str) -> str | None:
        lowered = text.lower()
        for brand, aliases in intake_parser.KNOWN_BRAND_ALIASES:
            if any(alias.lower() in lowered for alias in aliases):
                return brand
        return None

    def legacy_infer_name(text: str, brand: str | None) -> str | None:
        cleaned = legacy_remove_known_context(text, brand)
        suffix_name = intake_parser._extract_name_by_suffix(cleaned)
        if suffix_name:
            return suffix_name
        parts = [p.strip(" ,.，。!！?？、") for p in re.split(r"[\s,，。!！?？、]+", cleaned)]
        candidates = [p for p in parts if len(p) >= 2 and not p.isdigit()]
        if not candidates:
            return None
        return max(candidates, key=len)

    def legacy_remove_known_context(text: str, brand: str | None) -> str:
        cleaned = text
        remove_tokens = [
            "我", "刚喝了", "刚喝", "喝了", "买了", "点了",
            "来一杯", "记录", "加一条", "一杯", "一瓶",
            "今天", "现在", "刚刚", "刚才", "上午", "下午", "晚上",
        ]
        for token in remove_tokens:
            cleaned = cleaned.replace(token, " ")
        for token in intake_parser.FILLER_TOKENS:
            cleaned = cleaned.replace(token, " ")
        if brand:
            cleaned = cleaned.replace(brand, " ")
        for _, aliases in intake_parser.KNOWN_BRAND_ALIASES:
            for alias in aliases:
                cleaned = re.sub(re.escape(alias), " ", cleaned, flags=re.IGNORECASE)
        for _, aliases in intake_parser.SUGAR_ALIASES:
            for alias in aliases:
                cleaned = re.sub(re.escape(alias), " ", cleaned, flags=re.IGNORECASE)
        for _, aliases in intake_parser.SIZE_ALIASES:
            for alias in aliases:
                cleaned = cleaned.replace(alias, " ")
        cleaned = re.sub(r"\d{2,4}\s*(?:ml|mL|ML|毫升)", " ", cleaned)
        return cleaned

    intake_parser._infer_brand = legacy_infer_brand
    intake_parser._infer_name = legacy_infer_name
    intake_parser._remove_known_context = legacy_remove_known_context
    try:
        yield
    finally:
        intake_parser._infer_brand = original_infer_brand
        intake_parser._infer_name = original_infer_name
        intake_parser._remove_known_context = original_remove_context


def run_report(mode: str = "current") -> dict[str, Any]:
    original_api_key = os.getenv("OPENAI_API_KEY")
    original_enable_llm = os.getenv("ENABLE_LLM")
    original_offline = os.getenv("DRINKMIND_OFFLINE")
    os.environ["OPENAI_API_KEY"] = "dummy_synthetic_eval_key"
    os.environ["ENABLE_LLM"] = "false"
    os.environ["DRINKMIND_OFFLINE"] = "true"

    rows = []
    patcher = legacy_parser_baseline() if mode == "baseline" else contextlib.nullcontext()
    try:
        with patcher:
            for case in SYNTHETIC_CASES:
                rows.append(evaluate_case(case))
    finally:
        _restore_env("OPENAI_API_KEY", original_api_key)
        _restore_env("ENABLE_LLM", original_enable_llm)
        _restore_env("DRINKMIND_OFFLINE", original_offline)
        cleanup_cases(SYNTHETIC_CASES)

    summary = {
        "mode": mode,
        "total": len(rows),
        "passed": sum(1 for row in rows if row["passed"]),
        "failed": sum(1 for row in rows if not row["passed"]),
        "pass_rate": round(sum(1 for row in rows if row["passed"]) / len(rows), 4),
        "intent_distribution": dict(Counter(row["intent"] for row in rows)),
        "action_distribution": dict(Counter(row["final_action"] for row in rows)),
        "metrics": aggregate_metrics(rows),
    }
    return {"rows": rows, "summary": summary}


def _restore_env(name: str, original_value: str | None) -> None:
    if original_value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = original_value


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    result = run_case(case)
    expected = case["expected"]
    parsed = result.get("parsed_drink") or {}

    metrics: dict[str, dict[str, int]] = {}
    failures = []

    def score(name: str, correct: bool) -> None:
        metrics[name] = {"correct": 1 if correct else 0, "total": 1}
        if not correct:
            failures.append(name)

    score("intent_accuracy", result.get("intent") == expected.get("intent"))
    score("final_action_accuracy", result.get("final_action") == expected.get("final_action"))

    parsed_fields = expected.get("parsed_fields") or {}
    if parsed_fields:
        correct = sum(1 for key, value in parsed_fields.items() if parsed.get(key) == value)
        metrics["parsed_field_accuracy"] = {"correct": correct, "total": len(parsed_fields)}
        if correct != len(parsed_fields):
            failures.append("parsed_field_accuracy")

    required_missing = expected.get("required_missing_fields") or []
    if required_missing:
        actual_missing = parsed.get("missing_fields") or []
        correct = sum(1 for field in required_missing if field in actual_missing)
        metrics["missing_field_recall"] = {"correct": correct, "total": len(required_missing)}
        if correct != len(required_missing):
            failures.append("missing_field_recall")

    return {
        "id": case["id"],
        "intent": result.get("intent"),
        "final_action": result.get("final_action"),
        "parsed": parsed,
        "metrics": metrics,
        "passed": not failures,
        "failures": failures,
    }


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    db = SessionLocal()
    try:
        reset_case_data(db, case)
        db.commit()
        return run_agent_orchestrator(case["message"], case["date"], db)
    finally:
        db.close()


def reset_case_data(db, case: dict[str, Any]) -> None:
    db.query(DrinkLog).filter(DrinkLog.date == case["date"]).delete()
    db.query(UserPreference).delete()
    db.commit()


def cleanup_cases(cases: list[dict[str, Any]]) -> None:
    db = SessionLocal()
    try:
        for case in cases:
            reset_case_data(db, case)
    finally:
        db.close()


def aggregate_metrics(rows: list[dict[str, Any]]) -> dict[str, dict[str, int | float]]:
    totals: dict[str, dict[str, int | float]] = {}
    for row in rows:
        for name, metric in row["metrics"].items():
            bucket = totals.setdefault(name, {"correct": 0, "total": 0, "rate": 0.0})
            bucket["correct"] += metric["correct"]
            bucket["total"] += metric["total"]
    for metric in totals.values():
        metric["rate"] = round(metric["correct"] / metric["total"], 4) if metric["total"] else 0.0
    return totals


def compare_reports(baseline: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    metric_names = ["synthetic_pass_rate"]
    metric_names.extend(sorted(set(baseline["summary"]["metrics"]) | set(current["summary"]["metrics"])))
    rows = []
    for name in metric_names:
        if name == "synthetic_pass_rate":
            base_rate = baseline["summary"]["pass_rate"]
            cur_rate = current["summary"]["pass_rate"]
            base_count = f"{baseline['summary']['passed']}/{baseline['summary']['total']}"
            cur_count = f"{current['summary']['passed']}/{current['summary']['total']}"
        else:
            base_metric = baseline["summary"]["metrics"].get(name, {"correct": 0, "total": 0, "rate": 0.0})
            cur_metric = current["summary"]["metrics"].get(name, {"correct": 0, "total": 0, "rate": 0.0})
            base_rate = float(base_metric["rate"])
            cur_rate = float(cur_metric["rate"])
            base_count = f"{base_metric['correct']}/{base_metric['total']}"
            cur_count = f"{cur_metric['correct']}/{cur_metric['total']}"
        rows.append({
            "metric": name,
            "baseline_rate": base_rate,
            "current_rate": cur_rate,
            "delta": round(cur_rate - base_rate, 4),
            "baseline_count": base_count,
            "current_count": cur_count,
        })
    return rows


def format_table(rows: list[dict[str, Any]]) -> str:
    headers = ["id", "intent", "action", "result", "failures"]
    table_rows = [
        [
            row["id"],
            row.get("intent") or "-",
            row.get("final_action") or "-",
            "PASS" if row["passed"] else "FAIL",
            ",".join(row["failures"]) if row["failures"] else "-",
        ]
        for row in rows
    ]
    widths = [max(len(headers[i]), *(len(values[i]) for values in table_rows)) for i in range(len(headers))]
    lines = [
        " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))),
        "-+-".join("-" * width for width in widths),
    ]
    lines.extend(" | ".join(values[i].ljust(widths[i]) for i in range(len(headers))) for values in table_rows)
    return "\n".join(lines)


def format_summary(summary: dict[str, Any]) -> str:
    lines = [
        "",
        f"Synthetic Eval Summary ({summary['mode']})",
        "----------------------",
        f"Total cases: {summary['total']}",
        f"Passed: {summary['passed']}",
        f"Failed: {summary['failed']}",
        f"Pass rate: {summary['pass_rate']:.2%}",
        f"Intent distribution: {summary['intent_distribution']}",
        f"Action distribution: {summary['action_distribution']}",
        "",
        "Metrics",
        "-------",
    ]
    for name, metric in summary["metrics"].items():
        lines.append(f"{name}: {metric['correct']}/{metric['total']} ({metric['rate']:.2%})")
    return "\n".join(lines)


def format_comparison(rows: list[dict[str, Any]]) -> str:
    lines = [
        "",
        "Baseline vs Current",
        "-------------------",
        "metric | baseline | current | delta",
        "-------+----------+---------+------",
    ]
    for row in rows:
        delta = row["delta"] * 100
        lines.append(
            f"{row['metric']} | {row['baseline_count']} ({row['baseline_rate']:.2%}) | "
            f"{row['current_count']} ({row['current_rate']:.2%}) | {delta:+.2f}pp"
        )
    return "\n".join(lines)


def write_markdown_report(report: dict[str, Any], comparison: list[dict[str, Any]] | None = None) -> None:
    rows = report["rows"]
    summary = report["summary"]
    lines = [
        "# Synthetic Agent Eval Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "说明：该评测集为自建固定模拟输入集，用于度量固定场景下的 Agent 行为、字段解析和追问逻辑表现，不代表生产环境真实准确率。",
        "",
        "## Summary",
        "",
        f"- Mode: {summary['mode']}",
        f"- Total cases: {summary['total']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Pass rate: {summary['pass_rate']:.2%}",
        f"- Intent distribution: {summary['intent_distribution']}",
        f"- Action distribution: {summary['action_distribution']}",
        "",
        "## Metrics",
        "",
    ]
    for name, metric in summary["metrics"].items():
        lines.append(f"- {name}: {metric['correct']}/{metric['total']} ({metric['rate']:.2%})")

    if comparison:
        lines.extend(["", "## Baseline vs Current", "", "| Metric | Baseline | Current | Delta |", "| --- | --- | --- | --- |"])
        for row in comparison:
            lines.append(
                f"| {row['metric']} | {row['baseline_count']} ({row['baseline_rate']:.2%}) | "
                f"{row['current_count']} ({row['current_rate']:.2%}) | {row['delta'] * 100:+.2f}pp |"
            )

    lines.extend(["", "## Case Results", "", "| id | intent | action | result | failures |", "| --- | --- | --- | --- | --- |"])
    for row in rows:
        failures = "<br>".join(row["failures"]) if row["failures"] else "-"
        result = "PASS" if row["passed"] else "FAIL"
        lines.append(f"| {row['id']} | {row.get('intent') or '-'} | {row.get('final_action') or '-'} | {result} | {failures} |")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DrinkMind synthetic agent eval.")
    parser.add_argument("--write-doc", action="store_true", help="Write docs/synthetic_agent_eval_report.md")
    parser.add_argument("--compare-baseline", action="store_true", help="Run legacy baseline and current parser on the same 100 cases.")
    args = parser.parse_args()

    if args.compare_baseline:
        baseline = run_report(mode="baseline")
        current = run_report(mode="current")
        comparison = compare_reports(baseline, current)
        print(format_summary(baseline["summary"]))
        print(format_summary(current["summary"]))
        print(format_comparison(comparison))
        if args.write_doc:
            write_markdown_report(current, comparison)
            print(f"\nWrote {REPORT_PATH}")
        return 0 if current["summary"]["failed"] == 0 else 1

    report = run_report()
    print(format_table(report["rows"]))
    print(format_summary(report["summary"]))
    if args.write_doc:
        write_markdown_report(report)
        print(f"\nWrote {REPORT_PATH}")
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
