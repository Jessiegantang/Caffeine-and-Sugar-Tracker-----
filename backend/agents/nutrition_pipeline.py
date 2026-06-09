"""Stable nutrition estimation contract for backend callers.

This module coordinates the existing enrichment pipeline with the deterministic
Composition Estimation Agent. It does not read or write persistence directly.
"""

from __future__ import annotations

import json
from typing import Any

from agent import enrich_drink_data
from .composition_agent import estimate_composition_nutrition


KNOWLEDGE_METHODS_TO_KEEP = {"SQL_EXACT_MATCH", "RAG_MATCH"}
FALLBACK_METHODS_TO_REPLACE = {"LLM_ESTIMATION", "LOCAL_ESTIMATOR"}


def estimate_drink_nutrition(drink: dict, db) -> dict:
    """Estimate nutrition and return a stable result contract."""
    enriched = enrich_drink_data(drink, db)
    if not _should_use_composition(enriched):
        return _normalize_result(enriched, used_composition=False)

    try:
        composition_result = estimate_composition_nutrition(drink)
    except Exception as e:
        print(f"[Composition Estimation Error] {e}", flush=True)
        return _normalize_result(enriched, used_composition=False)

    merged = _merge_drink_context(enriched, composition_result, drink)
    return _normalize_result(merged, used_composition=True)


def _should_use_composition(enriched: dict) -> bool:
    method = enriched.get("estimation_method")
    if method in KNOWLEDGE_METHODS_TO_KEEP:
        return False
    if method in FALLBACK_METHODS_TO_REPLACE:
        return True
    if not enriched.get("matched_knowledge_id") and float(enriched.get("confidence") or 0.0) < 0.7:
        return True
    return False


def _merge_drink_context(enriched: dict, nutrition: dict, original: dict) -> dict:
    merged = {**enriched, **nutrition}
    for key in [
        "id",
        "date",
        "brand",
        "name",
        "type",
        "sugar",
        "volume",
        "startTime",
        "endTime",
        "status",
        "alcoholContent",
        "abv",
        "baseSugarDensity",
        "agent_trace_id",
    ]:
        if key in enriched or key in original:
            merged[key] = enriched.get(key, original.get(key))
    return merged


def _normalize_result(result: dict, *, used_composition: bool) -> dict:
    normalized = dict(result)
    normalized["caffeine"] = round(float(normalized.get("caffeine") or 0.0), 1)
    normalized["sugarContent"] = round(float(normalized.get("sugarContent") or 0.0), 1)
    normalized["data_source"] = normalized.get("data_source") or "Unknown"
    normalized["confidence"] = _clamp_confidence(normalized.get("confidence"))
    normalized["reasoning"] = _normalize_reasoning(normalized.get("reasoning"))
    normalized["estimation_method"] = normalized.get("estimation_method") or "UNKNOWN_ESTIMATION"
    normalized["matched_knowledge_id"] = normalized.get("matched_knowledge_id")
    normalized["retrieval_score"] = normalized.get("retrieval_score")
    normalized["composition"] = normalized.get("composition") if used_composition else None
    normalized["explainability"] = _build_explainability(normalized, used_composition=used_composition)
    return normalized


def _build_explainability(result: dict, *, used_composition: bool) -> dict:
    composition = result.get("composition") or {}
    components = composition.get("components") or []
    assumptions = composition.get("assumptions") or []
    warnings = composition.get("warnings") or []
    method = result.get("estimation_method") or "UNKNOWN_ESTIMATION"
    matched_id = result.get("matched_knowledge_id")
    used_knowledge_match = bool(matched_id) or method in KNOWLEDGE_METHODS_TO_KEEP

    return {
        "method": method,
        "used_composition": bool(used_composition),
        "used_knowledge_match": used_knowledge_match,
        "matched_knowledge_id": matched_id,
        "retrieval_score": result.get("retrieval_score"),
        "confidence": result.get("confidence"),
        "reasoning": result.get("reasoning") or [],
        "components": components,
        "assumptions": assumptions,
        "warnings": warnings,
    }


def _normalize_reasoning(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_stringify_reason(reason) for reason in value]
    return [_stringify_reason(value)]


def _stringify_reason(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _clamp_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.0
    return round(max(0.0, min(confidence, 1.0)), 2)
