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
from rules.llm_composition_decomposer import (
    composition_llm_enabled,
    decompose_with_llm,
)


KNOWLEDGE_METHODS_TO_KEEP = {"SQL_EXACT_MATCH", "RAG_MATCH"}
FALLBACK_METHODS_TO_REPLACE = {"LLM_ESTIMATION", "LOCAL_ESTIMATOR"}


class NutritionEstimationState(TypedDict, total=False):
    drink: dict
    db: Any
    normalized_drink: dict
    knowledge_result: dict
    route: str
    composition: dict
    composition_fallback_warning: str
    composition_result: dict
    selected_result: dict
    verification: dict
    final_result: dict
    graph_trace: list[Any]
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
    state["normalized_drink"] = dict(state["drink"])
    _trace(
        state,
        "normalize_input",
        phase="输入",
        agent="Input Normalizer",
        summary="保留用户录入的饮品字段，准备进入知识检索。",
        input=_drink_summary(state.get("drink") or {}),
        output=_drink_summary(state["normalized_drink"]),
    )
    return state


def _lookup_knowledge_node(state: NutritionEstimationState) -> NutritionEstimationState:
    state["knowledge_result"] = enrich_drink_data(
        dict(state["normalized_drink"]),
        state["db"],
        allow_llm_fallback=False,
    )
    _trace(
        state,
        "lookup_knowledge",
        phase="检索",
        agent="Knowledge Lookup Agent",
        summary="查询精确知识库和 RAG 候选，得到可复用的营养估算结果。",
        input=_drink_summary(state.get("normalized_drink") or {}),
        output=_result_summary(state["knowledge_result"]),
        confidence=state["knowledge_result"].get("confidence"),
    )
    return state


def _route_estimation_node(state: NutritionEstimationState) -> NutritionEstimationState:
    state["route"] = "composition" if _should_use_composition(state["knowledge_result"]) else "knowledge"
    _trace(
        state,
        "route_estimation",
        phase="决策",
        agent="Estimation Router",
        summary="根据知识库结果的可信度决定直接采用匹配结果，还是进入成分拆解估算。",
        input=_result_summary(state.get("knowledge_result") or {}),
        output={"route": state["route"]},
        decision="进入成分估算" if state["route"] == "composition" else "采用知识库结果",
        confidence=(state.get("knowledge_result") or {}).get("confidence"),
    )
    return state


def _use_knowledge_result_node(state: NutritionEstimationState) -> NutritionEstimationState:
    state["selected_result"] = state["knowledge_result"]
    state["used_composition"] = False
    _trace(
        state,
        "use_knowledge_result",
        phase="选择",
        agent="Knowledge Result Selector",
        summary="知识库匹配足够可信，直接采用该结果作为最终营养估算基础。",
        input=_result_summary(state.get("knowledge_result") or {}),
        output=_result_summary(state["selected_result"]),
        confidence=state["selected_result"].get("confidence"),
    )
    return state


def _composition_decompose_node(state: NutritionEstimationState) -> NutritionEstimationState:
    if state.get("composition"):
        return state

    try:
        state["composition"] = decompose_drink(state["normalized_drink"])
        fallback_warning = state.pop("composition_fallback_warning", None)
        if fallback_warning:
            state["composition"].setdefault("warnings", []).append(fallback_warning)
        state["composition"]["decomposition_source"] = "rule_fallback"
        state["composition"]["llm_decomposition_used"] = False
        _trace(
            state,
            "composition_decompose",
            phase="拆解",
            agent="Rule Composition Fallback",
            summary="LLM 成分拆解不可用时，使用本地名称和类型规则生成兜底成分结构。",
            input=_drink_summary(state.get("normalized_drink") or {}),
            output=_composition_summary(state["composition"]),
            confidence=state["composition"].get("confidence"),
        )
    except Exception as e:
        _handle_composition_error(state, e)
    return state


