import os
import json
import re
import uuid
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

from database import SessionLocal, DrinkLog, DrinkKnowledge
from local_estimator import estimate_nutrition
from agents.companion_agent import generate_companion_response
from agents.intake_parser import IntakeParseResult, parse_intake_message
from agents.rag_store import (
    chroma_path,
    default_chroma_path,
    delete_chroma_document,
    retriever,
    sync_chroma_document,
    use_chroma,
    vectorstore,
)
from agents.report_agent import generate_health_report
from agents.llm_config import (
    api_key,
    base_url,
    embeddings,
    env_truthy as _env_truthy,
    llm,
    llm_enabled,
    model_name,
)


def _llm_enabled() -> bool:
    return llm_enabled()

from agents.knowledge_lookup import (
    BRAND_CANONICAL_KEYS,
    _apply_hybrid_knowledge_result,
    _brand_key,
    _estimate_nutrition_with_fallback,
    _find_sql_knowledge_match,
    _knowledge_field_known,
    _knowledge_scope,
    _normalize_match_name,
    _sugar_from_knowledge,
)
import agents.knowledge_lookup as _knowledge_lookup


def enrich_drink_data(r: dict, db) -> dict:
    _knowledge_lookup.vectorstore = vectorstore
    _knowledge_lookup.llm = llm
    return _knowledge_lookup.enrich_drink_data(r, db)
