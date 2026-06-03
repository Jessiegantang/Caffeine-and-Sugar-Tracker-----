from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel
import datetime

from database import engine, get_db, Base, DrinkLog, SleepRecord, DrinkKnowledge, HealthPlan, ChatLog, init_db
from agent import enrich_drink_data, generate_health_report, generate_companion_response
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

class SleepInput(BaseModel):
    date: str
    sleep_hours: float

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

# --- Companion Chat Endpoints ---

@app.get("/api/chat")
def get_chat_history(date: str, db: Session = Depends(get_db)):
    logs = db.query(ChatLog).filter(ChatLog.date == date).order_by(ChatLog.timestamp).all()
    return {"status": "success", "history": [{"role": l.role, "content": l.content} for l in logs]}

class ChatInput(BaseModel):
    date: str
    message: str

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

    # 4. Generate AI response
    ai_response_text = generate_companion_response(input_data.message, history, context)

    # 5. Save AI response
    now_str2 = datetime.datetime.now().isoformat()
    ai_log = ChatLog(date=input_data.date, role="assistant", content=ai_response_text, timestamp=now_str2)
    db.add(ai_log)
    db.commit()

    return {"status": "success", "response": ai_response_text}

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
        return report
    except Exception as e:
        return {"insights": []}

import os
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), ".."), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
