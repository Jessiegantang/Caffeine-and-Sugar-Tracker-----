"""baseline schema

Revision ID: 20260614_0001
Revises:
Create Date: 2026-06-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260614_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DRINK_LOG_COLUMNS = {
    "id": lambda: sa.Column("id", sa.String(), primary_key=True, index=True),
    "date": lambda: sa.Column("date", sa.String(), index=True),
    "brand": lambda: sa.Column("brand", sa.String(), nullable=True),
    "name": lambda: sa.Column("name", sa.String()),
    "type": lambda: sa.Column("type", sa.String()),
    "sugar": lambda: sa.Column("sugar", sa.String()),
    "volume": lambda: sa.Column("volume", sa.Integer()),
    "startTime": lambda: sa.Column("startTime", sa.String()),
    "endTime": lambda: sa.Column("endTime", sa.String()),
    "caffeine": lambda: sa.Column("caffeine", sa.Float()),
    "sugarContent": lambda: sa.Column("sugarContent", sa.Float()),
    "baseSugarDensity": lambda: sa.Column("baseSugarDensity", sa.Float(), nullable=True),
    "status": lambda: sa.Column("status", sa.String(), server_default="active"),
    "data_source": lambda: sa.Column("data_source", sa.String(), server_default="user_input"),
    "confidence": lambda: sa.Column("confidence", sa.Float(), server_default="1.0"),
    "reasoning": lambda: sa.Column("reasoning", sa.String(), nullable=True),
    "estimation_method": lambda: sa.Column("estimation_method", sa.String(), nullable=True),
    "matched_knowledge_id": lambda: sa.Column("matched_knowledge_id", sa.String(), nullable=True),
    "retrieval_score": lambda: sa.Column("retrieval_score", sa.Float(), nullable=True),
    "agent_trace_id": lambda: sa.Column("agent_trace_id", sa.String(), nullable=True),
    "composition_json": lambda: sa.Column("composition_json", sa.String(), nullable=True),
    "explainability_json": lambda: sa.Column("explainability_json", sa.String(), nullable=True),
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "drink_logs" not in tables:
        op.create_table("drink_logs", *[factory() for factory in DRINK_LOG_COLUMNS.values()])
    else:
        _add_missing_columns("drink_logs", DRINK_LOG_COLUMNS)

    if "knowledge_base" not in tables:
        op.create_table(
            "knowledge_base",
            sa.Column("id", sa.String(), primary_key=True, index=True),
            sa.Column("brand", sa.String(), nullable=True, index=True),
            sa.Column("name", sa.String(), index=True),
            sa.Column("type", sa.String(), nullable=True),
            sa.Column("volume", sa.Integer(), server_default="500"),
            sa.Column("caffeine", sa.Float(), server_default="0.0"),
            sa.Column("baseSugar", sa.Float(), server_default="0.0"),
            sa.Column("source", sa.String(), server_default="system_preset"),
            sa.Column("confidence", sa.Float(), server_default="0.9"),
            sa.Column("created_at", sa.String()),
            sa.Column("updated_at", sa.String()),
        )

    if "sleep_records" not in tables:
        op.create_table(
            "sleep_records",
            sa.Column("date", sa.String(), primary_key=True, index=True),
            sa.Column("sleep_hours", sa.Float()),
        )

    if "chat_logs" not in tables:
        op.create_table(
            "chat_logs",
            sa.Column("id", sa.Integer(), primary_key=True, index=True, autoincrement=True),
            sa.Column("date", sa.String(), index=True),
            sa.Column("role", sa.String()),
            sa.Column("content", sa.String()),
            sa.Column("timestamp", sa.String()),
        )

    if "user_preferences" not in tables:
        op.create_table(
            "user_preferences",
            sa.Column("key", sa.String(), primary_key=True, index=True),
            sa.Column("value", sa.String()),
            sa.Column("updated_at", sa.String()),
        )

    if "agent_traces" not in tables:
        op.create_table(
            "agent_traces",
            sa.Column("id", sa.String(), primary_key=True, index=True),
            sa.Column("created_at", sa.String(), index=True),
            sa.Column("intent", sa.String(), nullable=True),
            sa.Column("user_input", sa.String(), nullable=True),
            sa.Column("agents_called", sa.String(), nullable=True),
            sa.Column("tools_used", sa.String(), nullable=True),
            sa.Column("retrieved_docs", sa.String(), nullable=True),
            sa.Column("model_name", sa.String(), nullable=True),
            sa.Column("latency_ms", sa.Float(), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.Column("final_action", sa.String(), nullable=True),
            sa.Column("error", sa.String(), nullable=True),
        )

    if "product_candidates" not in tables:
        op.create_table(
            "product_candidates",
            sa.Column("id", sa.String(), primary_key=True, index=True),
            sa.Column("brand", sa.String(), nullable=True, index=True),
            sa.Column("name", sa.String(), index=True),
            sa.Column("type", sa.String(), nullable=True),
            sa.Column("source_url", sa.String(), nullable=True),
            sa.Column("source_title", sa.String(), nullable=True),
            sa.Column("source_snippet", sa.String(), nullable=True),
            sa.Column("discovery_method", sa.String(), server_default="manual"),
            sa.Column("status", sa.String(), server_default="pending_review", index=True),
            sa.Column("confidence", sa.Float(), server_default="0.5"),
            sa.Column("created_at", sa.String(), index=True),
            sa.Column("updated_at", sa.String()),
        )

    if "nutrition_evidence" not in tables:
        op.create_table(
            "nutrition_evidence",
            sa.Column("id", sa.String(), primary_key=True, index=True),
            sa.Column("candidate_id", sa.String(), index=True),
            sa.Column("source_url", sa.String(), nullable=True),
            sa.Column("source_type", sa.String(), server_default="manual"),
            sa.Column("raw_evidence", sa.String()),
            sa.Column("extracted_json", sa.String(), nullable=True),
            sa.Column("confidence", sa.Float(), server_default="0.5"),
            sa.Column("status", sa.String(), server_default="pending_review", index=True),
            sa.Column("created_at", sa.String(), index=True),
        )


def downgrade() -> None:
    # This baseline migration is intentionally not reversible for existing local
    # SQLite databases because it may have adopted pre-existing user data.
    pass


def _add_missing_columns(table_name: str, column_factories: dict) -> None:
    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns(table_name)}
    for name, factory in column_factories.items():
        if name not in existing:
            op.add_column(table_name, factory())
