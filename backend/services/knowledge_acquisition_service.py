from fastapi import HTTPException

from knowledge.knowledge_acquisition_agent import (
    add_nutrition_evidence,
    analyze_image_with_vision,
    approve_evidence_to_knowledge,
    create_manual_candidate,
    is_allowed_source,
    serialize_candidate,
    serialize_evidence,
    stage_image_items,
)
from db.database import NutritionEvidence, ProductCandidate
from services.knowledge_service import serialize_knowledge, sync_approved_knowledge


def list_product_candidates(db, status: str = None, limit: int = 50) -> dict:
    limit = max(1, min(limit, 100))
    query = db.query(ProductCandidate).order_by(ProductCandidate.created_at.desc())
    if status:
        query = query.filter(ProductCandidate.status == status)
    else:
        query = query.filter(ProductCandidate.status.notin_(["imported", "deleted"]))
    candidates = query.limit(limit).all()
    return {"status": "success", "candidates": [serialize_candidate(candidate) for candidate in candidates]}


def create_product_candidate(db, input_data) -> dict:
    if input_data.source_url and not is_allowed_source(input_data.source_url):
        raise HTTPException(status_code=400, detail="Source domain is blocked by acquisition policy")
    candidate = create_manual_candidate(db, input_data.dict())
    return {"status": "success", "candidate": serialize_candidate(candidate)}


def analyze_acquisition_image(image_bytes: bytes, content_type: str, filename: str | None = None) -> dict:
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported")
    if len(image_bytes) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image is too large; max size is 8MB")
    result = analyze_image_with_vision(image_bytes, content_type, filename)
    return {"status": "success", **result}


def import_acquisition_image_items(db, input_data) -> dict:
    result = stage_image_items(db, input_data.items, input_data.source_type)
    return {"status": "success", **result}


def list_nutrition_evidence(db, candidate_id: str = None, limit: int = 50) -> dict:
    limit = max(1, min(limit, 100))
    query = db.query(NutritionEvidence).order_by(NutritionEvidence.created_at.desc())
    if candidate_id:
        query = query.filter(NutritionEvidence.candidate_id == candidate_id)
    else:
        query = query.filter(NutritionEvidence.status.notin_(["approved", "deleted"]))
    evidence_rows = query.limit(limit).all()
    return {"status": "success", "evidence": [serialize_evidence(row) for row in evidence_rows]}


def create_candidate_evidence(db, candidate_id: str, input_data) -> dict:
    if input_data.source_url and not is_allowed_source(input_data.source_url):
        raise HTTPException(status_code=400, detail="Source domain is blocked by acquisition policy")
    try:
        evidence = add_nutrition_evidence(db, candidate_id, input_data.dict())
        return {"status": "success", "evidence": serialize_evidence(evidence)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


def approve_candidate_evidence(db, evidence_id: str) -> dict:
    try:
        kb = approve_evidence_to_knowledge(db, evidence_id)
        sync_approved_knowledge(kb)
        return {"status": "success", "knowledge": serialize_knowledge(kb)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def approve_candidate_evidence_bulk(db, input_data) -> dict:
    approved = []
    errors = []
    for evidence_id in input_data.ids:
        try:
            kb = approve_evidence_to_knowledge(db, evidence_id)
            sync_approved_knowledge(kb)
            approved.append(kb.id)
        except ValueError as e:
            errors.append({"id": evidence_id, "error": str(e)})
    return {"status": "success", "approved": approved, "errors": errors}


def delete_candidate_evidence(db, evidence_id: str) -> dict:
    evidence = db.query(NutritionEvidence).filter(NutritionEvidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    evidence.status = "deleted"
    db.commit()
    return {"status": "success"}


def delete_candidate_evidence_bulk(db, input_data) -> dict:
    rows = db.query(NutritionEvidence).filter(NutritionEvidence.id.in_(input_data.ids)).all()
    for row in rows:
        row.status = "deleted"
    db.commit()
    return {"status": "success", "deleted": len(rows)}


def delete_product_candidate(db, candidate_id: str) -> dict:
    candidate = db.query(ProductCandidate).filter(ProductCandidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    candidate.status = "deleted"
    evidence_rows = db.query(NutritionEvidence).filter(NutritionEvidence.candidate_id == candidate_id).all()
    for row in evidence_rows:
        row.status = "deleted"
    db.commit()
    return {"status": "success"}


def delete_product_candidate_bulk(db, input_data) -> dict:
    candidates = db.query(ProductCandidate).filter(ProductCandidate.id.in_(input_data.ids)).all()
    for candidate in candidates:
        candidate.status = "deleted"
    evidence_rows = db.query(NutritionEvidence).filter(NutritionEvidence.candidate_id.in_(input_data.ids)).all()
    for row in evidence_rows:
        row.status = "deleted"
    db.commit()
    return {"status": "success", "deleted": len(candidates)}
