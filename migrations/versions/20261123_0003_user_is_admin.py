"""add is_admin to users

Revision ID: 20261123_0003
Revises: 20261123_0002
Create Date: 2026-11-23 14:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20261123_0003"
down_revision = "20261123_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column("users", "is_admin")
