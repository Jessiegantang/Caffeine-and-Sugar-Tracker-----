import os
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class DrinkLog(Base):
    __tablename__ = 'drink_logs'

    id = Column(String, primary_key=True, index=True)
    date = Column(String, index=True) # YYYY-MM-DD
    brand = Column(String, nullable=True)
    name = Column(String)
    type = Column(String)
    sugar = Column(String)
    volume = Column(Integer)
    startTime = Column(String) # HH:MM
    endTime = Column(String) # HH:MM
    caffeine = Column(Float)
    sugarContent = Column(Float)
    baseSugarDensity = Column(Float, nullable=True)
    # New fields for Agent system upgrade
    status = Column(String, default='active')
    data_source = Column(String, default='user_input')
    confidence = Column(Float, default=1.0)
    reasoning = Column(String, nullable=True)
    estimation_method = Column(String, nullable=True)
    matched_knowledge_id = Column(String, nullable=True)
    retrieval_score = Column(Float, nullable=True)
    agent_trace_id = Column(String, nullable=True)
    composition_json = Column(String, nullable=True)
    explainability_json = Column(String, nullable=True)

import datetime

class DrinkKnowledge(Base):
    __tablename__ = 'knowledge_base'

    id = Column(String, primary_key=True, index=True)
    brand = Column(String, nullable=True, index=True)
    name = Column(String, index=True)
    type = Column(String, nullable=True)
    volume = Column(Integer, default=500)
    caffeine = Column(Float, default=0.0)
    baseSugar = Column(Float, default=0.0)
    source = Column(String, default='system_preset')
    confidence = Column(Float, default=0.9)
    created_at = Column(String, default=lambda: datetime.datetime.now().isoformat())
    updated_at = Column(String, default=lambda: datetime.datetime.now().isoformat())

class SleepRecord(Base):
    __tablename__ = 'sleep_records'

    date = Column(String, primary_key=True, index=True) # YYYY-MM-DD
    sleep_hours = Column(Float)

class ChatLog(Base):
    __tablename__ = 'chat_logs'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    date = Column(String, index=True) # YYYY-MM-DD
    role = Column(String) # 'user' or 'assistant'
    content = Column(String)
    timestamp = Column(String) # ISO 8601 string

class UserPreference(Base):
    __tablename__ = 'user_preferences'

    key = Column(String, primary_key=True, index=True)
    value = Column(String)
    updated_at = Column(String, default=lambda: datetime.datetime.now().isoformat())

class AgentTrace(Base):
    __tablename__ = 'agent_traces'

    id = Column(String, primary_key=True, index=True)
    created_at = Column(String, default=lambda: datetime.datetime.now().isoformat(), index=True)
    intent = Column(String, nullable=True)
    user_input = Column(String, nullable=True)
    agents_called = Column(String, nullable=True)
    tools_used = Column(String, nullable=True)
    retrieved_docs = Column(String, nullable=True)
    model_name = Column(String, nullable=True)
    latency_ms = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    final_action = Column(String, nullable=True)
    error = Column(String, nullable=True)

class ProductCandidate(Base):
    __tablename__ = 'product_candidates'

    id = Column(String, primary_key=True, index=True)
    brand = Column(String, nullable=True, index=True)
    name = Column(String, index=True)
    type = Column(String, nullable=True)
    source_url = Column(String, nullable=True)
    source_title = Column(String, nullable=True)
    source_snippet = Column(String, nullable=True)
    discovery_method = Column(String, default="manual")
    status = Column(String, default="pending_review", index=True)
    confidence = Column(Float, default=0.5)
    created_at = Column(String, default=lambda: datetime.datetime.now().isoformat(), index=True)
    updated_at = Column(String, default=lambda: datetime.datetime.now().isoformat())

class NutritionEvidence(Base):
    __tablename__ = 'nutrition_evidence'

    id = Column(String, primary_key=True, index=True)
    candidate_id = Column(String, index=True)
    source_url = Column(String, nullable=True)
    source_type = Column(String, default="manual")
    raw_evidence = Column(String)
    extracted_json = Column(String, nullable=True)
    confidence = Column(Float, default=0.5)
    status = Column(String, default="pending_review", index=True)
    created_at = Column(String, default=lambda: datetime.datetime.now().isoformat(), index=True)

DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[1] / "drinks.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}")

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    # Schema changes are managed by Alembic. Run:
    #   venv\Scripts\python.exe -m alembic upgrade head
    return None

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
