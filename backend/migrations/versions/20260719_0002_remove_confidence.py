"""remove hard-coded confidence fields and sugar override

Revision ID: 20260719_0002
Revises: 20260614_0001
Create Date: 2026-07-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260719_0002"
down_revision: Union[str, None] = "20260614_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("drink_logs") as batch_op:
        batch_op.drop_column("baseSugarDensity")
        batch_op.drop_column("confidence")
    with op.batch_alter_table("knowledge_base") as batch_op:
        batch_op.drop_column("confidence")
    with op.batch_alter_table("agent_traces") as batch_op:
        batch_op.drop_column("confidence")
    with op.batch_alter_table("product_candidates") as batch_op:
        batch_op.drop_column("confidence")
    with op.batch_alter_table("nutrition_evidence") as batch_op:
        batch_op.drop_column("confidence")


def downgrade() -> None:
    with op.batch_alter_table("drink_logs") as batch_op:
        batch_op.add_column(sa.Column("baseSugarDensity", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("confidence", sa.Float(), server_default="1.0"))
    with op.batch_alter_table("knowledge_base") as batch_op:
        batch_op.add_column(sa.Column("confidence", sa.Float(), server_default="0.9"))
    with op.batch_alter_table("agent_traces") as batch_op:
        batch_op.add_column(sa.Column("confidence", sa.Float(), nullable=True))
    with op.batch_alter_table("product_candidates") as batch_op:
        batch_op.add_column(sa.Column("confidence", sa.Float(), server_default="0.5"))
    with op.batch_alter_table("nutrition_evidence") as batch_op:
        batch_op.add_column(sa.Column("confidence", sa.Float(), server_default="0.5"))
