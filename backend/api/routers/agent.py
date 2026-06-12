from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.schemas import AgentActInput, ChatInput, IntakeParseInput
from database import get_db
from services import agent_action_service, chat_service, user_preference_service
from services.trace_service import list_agent_traces


router = APIRouter()


@router.post("/api/agent/parse_intake")
def parse_intake(input_data: IntakeParseInput, db: Session = Depends(get_db)):
    return agent_action_service.parse_intake(db, input_data)


# --- Companion Chat Endpoints ---

@router.get("/api/chat")
def get_chat_history(date: str, db: Session = Depends(get_db)):
    return chat_service.get_chat_history(db, date)


@router.post("/api/agent/act")
def agent_act(input_data: AgentActInput, db: Session = Depends(get_db)):
    return agent_action_service.act(db, input_data)


@router.post("/api/chat")
def send_chat_message(input_data: ChatInput, db: Session = Depends(get_db)):
    return chat_service.send_chat_message(db, input_data)


@router.get("/api/agent/traces")
def get_agent_traces(limit: int = 20, db: Session = Depends(get_db)):
    return list_agent_traces(db, limit)


@router.get("/api/user/preferences")
def get_user_preferences(db: Session = Depends(get_db)):
    return user_preference_service.get_user_preferences(db)


@router.delete("/api/user/preferences")
def delete_user_preferences(db: Session = Depends(get_db)):
    return user_preference_service.delete_user_preferences(db)
