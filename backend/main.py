from fastapi import FastAPI, Depends, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel
import datetime

from database import engine, get_db, Base, DrinkLog, SleepRecord, DrinkKnowledge, HealthPlan, ChatLog, AgentTrace, ProductCandidate, NutritionEvidence, init_db
from agent import enrich_drink_data, generate_health_report, generate_companion_response, parse_intake_message
from agents.orchestrator import run_agent_orchestrator
from agents.memory_agent import apply_memory_updates, clear_user_memory, extract_memory_updates, read_user_memory
from agents.health_plan_agent import create_health_plan, get_active_plan, plan_progress_summary, serialize_plan, update_plan_progress
from agents.knowledge_acquisition_agent import (
    add_nutrition_evidence,
    analyze_image_with_vision,
    approve_evidence_to_knowledge,
    create_manual_candidate,
    discover_product_candidates,
    is_allowed_source,
    serialize_candidate,
    serialize_evidence,
    stage_image_items,
)
import uuid
import json

app = FastAPI(title="DrinkMind Agent API")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize DB
init_db()

def save_agent_trace(db: Session, trace_state: Dict[str, Any]) -> None:
    trace = AgentTrace(
        id=trace_state.get("trace_id") or f"trace_{uuid.uuid4().hex[:12]}",
        intent=trace_state.get("intent"),
        user_input=trace_state.get("user_message"),
        agents_called=json.dumps(trace_state.get("agents_called", []), ensure_ascii=False),
        tools_used=json.dumps(trace_state.get("tools_used", []), ensure_ascii=False),
        retrieved_docs=json.dumps(trace_state.get("retrieved_docs", []), ensure_ascii=False),
        model_name=trace_state.get("model_name"),
        latency_ms=trace_state.get("latency_ms"),
        confidence=trace_state.get("confidence"),
        final_action=trace_state.get("final_action"),
        error=trace_state.get("error"),
    )
    db.add(trace)
    db.commit()


def parse_json_list(value: str | None) -> list:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []

# Pydantic models for incoming data
class DrinkInput(BaseModel):
    id: str
    date: str
    brand: str = None
    name: str
    type: str
    sugar: str
    volume: int
    startTime: str
    endTime: str
    caffeine: float
    sugarContent: float
    alcoholContent: float = None
    abv: float = None
    baseSugarDensity: float = None
    status: str = "active"
    data_source: str = "用户录入"
    confidence: float = 1.0
    reasoning: Any = None
    estimation_method: str = None
    matched_knowledge_id: str = None
    retrieval_score: float = None
    agent_trace_id: str = None

class SleepInput(BaseModel):
    date: str
    sleep_hours: float

class IntakeParseInput(BaseModel):
    message: str
    date: str = None

@app.get("/api/logs")
def get_logs(db: Session = Depends(get_db)):
    logs = db.query(DrinkLog).filter(DrinkLog.status == 'active').all()
    # Convert SQLAlchemy objects to dict
    result = []
    for log in logs:
        result.append({c.name: getattr(log, c.name) for c in log.__table__.columns})
    return result

@app.post("/api/sync_logs")
def sync_logs(logs: List[DrinkInput], db: Session = Depends(get_db)):
    # Clear existing and insert new
    db.query(DrinkLog).delete()
    for log in logs:
        db_log = DrinkLog(**log.dict())
        db.add(db_log)
    db.commit()
    return {"status": "success", "count": len(logs)}

@app.delete("/api/logs/{log_id}")
def delete_log(log_id: str, db: Session = Depends(get_db)):
    db_log = db.query(DrinkLog).filter(DrinkLog.id == log_id).first()
    if db_log:
        db_log.status = 'deleted'
        db.commit()
        return {"status": "success"}
    else:
        raise HTTPException(status_code=404, detail="Log not found")

