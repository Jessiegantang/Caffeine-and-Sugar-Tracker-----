import json
from typing import Any, Dict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from agents.knowledge_acquisition_agent import (
    add_nutrition_evidence,
    create_manual_candidate,
    serialize_candidate,
    serialize_evidence,
)
from database import DrinkLog, ProductCandidate
from services.drink_log_service import safe_json_loads, serialize_drink_log


KNOWN_DRINK_TYPES = {"coffee", "teacoffee", "tea", "milktea", "fruittea", "soda", "alcohol"}


def _numeric_delta(previous, corrected) -> float:
    return round(float(corrected or 0) - float(previous or 0), 1)


def _feedback_delta(previous: Dict[str, Any], corrected: Dict[str, Any]) -> Dict[str, Any]:
    delta = {}
    for key in ["volume", "caffeine", "sugarContent"]:
        delta[key] = _numeric_delta(previous.get(key), corrected.get(key))
    for key in ["brand", "name", "type"]:
        if previous.get(key) != corrected.get(key):
            delta[key] = {"from": previous.get(key), "to": corrected.get(key)}
    return delta


def _is_high_feedback_delta(delta: Dict[str, Any]) -> bool:
    return (
        abs(float(delta.get("caffeine") or 0)) >= 100
        or abs(float(delta.get("sugarContent") or 0)) >= 20
        or abs(float(delta.get("volume") or 0)) >= 250
    )


def validate_feedback(input_data) -> Dict[str, Any]:
    corrected = input_data.corrected.dict()
    errors = []
    if not corrected.get("name"):
        errors.append("name is required")
    if corrected.get("type") not in KNOWN_DRINK_TYPES:
        errors.append("type must be a known drink type")
    if not 10 <= corrected.get("volume") <= 2000:
        errors.append("volume must be between 10 and 2000ml")
    if not 0 <= corrected.get("caffeine") <= 800:
        errors.append("caffeine must be between 0 and 800mg")
    if not 0 <= corrected.get("sugarContent") <= 150:
        errors.append("sugarContent must be between 0 and 150g")
    if input_data.submit_as_evidence and not (input_data.source_note or "").strip():
        errors.append("source_note is required when submit_as_evidence is true")
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    return corrected


def find_reusable_feedback_candidate(db: Session, corrected: Dict[str, Any]):
    query = db.query(ProductCandidate).filter(
        ProductCandidate.name == corrected.get("name"),
        ProductCandidate.status.notin_(["imported", "deleted"]),
    )
    brand = corrected.get("brand")
    if brand:
        query = query.filter(ProductCandidate.brand == brand)
    else:
        query = query.filter(ProductCandidate.brand.is_(None))
    candidate = query.first()
    if candidate and (candidate.type or corrected.get("type")) == corrected.get("type"):
        return candidate
    return None


def feedback_raw_evidence(log_id: str, corrected: Dict[str, Any], source_note: str) -> str:
    return (
        f"user feedback for log_id={log_id} "
        f"brand: {corrected.get('brand') or ''} "
        f"name: {corrected.get('name')} "
        f"volume: {corrected.get('volume')}ml "
        f"caffeine: {corrected.get('caffeine')}mg "
        f"sugar: {corrected.get('sugarContent')}g "
        f"note: {(source_note or '').strip()}"
    )


def submit_nutrition_feedback(db: Session, log_id: str, input_data) -> Dict[str, Any]:
    db_log = db.query(DrinkLog).filter(DrinkLog.id == log_id).first()
    if not db_log:
        raise HTTPException(status_code=404, detail="Log not found")

    corrected = validate_feedback(input_data)
    previous = {
        "brand": db_log.brand,
        "name": db_log.name,
        "type": db_log.type,
        "volume": db_log.volume,
        "caffeine": db_log.caffeine,
        "sugarContent": db_log.sugarContent,
    }
    delta = _feedback_delta(previous, corrected)
    high_delta = _is_high_feedback_delta(delta)

    if input_data.apply_to_log:
        db_log.brand = corrected.get("brand")
        db_log.name = corrected.get("name")
        db_log.type = corrected.get("type")
        db_log.volume = corrected.get("volume")
        db_log.caffeine = corrected.get("caffeine")
        db_log.sugarContent = corrected.get("sugarContent")
        explainability = safe_json_loads(db_log.explainability_json, {})
        if not isinstance(explainability, dict):
            explainability = {}
        explainability["feedback"] = {
            "corrected": corrected,
            "source_note": input_data.source_note,
            "source_type": input_data.source_type or "user_feedback",
            "previous": previous,
            "delta": delta,
            "high_delta": high_delta,
        }
        db_log.explainability_json = json.dumps(explainability, ensure_ascii=False)

    candidate = None
    evidence = None
    if input_data.submit_as_evidence:
        candidate = find_reusable_feedback_candidate(db, corrected)
        if not candidate:
            candidate = create_manual_candidate(db, {
                "brand": corrected.get("brand"),
                "name": corrected.get("name"),
                "type": corrected.get("type"),
                "source_title": "User nutrition feedback",
                "source_snippet": input_data.source_note,
                "discovery_method": "user_feedback",
                "status": "pending_review",
                "confidence": 0.6,
            })
        evidence = add_nutrition_evidence(db, candidate.id, {
            "source_type": "user_feedback",
            "source_url": None,
            "raw_evidence": feedback_raw_evidence(log_id, corrected, input_data.source_note),
        })

    db.commit()
    db.refresh(db_log)
    if candidate:
        db.refresh(candidate)
    if evidence:
        db.refresh(evidence)

    return {
        "status": "success",
        "log": serialize_drink_log(db_log),
        "candidate": serialize_candidate(candidate) if candidate else None,
        "evidence": serialize_evidence(evidence) if evidence else None,
    }
