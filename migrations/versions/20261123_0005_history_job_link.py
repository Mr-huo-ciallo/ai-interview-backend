"""add job_id and job_title to history_records

Revision ID: 20261123_0005
Revises: 20261123_0004
Create Date: 2026-11-23 19:15:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20261123_0005"
down_revision = "20261123_0004"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("history_records") as batch_op:
        batch_op.add_column(sa.Column("job_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("job_title", sa.String(length=200), nullable=True))
        batch_op.create_index("ix_history_records_job_id", ["job_id"])
        batch_op.create_foreign_key(
            "fk_history_records_job_id",
            "job_posts",
            ["job_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade():
    with op.batch_alter_table("history_records") as batch_op:
        batch_op.drop_constraint("fk_history_records_job_id", type_="foreignkey")
        batch_op.drop_index("ix_history_records_job_id")
        batch_op.drop_column("job_title")
        batch_op.drop_column("job_id")