@app.post("/api/log_drink")
def log_drink(drink: DrinkInput, db: Session = Depends(get_db)):
    # 1. Gather input into dict
    drink_dict = drink.dict()
    drink_dict["data_source"] = "用户录入"
    
    # 2. Enrich data synchronously (DB Exact Match -> RAG -> Estimator)
    enriched_drink = enrich_drink_data(drink_dict, db)
    
    # 3. Save to DB
    db_log = db.query(DrinkLog).filter(DrinkLog.id == drink.id).first()
    if not db_log:
        db_log = DrinkLog(**enriched_drink)
        if "reasoning" in enriched_drink and isinstance(enriched_drink["reasoning"], list):
            import json
            db_log.reasoning = json.dumps(enriched_drink["reasoning"])
        db.add(db_log)
        db.commit()
    else:
        # Update existing
        for k, v in enriched_drink.items():
            if k == "reasoning" and isinstance(v, list):
                import json
                setattr(db_log, k, json.dumps(v))
            elif hasattr(db_log, k):
                setattr(db_log, k, v)
        db.commit()
        
    insights = get_daily_insights(drink.date, db)
    return {
        "status": "success",
        "agent_analysis": insights
    }

@app.post("/api/sleep")
def log_sleep(sleep: SleepInput, db: Session = Depends(get_db)):
    db_sleep = db.query(SleepRecord).filter(SleepRecord.date == sleep.date).first()
    if db_sleep:
        db_sleep.sleep_hours = sleep.sleep_hours
    else:
        db_sleep = SleepRecord(date=sleep.date, sleep_hours=sleep.sleep_hours)
        db.add(db_sleep)
    db.commit()
    return {"status": "success"}

@app.post("/api/agent/parse_intake")
def parse_intake(input_data: IntakeParseInput, db: Session = Depends(get_db)):
    parsed = parse_intake_message(input_data.message)
    trace_state = {
        "trace_id": f"trace_{uuid.uuid4().hex[:12]}",
        "user_message": input_data.message,
        "intent": parsed.get("intent"),
        "agents_called": ["intake_parser"],
        "tools_used": ["LOCAL_INTAKE_PARSER"],
        "retrieved_docs": [],
        "model_name": "local",
        "latency_ms": 0.0,
        "confidence": parsed.get("confidence"),
        "final_action": "parse_intake",
        "error": None,
    }
    save_agent_trace(db, trace_state)
    return {"status": "success", "parsed_intake": parsed, "trace_id": trace_state["trace_id"]}

@app.get("/api/agent/daily_insights")
def get_daily_insights(date: str, db: Session = Depends(get_db)):
    # 纯统计，不再走 LLM
    today_records_db = db.query(DrinkLog).filter(DrinkLog.date == date, DrinkLog.status == 'active').all()
    caffeine_total = sum(r.caffeine or 0 for r in today_records_db)
    sugar_total = sum(r.sugarContent or 0 for r in today_records_db)
    
    # 简单规则计算 risk_level
    risk_level = "低风险"
    if caffeine_total > 400 or sugar_total > 50:
        risk_level = "高风险"
    elif caffeine_total > 200 or sugar_total > 25:
        risk_level = "中等风险"
        
    advice = "你好！我是 DrinkMind Companion。今天想喝点什么？"
    
    # Save the initial insights to chat log if empty
    existing_log = db.query(ChatLog).filter(ChatLog.date == date).first()
    if not existing_log and advice:
        now_str = datetime.datetime.now().isoformat()
        init_log = ChatLog(date=date, role="assistant", content=advice, timestamp=now_str)
        db.add(init_log)
        db.commit()

    return {
        "caffeine_total": caffeine_total,
        "sugar_total": sugar_total,
        "budget_caffeine": 400.0,
        "budget_sugar": 50.0,
        "risk_level": risk_level,
        "advice": advice
    }

class KnowledgeInput(BaseModel):
    id: str
    brand: str = None
    name: str
    type: str = None
    volume: int = 500
    caffeine: float = 0.0
    baseSugar: float = 0.0
    abv: float = 0.0
    source: str = "前端数据库"
    confidence: float = 0.9

