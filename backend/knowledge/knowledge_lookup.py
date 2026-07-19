"""Nutrition knowledge lookup for the LangGraph estimation workflow.

This module only retrieves verified SQL/RAG fields. It intentionally does not
estimate missing caffeine or sugar values; missing fields are completed by the
composition-agent branch in ``workflows.nutrition_pipeline``.
"""

from __future__ import annotations

import re
import uuid

from db.database import DrinkKnowledge
from knowledge.rag_store import vectorstore


BRAND_CANONICAL_KEYS = {
    "瑞幸咖啡": "luckin",
    "瑞幸": "luckin",
    "luckin coffee": "luckin",
    "luckin": "luckin",
    "库迪咖啡": "cotti",
    "库迪": "cotti",
    "cotti coffee": "cotti",
    "cotti": "cotti",
    "星巴克": "starbucks",
    "星巴克中国": "starbucks",
    "starbucks": "starbucks",
    "喜茶": "heytea",
    "heytea": "heytea",
    "奈雪": "nayuki",
    "奈雪的茶": "nayuki",
    "nayuki": "nayuki",
}


def _knowledge_scope(source: str | None) -> str:
    source = source or ""
    if "caffeine_sugar" in source:
        return "caffeine_sugar"
    if "caffeine_only" in source:
        return "caffeine_only"
    if "sugar_only" in source:
        return "sugar_only"
    if "partial" in source:
        return "partial"
    if "complete" in source:
        return "complete"
    return "inferred"


def _knowledge_field_known(scope: str, field_name: str, value=None) -> bool:
    if scope in {"complete", "caffeine_sugar"}:
        return True
    if scope == "caffeine_only":
        return field_name == "caffeine"
    if scope == "sugar_only":
        return field_name == "sugar"
    if scope in {"partial", "inferred"}:
        return value is not None and float(value or 0) > 0
    return False


def _normalize_match_name(name: str | None) -> str:
    normalized = re.sub(r"\s+", "", name or "").lower()
    for token in ["咖啡", "饮品", "冷饮", "热饮", "标准杯", "默认杯型"]:
        normalized = normalized.replace(token, "")
    return normalized


def _brand_key(brand: str | None) -> str:
    normalized = re.sub(r"\s+", " ", (brand or "").strip().lower())
    if normalized in BRAND_CANONICAL_KEYS:
        return BRAND_CANONICAL_KEYS[normalized]
    compact = normalized.replace(" ", "")
    for alias, key in BRAND_CANONICAL_KEYS.items():
        if alias.lower().replace(" ", "") == compact:
            return key
    return compact


def _find_sql_knowledge_match(db, brand: str, name: str):
    exact = db.query(DrinkKnowledge).filter(
        DrinkKnowledge.brand == brand,
        DrinkKnowledge.name == name,
    ).first()
    if exact:
        return exact

    query_name = _normalize_match_name(name)
    if not query_name:
        return None
    query_brand_key = _brand_key(brand)
    rows = db.query(DrinkKnowledge).all()
    for row in rows:
        if _brand_key(row.brand) != query_brand_key:
            continue
        row_name = _normalize_match_name(row.name)
        if row_name and (row_name == query_name or row_name in query_name or query_name in row_name):
            return row
    return None


def _build_knowledge_result(
    drink: dict,
    *,
    caffeine,
    sugar,
    source: str,
    method: str,
    matched_id: str | None,
    retrieval_score,
    reference_volume,
) -> dict:
    result = dict(drink)
    scope = _knowledge_scope(source)
    caffeine_known = _knowledge_field_known(scope, "caffeine", caffeine)
    sugar_known = _knowledge_field_known(scope, "sugar", sugar)
    target_volume = float(result.get("volume") or 500)
    source_volume = float(reference_volume or 500)
    ratio = target_volume / source_volume if source_volume else 1.0

    result.update({
        "caffeine": round(float(caffeine or 0) * ratio, 1) if caffeine_known else None,
        # Stored sugar is the normal-sugar total for the reference product.
        "sugarContent": round(float(sugar or 0) * ratio, 1) if sugar_known else None,
        "data_source": source,
        "reasoning": [
            f"{method} matched {matched_id or 'RAG document'}; "
            f"known fields: caffeine={caffeine_known}, sugar={sugar_known}; "
            f"scaled to {target_volume:g}ml."
        ],
        "estimation_method": method,
        "matched_knowledge_id": matched_id,
        "retrieval_score": retrieval_score,
        "knowledge_fields": {
            "caffeine": caffeine_known,
            "sugar": sugar_known,
            "scope": scope,
        },
    })
    return result


def _no_knowledge_result(drink: dict) -> dict:
    result = dict(drink)
    result.update({
        "caffeine": None,
        "sugarContent": None,
        "data_source": "No knowledge match",
        "reasoning": ["No SQL or RAG nutrition match; missing fields require composition analysis."],
        "estimation_method": "NO_KNOWLEDGE_MATCH",
        "matched_knowledge_id": None,
        "retrieval_score": None,
        "knowledge_fields": {"caffeine": False, "sugar": False, "scope": "none"},
    })
    return result


def enrich_drink_data(r: dict, db) -> dict:
    """Retrieve SQL/RAG nutrition fields without estimating missing values."""
    result = dict(r)
    result["agent_trace_id"] = result.get("agent_trace_id") or f"trace_{uuid.uuid4().hex[:12]}"
    brand = str(result.get("brand") or "")
    name = str(result.get("name") or "")

    sql_match = _find_sql_knowledge_match(db, brand, name)
    if sql_match:
        return _build_knowledge_result(
            result,
            caffeine=sql_match.caffeine,
            sugar=sql_match.baseSugar,
            source=sql_match.source or "SQL knowledge base",
            method="SQL_EXACT_MATCH",
            matched_id=sql_match.id,
            retrieval_score=None,
            reference_volume=sql_match.volume,
        )

    if vectorstore:
        try:
            matches = vectorstore.similarity_search_with_score(f"{brand} {name}", k=1)
            if matches:
                document, score = matches[0]
                metadata = document.metadata
                matched_name = str(metadata.get("name") or "")
                query_chars = set(name.replace(" ", ""))
                matched_chars = set(matched_name.replace(" ", ""))
                overlap = len(query_chars.intersection(matched_chars))
                brand_matches = bool(brand) and _brand_key(brand) == _brand_key(metadata.get("brand"))
                if brand_matches and (overlap >= 1 or float(score) < 0.3):
                    return _build_knowledge_result(
                        result,
                        caffeine=metadata.get("caffeine"),
                        sugar=metadata.get("sugar"),
                        source=metadata.get("source") or "RAG vector match",
                        method="RAG_MATCH",
                        matched_id=metadata.get("id"),
                        retrieval_score=float(score),
                        reference_volume=metadata.get("volume", 500),
                    )
        except Exception as error:
            print(f"[RAG Error] {error}", flush=True)

    return _no_knowledge_result(result)