def _llm_composition_decompose_node(state: NutritionEstimationState) -> NutritionEstimationState:
    if state.get("route") != "composition":
        return state

    if not composition_llm_enabled():
        state["composition"] = None
        _trace(
            state,
            "llm_composition_decompose",
            phase="拆解",
            agent="LLM Composition Decomposer",
            summary="LLM 成分拆解未启用，转入本地规则兜底。",
            input=_drink_summary(state.get("normalized_drink") or {}),
            decision="LLM 未启用，使用规则兜底",
        )
        return state

    try:
        state["composition"] = decompose_with_llm(state["normalized_drink"])
        _trace(
            state,
            "llm_composition_decompose",
            phase="拆解",
            agent="LLM Composition Decomposer",
            summary="优先让 LLM 把饮品拆成结构化成分；最终咖啡因和糖分仍由确定性规则换算。",
            input=_drink_summary(state.get("normalized_drink") or {}),
            output=_composition_summary(state["composition"]),
            decision="采用 LLM 成分结构",
            confidence=state["composition"].get("confidence"),
        )
    except Exception as e:
        state["composition"] = None
        state["composition_fallback_warning"] = (
            "LLM composition decomposition did not finish; using rule-based decomposition."
        )
        _trace(
            state,
            "llm_composition_decompose",
            phase="拆解",
            agent="LLM Composition Decomposer",
            summary="LLM 成分拆解未完成，转入本地规则兜底。",
            output={"error": str(e)},
            decision="LLM 失败，使用规则兜底",
            status="warning",
        )
    return state


def _composition_estimate_node(state: NutritionEstimationState) -> NutritionEstimationState:
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
        _trace(
            state,
            "composition_estimate",
            phase="估算",
            agent="Composition Estimation Agent",
            summary="按成分范围累计咖啡因和糖分，并给出当前最可能估算值。",
            input=_composition_summary(state.get("composition") or {}),
            output=_result_summary(state["composition_result"]),
            confidence=state["composition_result"].get("confidence"),
        )
    except Exception as e:
        _handle_composition_error(state, e)
    return state


def _verify_result_node(state: NutritionEstimationState) -> NutritionEstimationState:
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
    _trace(
        state,
        "verify_result",
        phase="校验",
        agent="Result Verifier",
        summary="检查数值范围、路由一致性和成分结果完整性。",
        input=_result_summary(result),
        output=state["verification"],
        status="warning" if state["verification"]["warnings"] else "completed",
    )
    return state


def _build_explainability_node(state: NutritionEstimationState) -> NutritionEstimationState:
    result = state.get("selected_result") or state.get("knowledge_result") or state.get("normalized_drink") or {}
    normalized = _normalize_result(result, used_composition=bool(state.get("used_composition")))
    explainability = normalized.get("explainability") or {}
    verification = state.get("verification") or {"passed": True, "warnings": [], "issues": []}
    existing_warnings = explainability.get("warnings") or []
    explainability["warnings"] = _dedupe_strings(existing_warnings + (verification.get("warnings") or []))
    explainability["verification"] = verification
    normalized["explainability"] = explainability
    state["final_result"] = normalized
    _trace(
        state,
        "build_explainability",
        phase="输出",
        agent="Explainability Builder",
        summary="组装前端展示所需的解释性字段、证据和流程 trace。",
        input=_result_summary(result),
        output=_result_summary(normalized),
        confidence=normalized.get("confidence"),
    )
    explainability["graph_trace"] = list(state.get("graph_trace") or [])
    return state


def _route_after_decision(state: NutritionEstimationState) -> str:
    return state.get("route") or "knowledge"


def _route_after_llm_decompose(state: NutritionEstimationState) -> str:
    if state.get("route") != "composition":
        return "fallback_knowledge"
    return "composition_estimate" if state.get("composition") else "composition_decompose"


def _route_after_rule_decompose(state: NutritionEstimationState) -> str:
    if state.get("route") != "composition" or not state.get("composition"):
        return "fallback_knowledge"
    return "composition_estimate"


def _handle_composition_error(state: NutritionEstimationState, error: Exception) -> None:
    print(f"[Composition Estimation Error] {error}", flush=True)
    state["error"] = str(error)
    state["route"] = "fallback_knowledge"
    state["selected_result"] = state.get("knowledge_result", {})
    state["used_composition"] = False
    _trace(
        state,
        "composition_error",
        phase="异常",
        agent="Composition Agent",
        summary="成分估算失败，回退到知识库或兜底结果。",
        output={"error": str(error), "route": state["route"]},
        status="error",
    )


