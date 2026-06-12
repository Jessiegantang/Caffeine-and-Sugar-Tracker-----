from typing import Any, Dict, List

from pydantic import BaseModel


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


class NutritionFeedbackCorrected(BaseModel):
    brand: str = None
    name: str
    type: str
    volume: int
    caffeine: float
    sugarContent: float


class NutritionFeedbackInput(BaseModel):
    corrected: NutritionFeedbackCorrected
    source_type: str = "user_feedback"
    source_note: str = ""
    apply_to_log: bool = True
    submit_as_evidence: bool = False


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


class EvidenceInput(BaseModel):
    source_url: str = None
    source_type: str = "manual"
    raw_evidence: str


class ImageImportInput(BaseModel):
    source_type: str = "image_upload"
    items: List[Dict[str, Any]]


class BulkIdsInput(BaseModel):
    ids: List[str]


class ChatInput(BaseModel):
    date: str
    message: str


class AgentActInput(BaseModel):
    date: str
    message: str


class HealthPlanInput(BaseModel):
    date: str
    goal: str
