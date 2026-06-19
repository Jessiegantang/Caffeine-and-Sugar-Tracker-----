"""Run fixed effect-eval cases for the DrinkMind agent.

This is intentionally higher level than unit tests. It checks whether the
agent chooses the right action, cites the expected evidence path, keeps risk
judgment sane, and remains stable in offline mode.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.orchestrator import run_agent_orchestrator
from db.database import DrinkKnowledge, DrinkLog, SessionLocal, UserPreference


ROOT_DIR = Path(__file__).resolve().parents[2]
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "agent_effect_eval_cases.json"
REPORT_PATH = ROOT_DIR / "docs" / "agent_effect_eval_report.md"


def load_cases() -> list[dict]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def run_report(*, compare_llm: bool = False) -> dict:
    cases = load_cases()
    original_api_key = os.getenv("OPENAI_API_KEY")
    original_enable_llm = os.getenv("ENABLE_LLM")
    os.environ["OPENAI_API_KEY"] = "dummy_agent_effect_eval_key"
    os.environ["ENABLE_LLM"] = "false"
    os.environ["DRINKMIND_OFFLINE"] = "true"

    rows: list[dict] = []
    try:
        for case in cases:
            rows.append(evaluate_case(case))
    finally:
        if original_api_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = original_api_key
        if original_enable_llm is None:
            os.environ.pop("ENABLE_LLM", None)
        else:
            os.environ["ENABLE_LLM"] = original_enable_llm
        cleanup_cases(cases)

    metrics = _aggregate_metrics(rows)
    summary = {
        "total": len(rows),
        "passed": sum(1 for row in rows if row["passed"]),
        "failed": sum(1 for row in rows if not row["passed"]),
        "intent_distribution": dict(Counter(row["intent"] for row in rows)),
        "action_distribution": dict(Counter(row["final_action"] for row in rows)),
        "metrics": metrics,
        "llm_comparison": "skipped" if not compare_llm else "not_implemented_for_quality_gate",
    }
    return {"rows": rows, "summary": summary}


def evaluate_case(case: dict) -> dict:
    failures: list[str] = []
    expected = case.get("expected", {})

    result = _run_case_once(case)
    failures.extend(_check_expected(case, result))
    metrics = _score_case(case, result)

    if expected.get("offline_stable"):
        second = _run_case_once(case)
        stability_failures = _check_stability(result, second)
        failures.extend(stability_failures)
        metrics["offline_stability"] = {
            "correct": 0 if stability_failures else 1,
            "total": 1,
        }

    return {
        "id": case["id"],
        "intent": result.get("intent"),
        "final_action": result.get("final_action"),
        "risk_level": (result.get("risk_result") or {}).get("risk_level"),
        "nutrition_method": (result.get("nutrition_result") or {}).get("estimation_method"),
        "tools": result.get("tools_used") or [],
        "retrieved_docs": result.get("retrieved_docs") or [],
        "metrics": metrics,
        "passed": not failures,
        "failures": failures,
    }


def _score_case(case: dict, result: dict) -> dict:
    expected = case.get("expected", {})
    parsed = result.get("parsed_drink") or {}
    nutrition = result.get("nutrition_result") or {}
    risk_result = result.get("risk_result") or {}
    explainability = nutrition.get("explainability") or {}
    tools = result.get("tools_used") or []
    trace = explainability.get("graph_trace") or []
    trace_ids = [_trace_id(event) for event in trace]

    metrics: dict[str, dict[str, int]] = {}

    def add_metric(name: str, correct: bool, enabled: bool = True) -> None:
        if enabled:
            metrics[name] = {"correct": 1 if correct else 0, "total": 1}

    add_metric("intent_accuracy", result.get("intent") == expected.get("intent"), expected.get("intent") is not None)
    add_metric(
        "final_action_accuracy",
        result.get("final_action") == expected.get("final_action"),
        expected.get("final_action") is not None,
    )
    add_metric(
        "risk_level_accuracy",
        risk_result.get("risk_level") == expected.get("risk_level"),
        expected.get("risk_level") is not None,
    )
    add_metric(
        "nutrition_method_accuracy",
        nutrition.get("estimation_method") == expected.get("nutrition_method"),
        expected.get("nutrition_method") is not None,
    )
    add_metric(
        "used_composition_accuracy",
        explainability.get("used_composition") == expected.get("used_composition"),
        expected.get("used_composition") is not None,
    )
    add_metric(
        "used_knowledge_match_accuracy",
        explainability.get("used_knowledge_match") == expected.get("used_knowledge_match"),
        expected.get("used_knowledge_match") is not None,
    )

    parsed_fields = expected.get("parsed_fields") or {}
    if parsed_fields:
        correct = sum(1 for key, value in parsed_fields.items() if parsed.get(key) == value)
        metrics["parsed_field_accuracy"] = {"correct": correct, "total": len(parsed_fields)}

    missing_fields = expected.get("required_missing_fields") or []
    if missing_fields:
        actual_missing = parsed.get("missing_fields") or []
        correct = sum(1 for field in missing_fields if field in actual_missing)
        metrics["missing_field_recall"] = {"correct": correct, "total": len(missing_fields)}

    required_tools = expected.get("required_tools") or []
    if required_tools:
        correct = sum(1 for tool in required_tools if tool in tools)
        metrics["required_tool_recall"] = {"correct": correct, "total": len(required_tools)}

    forbidden_tools = expected.get("forbidden_tools") or []
    if forbidden_tools:
        correct = sum(1 for tool in forbidden_tools if tool not in tools)
        metrics["forbidden_tool_accuracy"] = {"correct": correct, "total": len(forbidden_tools)}

    expected_trace_ids = expected.get("trace_ids") or []
    if expected_trace_ids:
        correct = sum(1 for trace_id in expected_trace_ids if trace_id in trace_ids)
        metrics["trace_node_recall"] = {"correct": correct, "total": len(expected_trace_ids)}

    if expected.get("trace_event_shape"):
        required_keys = ["id", "label", "phase", "agent", "status", "summary"]
        valid_events = [
            event
            for event in trace
            if isinstance(event, dict) and all(key in event for key in required_keys)
        ]
        metrics["trace_event_shape_accuracy"] = {
            "correct": len(valid_events),
            "total": len(trace) or 1,
        }

    return metrics


def _aggregate_metrics(rows: list[dict]) -> dict:
    totals: dict[str, dict[str, int | float]] = {}
    for row in rows:
        for name, metric in (row.get("metrics") or {}).items():
            bucket = totals.setdefault(name, {"correct": 0, "total": 0, "rate": 0.0})
            bucket["correct"] += metric.get("correct", 0)
            bucket["total"] += metric.get("total", 0)
    for metric in totals.values():
        total = int(metric["total"])
        correct = int(metric["correct"])
        metric["rate"] = round(correct / total, 4) if total else 0.0
    return totals


def _run_case_once(case: dict) -> dict:
    db = SessionLocal()
    try:
        _reset_case_data(db, case)
        _seed_knowledge(db, case.get("setup_knowledge"))
        _seed_prior_logs(db, case)
        db.commit()
        return run_agent_orchestrator(case["message"], case["date"], db)
    finally:
        db.close()


def _check_expected(case: dict, result: dict) -> list[str]:
    expected = case.get("expected", {})
    failures: list[str] = []

    _expect_equal(failures, "intent", result.get("intent"), expected.get("intent"))
    _expect_equal(failures, "final_action", result.get("final_action"), expected.get("final_action"))
    risk_result = result.get("risk_result") or {}
    _expect_equal(failures, "risk_level", risk_result.get("risk_level"), expected.get("risk_level"))

    tools = result.get("tools_used") or []
    for tool in expected.get("required_tools", []):
        if tool not in tools:
            failures.append(f"missing tool {tool}")
    for tool in expected.get("forbidden_tools", []):
        if tool in tools:
            failures.append(f"forbidden tool present {tool}")

    parsed = result.get("parsed_drink") or {}
    for key, value in (expected.get("parsed_fields") or {}).items():
        if parsed.get(key) != value:
            failures.append(f"parsed.{key} expected {value!r}, got {parsed.get(key)!r}")
    for field in expected.get("required_missing_fields", []):
        if field not in (parsed.get("missing_fields") or []):
            failures.append(f"missing_fields does not include {field}")

    nutrition = result.get("nutrition_result") or {}
    explainability = nutrition.get("explainability") or {}
    _expect_equal(failures, "nutrition_method", nutrition.get("estimation_method"), expected.get("nutrition_method"))
    _expect_equal(failures, "used_composition", explainability.get("used_composition"), expected.get("used_composition"))
    _expect_equal(
        failures,
        "used_knowledge_match",
        explainability.get("used_knowledge_match"),
        expected.get("used_knowledge_match"),
    )

    retrieved_docs = result.get("retrieved_docs") or []
    for doc_id in expected.get("retrieved_docs", []):
        if doc_id not in retrieved_docs:
            failures.append(f"retrieved_docs missing {doc_id}")
    if "retrieved_docs" in expected.get("required_evidence", []) and not retrieved_docs:
        failures.append("expected at least one retrieved_doc evidence id")

    trace = explainability.get("graph_trace") or []
    trace_ids = [_trace_id(event) for event in trace]
    for trace_id in expected.get("trace_ids", []):
        if trace_id not in trace_ids:
            failures.append(f"graph_trace missing {trace_id}")
    if expected.get("trace_event_shape"):
        for event in trace:
            if not isinstance(event, dict):
                failures.append("graph_trace event is not an object")
                continue
            for key in ["id", "label", "phase", "agent", "status", "summary"]:
                if key not in event:
                    failures.append(f"graph_trace event missing {key}")

    response = result.get("final_response") or ""
    for text in expected.get("response_contains", []):
        if text not in response:
            failures.append(f"response missing {text!r}")

    memory_updates = result.get("memory_updates") or {}
    for key, value in (expected.get("required_memory") or {}).items():
        if memory_updates.get(key) != value:
            failures.append(f"memory_updates.{key} expected {value!r}, got {memory_updates.get(key)!r}")

    return failures


def _check_stability(first: dict, second: dict) -> list[str]:
    failures: list[str] = []
    stable_paths = [
        ("intent", first.get("intent"), second.get("intent")),
        ("final_action", first.get("final_action"), second.get("final_action")),
        ("risk_level", (first.get("risk_result") or {}).get("risk_level"), (second.get("risk_result") or {}).get("risk_level")),
        (
            "nutrition_method",
            (first.get("nutrition_result") or {}).get("estimation_method"),
            (second.get("nutrition_result") or {}).get("estimation_method"),
        ),
        ("tools_used", first.get("tools_used"), second.get("tools_used")),
    ]
    for label, left, right in stable_paths:
        if left != right:
            failures.append(f"offline stability mismatch for {label}: {left!r} != {right!r}")
    return failures


def _expect_equal(failures: list[str], label: str, actual: Any, expected: Any) -> None:
    if expected is not None and actual != expected:
        failures.append(f"{label} expected {expected!r}, got {actual!r}")


def _trace_id(event: Any) -> str | None:
    if isinstance(event, dict):
        return event.get("id")
    return event


def _seed_knowledge(db, payload: dict | None) -> None:
    if not payload:
        return
    existing = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == payload["id"]).first()
    if existing:
        db.delete(existing)
        db.commit()
    db.add(DrinkKnowledge(**payload))


def _seed_prior_logs(db, case: dict) -> None:
    for payload in case.get("prior_logs") or []:
        row = {
            "date": case["date"],
            "startTime": "09:00",
            "endTime": "09:10",
            "status": "active",
            "data_source": "eval_fixture",
            "confidence": 1.0,
            **payload,
        }
        db.add(DrinkLog(**row))


def _reset_case_data(db, case: dict) -> None:
    db.query(DrinkLog).filter(DrinkLog.date == case["date"]).delete()
    db.query(UserPreference).delete()
    knowledge_id = (case.get("setup_knowledge") or {}).get("id")
    if knowledge_id:
        existing = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == knowledge_id).first()
        if existing:
            db.delete(existing)
    db.commit()


def cleanup_cases(cases: list[dict]) -> None:
    db = SessionLocal()
    try:
        for case in cases:
            _reset_case_data(db, case)
    finally:
        db.close()


def format_table(rows: list[dict]) -> str:
    headers = ["id", "intent", "action", "risk", "method", "result"]
    table_rows = [
        [
            row["id"],
            row.get("intent") or "-",
            row.get("final_action") or "-",
            row.get("risk_level") or "-",
            row.get("nutrition_method") or "-",
            "PASS" if row["passed"] else "FAIL",
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


def format_summary(summary: dict) -> str:
    lines = [
        "",
        "Summary",
        "-------",
        f"Total cases: {summary['total']}",
        f"Passed: {summary['passed']}",
        f"Failed: {summary['failed']}",
        f"Intent distribution: {summary['intent_distribution']}",
        f"Action distribution: {summary['action_distribution']}",
        "",
        "Metrics",
        "-------",
    ]
    for name, metric in summary.get("metrics", {}).items():
        lines.append(
            f"{name}: {metric['correct']}/{metric['total']} ({metric['rate']:.2%})"
        )
    lines.append(f"LLM comparison: {summary['llm_comparison']}")
    return "\n".join(lines)


def write_markdown_report(report: dict) -> None:
    rows = report["rows"]
    summary = report["summary"]
    lines = [
        "# Agent Effect Eval Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "| id | intent | action | risk | method | result | failures |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        result = "PASS" if row["passed"] else "FAIL"
        failures = "<br>".join(row["failures"]) if row["failures"] else "-"
        lines.append(
            f"| {row['id']} | {row.get('intent') or '-'} | "
            f"{row.get('final_action') or '-'} | {row.get('risk_level') or '-'} | "
            f"{row.get('nutrition_method') or '-'} | {result} | {failures} |"
        )
    lines.extend([
        "",
        "## Summary",
        "",
        f"- Total cases: {summary['total']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Intent distribution: {summary['intent_distribution']}",
        f"- Action distribution: {summary['action_distribution']}",
        f"- LLM comparison: {summary['llm_comparison']}",
        "",
        "## Metrics",
        "",
    ])
    for name, metric in summary.get("metrics", {}).items():
        lines.append(f"- {name}: {metric['correct']}/{metric['total']} ({metric['rate']:.2%})")
    lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DrinkMind agent effect eval.")
    parser.add_argument("--write-doc", action="store_true", help="Write docs/agent_effect_eval_report.md")
    parser.add_argument("--compare-llm", action="store_true", help="Reserved for optional LLM-vs-rule comparison")
    args = parser.parse_args()

    report = run_report(compare_llm=args.compare_llm)
    print(format_table(report["rows"]))
    print(format_summary(report["summary"]))
    for row in report["rows"]:
        if row["failures"]:
            print(f"\n{row['id']} failures:")
            for failure in row["failures"]:
                print(f"  - {failure}")
    if args.write_doc:
        write_markdown_report(report)
        print(f"\nWrote {REPORT_PATH}")
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