def _trace(
    state: NutritionEstimationState,
    node: str,
    *,
    phase: str,
    agent: str,
    summary: str,
    input: dict | None = None,
    output: dict | None = None,
    decision: str | None = None,
    confidence: Any = None,
    status: str = "completed",
) -> None:
    event = {
        "id": node,
        "label": TRACE_LABELS.get(node, node),
        "phase": phase,
        "agent": agent,
        "status": status,
        "summary": summary,
    }
    if input is not None:
        event["input"] = input
    if output is not None:
        event["output"] = output
    if decision:
        event["decision"] = decision
    if confidence is not None:
        event["confidence"] = _clamp_confidence(confidence)
    state.setdefault("graph_trace", []).append(event)


TRACE_LABELS = {
    "normalize_input": "标准化输入",
    "lookup_knowledge": "知识库检索",
    "route_estimation": "路由决策",
    "use_knowledge_result": "采用知识结果",
    "composition_decompose": "成分拆解",
    "llm_composition_decompose": "LLM 成分拆解",
    "composition_estimate": "成分估算",
    "composition_error": "成分估算异常",
    "verify_result": "结果校验",
    "build_explainability": "生成解释",
}


def _drink_summary(drink: dict) -> dict:
    return _drop_empty({
        "brand": drink.get("brand"),
        "name": drink.get("name"),
        "type": drink.get("type"),
        "volume_ml": drink.get("volume"),
        "sugar": drink.get("sugar"),
    })


def _result_summary(result: dict) -> dict:
    return _drop_empty({
        "method": result.get("estimation_method"),
        "source": result.get("data_source"),
        "caffeine_mg": result.get("caffeine"),
        "sugar_g": result.get("sugarContent"),
        "confidence": result.get("confidence"),
        "matched_knowledge_id": result.get("matched_knowledge_id"),
        "retrieval_score": result.get("retrieval_score"),
        "components": len((result.get("composition") or {}).get("components") or []),
    })


def _composition_summary(composition: dict) -> dict:
    return _drop_empty({
        "drink_type": composition.get("drink_type"),
        "espresso_shots": composition.get("espresso_shots"),
        "tea_base_volume_ml": composition.get("tea_base_volume_ml"),
        "milk_volume_ml": composition.get("milk_volume_ml"),
        "fruit_base_volume_ml": composition.get("fruit_base_volume_ml"),
        "syrup_pumps": composition.get("syrup_pumps"),
        "sweetness_level": composition.get("sweetness_level"),
        "decomposition_source": composition.get("decomposition_source"),
        "llm_decomposition_used": composition.get("llm_decomposition_used"),
        "confidence": composition.get("confidence"),
        "assumptions": composition.get("assumptions"),
        "warnings": composition.get("warnings"),
    })


def _drop_empty(values: dict) -> dict:
    return {
        key: value
        for key, value in values.items()
        if value is not None and value != "" and value != [] and value != {}
    }


def _build_graph():
    graph = StateGraph(NutritionEstimationState)
    graph.add_node("normalize_input", _normalize_input_node)
    graph.add_node("lookup_knowledge", _lookup_knowledge_node)
    graph.add_node("route_estimation", _route_estimation_node)
    graph.add_node("use_knowledge_result", _use_knowledge_result_node)
    graph.add_node("composition_decompose", _composition_decompose_node)
    graph.add_node("llm_composition_decompose", _llm_composition_decompose_node)
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
            "composition": "llm_composition_decompose",
        },
    )
    graph.add_conditional_edges(
        "llm_composition_decompose",
        _route_after_llm_decompose,
        {
            "composition_estimate": "composition_estimate",
            "composition_decompose": "composition_decompose",
            "fallback_knowledge": "verify_result",
        },
    )
    graph.add_conditional_edges(
        "composition_decompose",
        _route_after_rule_decompose,
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
