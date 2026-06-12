import datetime

from fastapi import HTTPException

from agents.rag_store import delete_chroma_document, sync_chroma_document
from database import DrinkKnowledge


def serialize_knowledge(row: DrinkKnowledge) -> dict:
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


def list_knowledge(db) -> list[dict]:
    kb_logs = db.query(DrinkKnowledge).all()
    return [serialize_knowledge(log) for log in kb_logs]


def create_knowledge(db, kb) -> dict:
    db_kb = DrinkKnowledge(**kb.dict())
    db.add(db_kb)
    db.commit()
    # Sync to Chroma
    sync_chroma_document(kb.id, kb.dict())
    return {"status": "success"}


def update_knowledge(db, kb_id: str, kb) -> dict:
    db_kb = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == kb_id).first()
    if db_kb:
        update_data = kb.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_kb, key, value)
        db_kb.updated_at = datetime.datetime.now().isoformat()
        db.commit()
        # Sync to Chroma
        sync_chroma_document(kb_id, kb.dict())
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Knowledge not found")


def delete_knowledge(db, kb_id: str) -> dict:
    db_kb = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == kb_id).first()
    if db_kb:
        db.delete(db_kb)
        db.commit()
        # Sync to Chroma
        delete_chroma_document(kb_id)
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Knowledge not found")


def sync_approved_knowledge(kb: DrinkKnowledge) -> None:
    sync_chroma_document(kb.id, {
        "brand": kb.brand,
        "name": kb.name,
        "type": kb.type,
        "volume": kb.volume,
        "caffeine": kb.caffeine,
        "baseSugar": kb.baseSugar,
        "abv": kb.abv,
        "source": kb.source,
        "confidence": kb.confidence,
    })