class CandidateInput(BaseModel):
    brand: str = None
    name: str
    type: str = None
    source_url: str = None
    source_title: str = None
    source_snippet: str = None
    discovery_method: str = "manual"
    confidence: float = 0.6

class DiscoveryInput(BaseModel):
    query: str
    max_results: int = 5
    allowed_domains: List[str] = None
    mode: str = "safe"
    max_pages: int = 3

class EvidenceInput(BaseModel):
    source_url: str = None
    source_type: str = "manual"
    raw_evidence: str

class ImageImportInput(BaseModel):
    source_type: str = "image_upload"
    items: List[Dict[str, Any]]

class BulkIdsInput(BaseModel):
    ids: List[str]

from agent import sync_chroma_document, delete_chroma_document

@app.get("/api/knowledge_base")
def get_knowledge_base(db: Session = Depends(get_db)):
    kb_logs = db.query(DrinkKnowledge).all()
    return [{c.name: getattr(log, c.name) for c in log.__table__.columns} for log in kb_logs]

@app.post("/api/knowledge_base")
def add_knowledge(kb: KnowledgeInput, db: Session = Depends(get_db)):
    db_kb = DrinkKnowledge(**kb.dict())
    db.add(db_kb)
    db.commit()
    # Sync to Chroma
    sync_chroma_document(kb.id, kb.dict())
    return {"status": "success"}

@app.put("/api/knowledge_base/{kb_id}")
def update_knowledge(kb_id: str, kb: KnowledgeInput, db: Session = Depends(get_db)):
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

@app.delete("/api/knowledge_base/{kb_id}")
def delete_knowledge(kb_id: str, db: Session = Depends(get_db)):
    db_kb = db.query(DrinkKnowledge).filter(DrinkKnowledge.id == kb_id).first()
    if db_kb:
        db.delete(db_kb)
        db.commit()
        # Sync to Chroma
        delete_chroma_document(kb_id)
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Knowledge not found")

# --- Knowledge Acquisition Agent Endpoints ---

@app.get("/api/knowledge/acquisition/candidates")
def list_product_candidates(status: str = None, limit: int = 50, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 100))
    query = db.query(ProductCandidate).order_by(ProductCandidate.created_at.desc())
    if status:
        query = query.filter(ProductCandidate.status == status)
    else:
        query = query.filter(ProductCandidate.status.notin_(["imported", "deleted"]))
    candidates = query.limit(limit).all()
    return {"status": "success", "candidates": [serialize_candidate(candidate) for candidate in candidates]}

@app.post("/api/knowledge/acquisition/candidates")
def create_product_candidate(input_data: CandidateInput, db: Session = Depends(get_db)):
    if input_data.source_url and not is_allowed_source(input_data.source_url):
        raise HTTPException(status_code=400, detail="Source domain is blocked by acquisition policy")
    candidate = create_manual_candidate(db, input_data.dict())
    return {"status": "success", "candidate": serialize_candidate(candidate)}

@app.post("/api/knowledge/acquisition/discover")
def discover_candidates(input_data: DiscoveryInput, db: Session = Depends(get_db)):
    result = discover_product_candidates(
        db,
        query=input_data.query,
        max_results=input_data.max_results,
        allowed_domains=input_data.allowed_domains,
        mode=input_data.mode,
        max_pages=input_data.max_pages,
    )
    return {"status": "success", **result}

@app.post("/api/knowledge/acquisition/image/analyze")
async def analyze_acquisition_image(file: UploadFile = File(...)):
    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported")
    image_bytes = await file.read()
    if len(image_bytes) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image is too large; max size is 8MB")
    result = analyze_image_with_vision(image_bytes, content_type, file.filename)
    return {"status": "success", **result}

