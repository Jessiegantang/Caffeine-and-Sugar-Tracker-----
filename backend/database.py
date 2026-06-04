import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, Time, Boolean, text
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
    alcoholContent = Column(Float, nullable=True)
    abv = Column(Float, nullable=True)
    baseSugarDensity = Column(Float, nullable=True)
    # New fields for Agent system upgrade
    status = Column(String, default='active')
    data_source = Column(String, default='用户录入')
    confidence = Column(Float, default=1.0)
    reasoning = Column(String, nullable=True)
    estimation_method = Column(String, nullable=True)
    matched_knowledge_id = Column(String, nullable=True)
    retrieval_score = Column(Float, nullable=True)
    agent_trace_id = Column(String, nullable=True)

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
    abv = Column(Float, default=0.0)
    source = Column(String, default="系统预设")
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

class HealthPlan(Base):
    __tablename__ = 'health_plans'

    id = Column(String, primary_key=True, index=True)
    target = Column(String)  # e.g., 'reduce_caffeine', 'reduce_sugar'
    status = Column(String, default='active')  # 'active', 'completed', 'abandoned'
    total_days = Column(Integer, default=7)
    current_day = Column(Integer, default=1)
    start_date = Column(String) # YYYY-MM-DD
    plan_content = Column(String) # JSON string of the plan
    created_at = Column(String, default=lambda: datetime.datetime.now().isoformat())
    updated_at = Column(String, default=lambda: datetime.datetime.now().isoformat())

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

DATABASE_URL = "sqlite:///./drinks.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def auto_migrate_db():
    """Auto migrate sqlite database to add new columns if missing."""
    try:
        with engine.connect() as conn:
            # Check if columns exist
            result = conn.execute(text("PRAGMA table_info(drink_logs)")).fetchall()
            columns = [row[1] for row in result]
            
            if 'status' not in columns:
                conn.execute(text("ALTER TABLE drink_logs ADD COLUMN status VARCHAR DEFAULT 'active'"))
                print("Migrated DB: Added 'status' column.")
            if 'data_source' not in columns:
                conn.execute(text("ALTER TABLE drink_logs ADD COLUMN data_source VARCHAR DEFAULT '用户录入'"))
                print("Migrated DB: Added 'data_source' column.")
            if 'confidence' not in columns:
                conn.execute(text("ALTER TABLE drink_logs ADD COLUMN confidence FLOAT DEFAULT 1.0"))
                print("Migrated DB: Added 'confidence' column.")
            if 'reasoning' not in columns:
                conn.execute(text("ALTER TABLE drink_logs ADD COLUMN reasoning VARCHAR"))
                print("Migrated DB: Added 'reasoning' column.")
            if 'estimation_method' not in columns:
                conn.execute(text("ALTER TABLE drink_logs ADD COLUMN estimation_method VARCHAR"))
                print("Migrated DB: Added 'estimation_method' column.")
            if 'matched_knowledge_id' not in columns:
                conn.execute(text("ALTER TABLE drink_logs ADD COLUMN matched_knowledge_id VARCHAR"))
                print("Migrated DB: Added 'matched_knowledge_id' column.")
            if 'retrieval_score' not in columns:
                conn.execute(text("ALTER TABLE drink_logs ADD COLUMN retrieval_score FLOAT"))
                print("Migrated DB: Added 'retrieval_score' column.")
            if 'agent_trace_id' not in columns:
                conn.execute(text("ALTER TABLE drink_logs ADD COLUMN agent_trace_id VARCHAR"))
                print("Migrated DB: Added 'agent_trace_id' column.")
            conn.commit()
    except Exception as e:
        print(f"Auto-migration failed: {e}")

def init_db():
    Base.metadata.create_all(bind=engine)
    auto_migrate_db()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
