from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from api.schemas import BulkIdsInput, CandidateInput, EvidenceInput, ImageImportInput, KnowledgeInput, TextAnalyzeInput
from db.database import get_db
from services import knowledge_acquisition_service, knowledge_service


router = APIRouter()


@router.get("/api/knowledge_base")
def get_knowledge_base(db: Session = Depends(get_db)):
    return knowledge_service.list_knowledge(db)


@router.post("/api/knowledge_base")
def add_knowledge(kb: KnowledgeInput, db: Session = Depends(get_db)):
    return knowledge_service.create_knowledge(db, kb)


@router.put("/api/knowledge_base/{kb_id}")
def update_knowledge(kb_id: str, kb: KnowledgeInput, db: Session = Depends(get_db)):
    return knowledge_service.update_knowledge(db, kb_id, kb)


@router.delete("/api/knowledge_base/{kb_id}")
def delete_knowledge(kb_id: str, db: Session = Depends(get_db)):
    return knowledge_service.delete_knowledge(db, kb_id)


# --- Knowledge Acquisition Agent Endpoints ---

@router.get("/api/knowledge/acquisition/candidates")
def list_product_candidates(status: str = None, limit: int = 50, db: Session = Depends(get_db)):
    return knowledge_acquisition_service.list_product_candidates(db, status, limit)


@router.post("/api/knowledge/acquisition/candidates")
def create_product_candidate(input_data: CandidateInput, db: Session = Depends(get_db)):
    return knowledge_acquisition_service.create_product_candidate(db, input_data)


@router.post("/api/knowledge/acquisition/image/analyze")
async def analyze_acquisition_image(file: UploadFile = File(...), context_text: str = Form("")):
    content_type = file.content_type or ""
    image_bytes = await file.read()
    return knowledge_acquisition_service.analyze_acquisition_image(image_bytes, content_type, file.filename, context_text)


@router.post("/api/knowledge/acquisition/image/import")
def import_acquisition_image_items(input_data: ImageImportInput, db: Session = Depends(get_db)):
    return knowledge_acquisition_service.import_acquisition_image_items(db, input_data)


@router.post("/api/knowledge/acquisition/text/analyze")
def analyze_acquisition_text(input_data: TextAnalyzeInput):
    return knowledge_acquisition_service.analyze_acquisition_text(input_data)


@router.get("/api/knowledge/acquisition/evidence")
def list_nutrition_evidence(candidate_id: str = None, limit: int = 50, db: Session = Depends(get_db)):
    return knowledge_acquisition_service.list_nutrition_evidence(db, candidate_id, limit)


@router.post("/api/knowledge/acquisition/candidates/{candidate_id}/evidence")
def create_candidate_evidence(candidate_id: str, input_data: EvidenceInput, db: Session = Depends(get_db)):
    return knowledge_acquisition_service.create_candidate_evidence(db, candidate_id, input_data)


@router.post("/api/knowledge/acquisition/evidence/{evidence_id}/approve")
def approve_candidate_evidence(evidence_id: str, db: Session = Depends(get_db)):
    return knowledge_acquisition_service.approve_candidate_evidence(db, evidence_id)


@router.post("/api/knowledge/acquisition/evidence/bulk_approve")
def approve_candidate_evidence_bulk(input_data: BulkIdsInput, db: Session = Depends(get_db)):
    return knowledge_acquisition_service.approve_candidate_evidence_bulk(db, input_data)


@router.delete("/api/knowledge/acquisition/evidence/{evidence_id}")
def delete_candidate_evidence(evidence_id: str, db: Session = Depends(get_db)):
    return knowledge_acquisition_service.delete_candidate_evidence(db, evidence_id)


@router.post("/api/knowledge/acquisition/evidence/bulk/delete")
def delete_candidate_evidence_bulk(input_data: BulkIdsInput, db: Session = Depends(get_db)):
    return knowledge_acquisition_service.delete_candidate_evidence_bulk(db, input_data)


@router.delete("/api/knowledge/acquisition/candidates/{candidate_id}")
def delete_product_candidate(candidate_id: str, db: Session = Depends(get_db)):
    return knowledge_acquisition_service.delete_product_candidate(db, candidate_id)


@router.post("/api/knowledge/acquisition/candidates/bulk/delete")
def delete_product_candidate_bulk(input_data: BulkIdsInput, db: Session = Depends(get_db)):
    return knowledge_acquisition_service.delete_product_candidate_bulk(db, input_data)
