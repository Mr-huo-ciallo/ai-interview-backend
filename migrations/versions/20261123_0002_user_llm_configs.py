"""add user_llm_configs table

Revision ID: 20261123_0002
Revises: 20260711_0001
Create Date: 2026-11-23 13:40:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20261123_0002"
down_revision = "20260711_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_llm_configs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="custom"),
        sa.Column("api_format", sa.String(length=20), nullable=False, server_default="openai"),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("model", sa.String(length=150), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", name="uq_user_llm_configs_user_id"),
    )


def downgrade():
    op.drop_table("user_llm_configs")
