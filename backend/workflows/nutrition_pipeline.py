"""Stable nutrition estimation contract for backend callers.

This module coordinates the existing enrichment pipeline with the deterministic
Composition Estimation Agent. It does not read or write persistence directly.
"""

from __future__ import annotations

import json
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from knowledge.knowledge_lookup import enrich_drink_data
from rules.composition_agent import decompose_drink, estimate_from_composition


KNOWLEDGE_METHODS_TO_KEEP = {"SQL_EXACT_MATCH", "RAG_MATCH"}
FALLBACK_METHODS_TO_REPLACE = {"LLM_ESTIMATION", "LOCAL_ESTIMATOR"}


class NutritionEstimationState(TypedDict, total=False):
    drink: dict
    db: Any
    normalized_drink: dict
    knowledge_result: dict
    route: str
    composition: dict
    composition_result: dict
    selected_result: dict
    verification: dict
    final_result: dict
    graph_trace: list[str]
    error: str | None
    used_composition: bool


def estimate_drink_nutrition(drink: dict, db) -> dict:
    """Estimate nutrition and return a stable result contract."""
    state = nutrition_graph.invoke({
        "drink": drink,
        "db": db,
        "graph_trace": [],
        "error": None,
    })
    return state["final_result"]


def _normalize_input_node(state: NutritionEstimationState) -> NutritionEstimationState:
    _trace(state, "normalize_input")
    state["normalized_drink"] = dict(state["drink"])
    return state


def _lookup_knowledge_node(state: NutritionEstimationState) -> NutritionEstimationState:
    _trace(state, "lookup_knowledge")
    state["knowledge_result"] = enrich_drink_data(dict(state["normalized_drink"]), state["db"])
    return state


def _route_estimation_node(state: NutritionEstimationState) -> NutritionEstimationState:
    _trace(state, "route_estimation")
    state["route"] = "composition" if _should_use_composition(state["knowledge_result"]) else "knowledge"
    return state


def _use_knowledge_result_node(state: NutritionEstimationState) -> NutritionEstimationState:
    _trace(state, "use_knowledge_result")
    state["selected_result"] = state["knowledge_result"]
    state["used_composition"] = False
    return state


def _composition_decompose_node(state: NutritionEstimationState) -> NutritionEstimationState:
    _trace(state, "composition_decompose")
    try:
        state["composition"] = decompose_drink(state["normalized_drink"])
    except Exception as e:
        _handle_composition_error(state, e)
    return state


def _composition_estimate_node(state: NutritionEstimationState) -> NutritionEstimationState:
    _trace(state, "composition_estimate")
    if state.get("route") != "composition":
        return state

    try:
        estimate = estimate_from_composition(state["composition"])
        composition_with_components = {
            **state["composition"],
            "components": estimate["components"],
        }
        state["composition_result"] = {
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
        state["selected_result"] = _merge_drink_context(
            state["knowledge_result"],
            state["composition_result"],
            state["normalized_drink"],
        )
        state["used_composition"] = True
    except Exception as e:
        _handle_composition_error(state, e)
    return state


def _verify_result_node(state: NutritionEstimationState) -> NutritionEstimationState:
    _trace(state, "verify_result")
    result = state.get("selected_result") or state.get("knowledge_result") or {}
    warnings = list((result.get("composition") or {}).get("warnings") or [])
    issues: list[str] = []

    caffeine = _safe_float(result.get("caffeine"))
    sugar = _safe_float(result.get("sugarContent"))
    if caffeine < 0:
        warnings.append("caffeine is negative")
    if sugar < 0:
        warnings.append("sugarContent is negative")
    if caffeine > 500:
        warnings.append("caffeine exceeds 500mg")
    if sugar > 100:
        warnings.append("sugarContent exceeds 100g")

    method = result.get("estimation_method")
    used_composition = bool(state.get("used_composition"))
    components = ((result.get("composition") or {}).get("components") or [])
    if state.get("route") == "composition" and not components:
        warnings.append("composition route produced no components")
    if used_composition and method != "COMPOSITION_ESTIMATION":
        warnings.append("composition route selected a non-composition method")
    if not used_composition and method == "COMPOSITION_ESTIMATION":
        warnings.append("knowledge route selected a composition method")
    if method in KNOWLEDGE_METHODS_TO_KEEP and result.get("composition") is not None:
        warnings.append("knowledge result should not include composition details")
    if method == "COMPOSITION_ESTIMATION" and result.get("matched_knowledge_id"):
        warnings.append("composition result should not include matched knowledge id")

    state["verification"] = {
        "passed": not issues,
        "warnings": _dedupe_strings(warnings),
        "issues": issues,
    }
    return state


def _build_explainability_node(state: NutritionEstimationState) -> NutritionEstimationState:
    _trace(state, "build_explainability")
    result = state.get("selected_result") or state.get("knowledge_result") or state.get("normalized_drink") or {}
    normalized = _normalize_result(result, used_composition=bool(state.get("used_composition")))
    explainability = normalized.get("explainability") or {}
    verification = state.get("verification") or {"passed": True, "warnings": [], "issues": []}
    existing_warnings = explainability.get("warnings") or []
    explainability["warnings"] = _dedupe_strings(existing_warnings + (verification.get("warnings") or []))
    explainability["graph_trace"] = list(state.get("graph_trace") or [])
    explainability["verification"] = verification
    normalized["explainability"] = explainability
    state["final_result"] = normalized
    return state


def _route_after_decision(state: NutritionEstimationState) -> str:
    return state.get("route") or "knowledge"


def _route_after_decompose(state: NutritionEstimationState) -> str:
    return "fallback_knowledge" if state.get("route") != "composition" else "composition_estimate"


def _handle_composition_error(state: NutritionEstimationState, error: Exception) -> None:
    print(f"[Composition Estimation Error] {error}", flush=True)
    state["error"] = str(error)
    state["route"] = "fallback_knowledge"
    state["selected_result"] = state.get("knowledge_result", {})
    state["used_composition"] = False
    _trace(state, "composition_error")


def _trace(state: NutritionEstimationState, node: str) -> None:
    state.setdefault("graph_trace", []).append(node)


def _build_graph():
    graph = StateGraph(NutritionEstimationState)
    graph.add_node("normalize_input", _normalize_input_node)
    graph.add_node("lookup_knowledge", _lookup_knowledge_node)
    graph.add_node("route_estimation", _route_estimation_node)
    graph.add_node("use_knowledge_result", _use_knowledge_result_node)
    graph.add_node("composition_decompose", _composition_decompose_node)
    graph.add_node("composition_estimate", _composition_estimate_node)
    graph.add_node("verify_result", _verify_result_node)
    graph.add_node("build_explainability", _build_explainability_node)

    graph.add_edge(START, "normalize_input")
    graph.add_edge("normalize_input", "lookup_knowledge")
    graph.add_edge("lookup_knowledge", "route_estimation")
    graph.add_conditional_edges(
        "route_estimation",
        _route_after_decision,
        {
            "knowledge": "use_knowledge_result",
            "composition": "composition_decompose",
        },
    )
    graph.add_conditional_edges(
        "composition_decompose",
        _route_after_decompose,
        {
            "composition_estimate": "composition_estimate",
            "fallback_knowledge": "verify_result",
        },
    )
    graph.add_edge("composition_estimate", "verify_result")
    graph.add_edge("use_knowledge_result", "verify_result")
    graph.add_edge("verify_result", "build_explainability")
    graph.add_edge("build_explainability", END)
    return graph.compile()


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


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _dedupe_strings(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value and value not in deduped:
            deduped.append(value)
    return deduped


nutrition_graph = _build_graph()
