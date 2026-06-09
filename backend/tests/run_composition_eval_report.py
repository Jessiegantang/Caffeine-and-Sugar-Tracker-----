"""Print a human-readable Composition Estimation eval report.

This script is intentionally separate from unittest. The regression gate lives
in test_composition_eval.py; this report is for inspecting rule changes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import agent as legacy_agent
from agents.nutrition_pipeline import estimate_drink_nutrition
from database import DrinkKnowledge, SessionLocal


ROOT_DIR = Path(__file__).resolve().parents[2]
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "composition_eval_cases.json"
REPORT_PATH = ROOT_DIR / "docs" / "composition_eval_report.md"


class DisabledLLM:
    def with_structured_output(self, *args, **kwargs):
        raise RuntimeError("LLM disabled for deterministic composition eval report")


def load_cases() -> list[dict]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def seed_knowledge(db, payload: dict | None) -> None:
    if not payload:
        return
    existing = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == payload["id"]).first()
    if existing:
        db.delete(existing)
        db.commit()
    db.add(DrinkKnowledge(**payload))
    db.commit()


def cleanup_knowledge(db, cases: list[dict]) -> None:
    ids = [
        case.get("setup_knowledge", {}).get("id")
        for case in cases
        if case.get("setup_knowledge", {}).get("id")
    ]
    if not ids:
        return
    for row in db.query(DrinkKnowledge).filter(DrinkKnowledge.id.in_(ids)).all():
        db.delete(row)
    db.commit()


def evaluate_case(case: dict) -> dict:
    db = SessionLocal()
    try:
        seed_knowledge(db, case.get("setup_knowledge"))
        result = estimate_drink_nutrition(case["input"], db)
    finally:
        db.close()

    expected = case["expected"]
    explainability = result.get("explainability") or {}
    composition = result.get("composition") or {}
    components = composition.get("components") or explainability.get("components") or []
    component_names = {component.get("name") for component in components}
    caffeine = result.get("caffeine")
    sugar = result.get("sugarContent")
    confidence = result.get("confidence")

    checks = [
        result.get("estimation_method") == expected["method"],
        explainability.get("used_composition") == expected["used_composition"],
        expected.get("drink_type") is None or composition.get("drink_type") == expected["drink_type"],
        all(name in component_names for name in expected.get("required_components", [])),
        expected["caffeine_range"][0] <= caffeine <= expected["caffeine_range"][1],
        expected["sugar_range"][0] <= sugar <= expected["sugar_range"][1],
        confidence >= expected["min_confidence"],
        isinstance(result.get("reasoning"), list),
        bool(explainability),
    ]
    if "used_knowledge_match" in expected:
        checks.append(explainability.get("used_knowledge_match") == expected["used_knowledge_match"])

    return {
        "id": case["id"],
        "expected_method": expected["method"],
        "actual_method": result.get("estimation_method"),
        "used_composition": explainability.get("used_composition"),
        "used_knowledge_match": explainability.get("used_knowledge_match"),
        "drink_type": composition.get("drink_type"),
        "caffeine": caffeine,
        "sugarContent": sugar,
        "confidence": confidence,
        "passed": all(checks),
    }


def run_report() -> dict:
    cases = load_cases()
    original_vectorstore = legacy_agent.vectorstore
    original_retriever = legacy_agent.retriever
    original_llm = legacy_agent.llm
    legacy_agent.vectorstore = None
    legacy_agent.retriever = None
    legacy_agent.llm = DisabledLLM()

    try:
        rows = [evaluate_case(case) for case in cases]
    finally:
        db = SessionLocal()
        try:
            cleanup_knowledge(db, cases)
        finally:
            db.close()
        legacy_agent.vectorstore = original_vectorstore
        legacy_agent.retriever = original_retriever
        legacy_agent.llm = original_llm

    summary = {
        "total": len(rows),
        "passed": sum(1 for row in rows if row["passed"]),
        "failed": sum(1 for row in rows if not row["passed"]),
        "method_distribution": dict(Counter(row["actual_method"] for row in rows)),
        "composition_used_count": sum(1 for row in rows if row["used_composition"]),
        "knowledge_match_count": sum(1 for row in rows if row["used_knowledge_match"]),
    }
    return {"rows": rows, "summary": summary}


def format_table(rows: list[dict]) -> str:
    headers = [
        "id",
        "expected",
        "actual",
        "composition",
        "knowledge",
        "drink_type",
        "caffeine",
        "sugar",
        "confidence",
        "result",
    ]
    table_rows = [
        [
            row["id"],
            row["expected_method"],
            row["actual_method"],
            str(row["used_composition"]),
            str(row["used_knowledge_match"]),
            row["drink_type"] or "-",
            str(row["caffeine"]),
            str(row["sugarContent"]),
            str(row["confidence"]),
            "PASS" if row["passed"] else "FAIL",
        ]
        for row in rows
    ]
    widths = [
        max(len(headers[i]), *(len(values[i]) for values in table_rows))
        for i in range(len(headers))
    ]
    lines = [
        " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))),
        "-+-".join("-" * width for width in widths),
    ]
    lines.extend(
        " | ".join(values[i].ljust(widths[i]) for i in range(len(headers)))
        for values in table_rows
    )
    return "\n".join(lines)


def format_summary(summary: dict) -> str:
    method_distribution = ", ".join(
        f"{method}: {count}" for method, count in sorted(summary["method_distribution"].items())
    )
    return "\n".join(
        [
            "",
            "Summary",
            "-------",
            f"Total cases: {summary['total']}",
            f"Passed: {summary['passed']}",
            f"Failed: {summary['failed']}",
            f"Method distribution: {method_distribution}",
            f"Composition-used count: {summary['composition_used_count']}",
            f"Knowledge-match count: {summary['knowledge_match_count']}",
        ]
    )


def write_markdown_report(report: dict) -> None:
    rows = report["rows"]
    summary = report["summary"]
    lines = [
        "# Composition Eval Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "This report is a human-readable snapshot. The unittest suite remains the regression gate.",
        "",
        "| id | expected | actual | composition | knowledge | drink_type | caffeine | sugar | confidence | result |",
        "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| {id} | {expected_method} | {actual_method} | {used_composition} | "
            "{used_knowledge_match} | {drink_type} | {caffeine} | {sugarContent} | "
            "{confidence} | {result} |".format(
                **row,
                drink_type=row["drink_type"] or "-",
                result="PASS" if row["passed"] else "FAIL",
            )
        )
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Total cases: {summary['total']}",
            f"- Passed: {summary['passed']}",
            f"- Failed: {summary['failed']}",
            f"- Method distribution: {summary['method_distribution']}",
            f"- Composition-used count: {summary['composition_used_count']}",
            f"- Knowledge-match count: {summary['knowledge_match_count']}",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Composition Estimation eval report.")
    parser.add_argument("--write-doc", action="store_true", help="Write docs/composition_eval_report.md")
    args = parser.parse_args()

    report = run_report()
    print(format_table(report["rows"]))
    print(format_summary(report["summary"]))
    if args.write_doc:
        write_markdown_report(report)
        print(f"\nWrote {REPORT_PATH}")
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