@app.post("/api/knowledge/acquisition/image/import")
def import_acquisition_image_items(input_data: ImageImportInput, db: Session = Depends(get_db)):
    result = stage_image_items(db, input_data.items, input_data.source_type)
    return {"status": "success", **result}

@app.get("/api/knowledge/acquisition/evidence")
def list_nutrition_evidence(candidate_id: str = None, limit: int = 50, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 100))
    query = db.query(NutritionEvidence).order_by(NutritionEvidence.created_at.desc())
    if candidate_id:
        query = query.filter(NutritionEvidence.candidate_id == candidate_id)
    else:
        query = query.filter(NutritionEvidence.status.notin_(["approved", "deleted"]))
    evidence_rows = query.limit(limit).all()
    return {"status": "success", "evidence": [serialize_evidence(row) for row in evidence_rows]}

@app.post("/api/knowledge/acquisition/candidates/{candidate_id}/evidence")
def create_candidate_evidence(candidate_id: str, input_data: EvidenceInput, db: Session = Depends(get_db)):
    if input_data.source_url and not is_allowed_source(input_data.source_url):
        raise HTTPException(status_code=400, detail="Source domain is blocked by acquisition policy")
    try:
        evidence = add_nutrition_evidence(db, candidate_id, input_data.dict())
        return {"status": "success", "evidence": serialize_evidence(evidence)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/knowledge/acquisition/evidence/{evidence_id}/approve")
def approve_candidate_evidence(evidence_id: str, db: Session = Depends(get_db)):
    try:
        kb = approve_evidence_to_knowledge(db, evidence_id)
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
        return {"status": "success", "knowledge": {c.name: getattr(kb, c.name) for c in kb.__table__.columns}}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/knowledge/acquisition/evidence/bulk_approve")
def approve_candidate_evidence_bulk(input_data: BulkIdsInput, db: Session = Depends(get_db)):
    approved = []
    errors = []
    for evidence_id in input_data.ids:
        try:
            kb = approve_evidence_to_knowledge(db, evidence_id)
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
            approved.append(kb.id)
        except ValueError as e:
            errors.append({"id": evidence_id, "error": str(e)})
    return {"status": "success", "approved": approved, "errors": errors}

@app.delete("/api/knowledge/acquisition/evidence/{evidence_id}")
def delete_candidate_evidence(evidence_id: str, db: Session = Depends(get_db)):
    evidence = db.query(NutritionEvidence).filter(NutritionEvidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    evidence.status = "deleted"
    db.commit()
    return {"status": "success"}

@app.post("/api/knowledge/acquisition/evidence/bulk/delete")
def delete_candidate_evidence_bulk(input_data: BulkIdsInput, db: Session = Depends(get_db)):
    rows = db.query(NutritionEvidence).filter(NutritionEvidence.id.in_(input_data.ids)).all()
    for row in rows:
        row.status = "deleted"
    db.commit()
    return {"status": "success", "deleted": len(rows)}

@app.delete("/api/knowledge/acquisition/candidates/{candidate_id}")
def delete_product_candidate(candidate_id: str, db: Session = Depends(get_db)):
    candidate = db.query(ProductCandidate).filter(ProductCandidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    candidate.status = "deleted"
    evidence_rows = db.query(NutritionEvidence).filter(NutritionEvidence.candidate_id == candidate_id).all()
    for row in evidence_rows:
        row.status = "deleted"
    db.commit()
    return {"status": "success"}

@app.post("/api/knowledge/acquisition/candidates/bulk/delete")
def delete_product_candidate_bulk(input_data: BulkIdsInput, db: Session = Depends(get_db)):
    candidates = db.query(ProductCandidate).filter(ProductCandidate.id.in_(input_data.ids)).all()
    for candidate in candidates:
        candidate.status = "deleted"
    evidence_rows = db.query(NutritionEvidence).filter(NutritionEvidence.candidate_id.in_(input_data.ids)).all()
    for row in evidence_rows:
        row.status = "deleted"
    db.commit()
    return {"status": "success", "deleted": len(candidates)}

# --- Companion Chat Endpoints ---

@app.get("/api/chat")
def get_chat_history(date: str, db: Session = Depends(get_db)):
    logs = db.query(ChatLog).filter(ChatLog.date == date).order_by(ChatLog.timestamp).all()
    return {"status": "success", "history": [{"role": l.role, "content": l.content} for l in logs]}

class ChatInput(BaseModel):
    date: str
    message: str

class AgentActInput(BaseModel):
    date: str
    message: str

class HealthPlanInput(BaseModel):
    date: str
    goal: str

@app.post("/api/agent/act")
def agent_act(input_data: AgentActInput, db: Session = Depends(get_db)):
    agent_state = run_agent_orchestrator(input_data.message, input_data.date, db)
    agent_state["memory_updates"] = apply_memory_updates(db, agent_state.get("memory_updates", {}))
    if agent_state.get("intent") == "create_health_plan":
        plan = create_health_plan(db, input_data.message, input_data.date)
        agent_state["health_plan"] = serialize_plan(plan)
    save_agent_trace(db, agent_state)
    return {"status": "success", "agent_state": agent_state}

@app.post("/api/chat")
def send_chat_message(input_data: ChatInput, db: Session = Depends(get_db)):
    # 1. Save user message
    now_str = datetime.datetime.now().isoformat()
    user_log = ChatLog(date=input_data.date, role="user", content=input_data.message, timestamp=now_str)
    db.add(user_log)
    db.commit()

    # 2. Get history
    logs = db.query(ChatLog).filter(ChatLog.date == input_data.date).order_by(ChatLog.timestamp).all()
    history = [{"role": l.role, "content": l.content} for l in logs[:-1]] # exclude current msg

    # 3. Get context
    today_records_db = db.query(DrinkLog).filter(DrinkLog.date == input_data.date, DrinkLog.status == 'active').all()
    today_caffeine = sum(r.caffeine or 0 for r in today_records_db)
    today_sugar = sum(r.sugarContent or 0 for r in today_records_db)
    
    sleep_record = db.query(SleepRecord).filter(SleepRecord.date == input_data.date).first()
    sleep_hours = sleep_record.sleep_hours if sleep_record else "未知"
    
    # 获取偏好记忆
    from database import UserPreference
    prefs_db = db.query(UserPreference).all()
    preferences = {p.key: p.value for p in prefs_db}

    context = {
        "today_caffeine_mg": today_caffeine,
        "today_sugar_g": today_sugar,
        "last_night_sleep_hours": sleep_hours,
        "user_preferences": preferences
    }

    # 4. Parse possible drink logging action before falling back to companion chat
    parsed_intake = parse_intake_message(input_data.message)
    if parsed_intake.get("intent") == "log_drink":
        memory_updates = extract_memory_updates(input_data.message, "log_drink", parsed_intake, db)
        if parsed_intake.get("missing_fields"):
            ai_response_text = parsed_intake.get("follow_up") or "我还需要一点信息才能帮你记录这杯饮品。"
        else:
            ai_response_text = (
                f"我识别到这是一杯 {parsed_intake.get('brand') or ''} "
                f"{parsed_intake.get('name')}，{parsed_intake.get('volume')}ml，"
                f"甜度 {parsed_intake.get('sugar')}。我已经整理成结构化饮品对象。"
            )
    else:
        parsed_intake = None
        memory_updates = extract_memory_updates(input_data.message, "ask_advice", None, db)
        ai_response_text = generate_companion_response(input_data.message, history, context)
    memory_updates = apply_memory_updates(db, memory_updates)

    # 5. Save AI response
    now_str2 = datetime.datetime.now().isoformat()
    ai_log = ChatLog(date=input_data.date, role="assistant", content=ai_response_text, timestamp=now_str2)
    db.add(ai_log)
    db.commit()

    trace_state = {
        "trace_id": f"trace_{uuid.uuid4().hex[:12]}",
        "user_message": input_data.message,
        "intent": parsed_intake.get("intent") if parsed_intake else "ask_advice",
        "agents_called": ["intake_parser"] if parsed_intake else ["intake_parser", "companion_agent"],
        "tools_used": ["LOCAL_INTAKE_PARSER"] if parsed_intake else ["LLM_CHAT"],
        "retrieved_docs": [],
        "model_name": "local" if parsed_intake else None,
        "latency_ms": 0.0,
        "confidence": parsed_intake.get("confidence") if parsed_intake else None,
        "memory_updates": memory_updates,
        "final_action": "ask_follow_up" if parsed_intake and parsed_intake.get("missing_fields") else ("fill_log_form" if parsed_intake else "answer_advice"),
        "error": None,
    }
    save_agent_trace(db, trace_state)

    return {"status": "success", "response": ai_response_text, "parsed_intake": parsed_intake, "trace_id": trace_state["trace_id"]}

@app.get("/api/agent/traces")
def get_agent_traces(limit: int = 20, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 100))
    traces = db.query(AgentTrace).order_by(AgentTrace.created_at.desc()).limit(limit).all()
    return {
        "status": "success",
        "traces": [
            {
                "id": trace.id,
                "created_at": trace.created_at,
                "intent": trace.intent,
                "user_input": trace.user_input,
                "agents_called": parse_json_list(trace.agents_called),
                "tools_used": parse_json_list(trace.tools_used),
                "retrieved_docs": parse_json_list(trace.retrieved_docs),
                "model_name": trace.model_name,
                "latency_ms": trace.latency_ms,
                "confidence": trace.confidence,
                "final_action": trace.final_action,
                "error": trace.error,
            }
            for trace in traces
        ]
    }

@app.get("/api/user/preferences")
def get_user_preferences(db: Session = Depends(get_db)):
    return {"status": "success", "preferences": read_user_memory(db)}

@app.delete("/api/user/preferences")
def delete_user_preferences(db: Session = Depends(get_db)):
    deleted = clear_user_memory(db)
    return {"status": "success", "deleted": deleted}

@app.post("/api/health/plans")
def create_plan(input_data: HealthPlanInput, db: Session = Depends(get_db)):
    plan = create_health_plan(db, input_data.goal, input_data.date)
    return {"status": "success", "plan": serialize_plan(plan)}

@app.get("/api/health/plans/active")
def get_active_health_plan(db: Session = Depends(get_db)):
    return {"status": "success", "plan": serialize_plan(get_active_plan(db))}

@app.post("/api/health/plans/active/progress")
def refresh_active_health_plan(date: str, db: Session = Depends(get_db)):
    plan = update_plan_progress(db, get_active_plan(db), date)
    return {"status": "success", "plan": plan}

@app.get("/api/agent/reports/daily")
def get_daily_report(date: str, db: Session = Depends(get_db)):
    today_records_db = db.query(DrinkLog).filter(DrinkLog.date == date, DrinkLog.status == 'active').all()
    logs = [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in today_records_db]
    report = generate_health_report(logs, "日度")
    return report

@app.get("/api/agent/reports/weekly")
def get_weekly_report(date: str, db: Session = Depends(get_db)):
    try:
        end_date = datetime.datetime.strptime(date, "%Y-%m-%d")
        start_date = end_date - datetime.timedelta(days=6)
        start_str = start_date.strftime("%Y-%m-%d")
        records_db = db.query(DrinkLog).filter(DrinkLog.date >= start_str, DrinkLog.date <= date, DrinkLog.status == 'active').all()
        logs = [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in records_db]
        report = generate_health_report(logs, "周度")
        active_plan = get_active_plan(db)
        report["active_plan_progress"] = plan_progress_summary(active_plan)
        return report
    except Exception as e:
        return {"insights": []}

import os
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), ".."), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
