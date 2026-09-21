"""initial schema

Revision ID: 20260711_0001
Revises:
Create Date: 2026-07-11 16:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260711_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )

    op.create_table(
        "history_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("role_name", sa.String(length=100), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=False),
        sa.Column("answer_count", sa.Integer(), nullable=False),
        sa.Column("submit_time", sa.String(length=100), nullable=False),
        sa.Column("answers_json", sa.Text(), nullable=False),
        sa.Column("feature_matrix_json", sa.Text(), nullable=True),
        sa.Column("score_meta_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_history_records_user_id", "history_records", ["user_id"])

    op.create_table(
        "interview_questions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("difficulty", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("key_points", sa.Text(), nullable=True),
        sa.Column("scoring_focus", sa.Text(), nullable=True),
        sa.Column("reference_answer_basic", sa.Text(), nullable=True),
        sa.Column("reference_answer_good", sa.Text(), nullable=True),
        sa.Column("followup_focus", sa.Text(), nullable=True),
        sa.Column("followup_examples", sa.Text(), nullable=True),
    )

    op.create_table(
        "resume_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("resume_text", sa.Text(), nullable=False),
        sa.Column("skills_json", sa.Text(), nullable=False),
        sa.Column("target_role", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", name="uq_resume_profiles_user_id"),
    )

    op.create_table(
        "job_posts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("company", sa.String(length=150), nullable=False),
        sa.Column("location", sa.String(length=100), nullable=True),
        sa.Column("salary", sa.String(length=100), nullable=True),
        sa.Column("required_skills", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("application_status", sa.String(length=30), nullable=False, server_default="saved"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_job_posts_user_id", "job_posts", ["user_id"])

    op.create_table(
        "resume_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_resume_versions_user_id", "resume_versions", ["user_id"])
    op.create_index("ix_resume_versions_job_id", "resume_versions", ["job_id"])

    op.create_table(
        "job_follow_ups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.String(length=40), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_job_follow_ups_user_id", "job_follow_ups", ["user_id"])
    op.create_index("ix_job_follow_ups_job_id", "job_follow_ups", ["job_id"])
    op.create_index("ix_job_follow_ups_due_at", "job_follow_ups", ["due_at"])


def downgrade():
    op.drop_index("ix_job_follow_ups_due_at", table_name="job_follow_ups")
    op.drop_index("ix_job_follow_ups_job_id", table_name="job_follow_ups")
    op.drop_index("ix_job_follow_ups_user_id", table_name="job_follow_ups")
    op.drop_table("job_follow_ups")
    op.drop_index("ix_resume_versions_job_id", table_name="resume_versions")
    op.drop_index("ix_resume_versions_user_id", table_name="resume_versions")
    op.drop_table("resume_versions")
    op.drop_index("ix_job_posts_user_id", table_name="job_posts")
    op.drop_table("job_posts")
    op.drop_table("resume_profiles")
    op.drop_table("interview_questions")
    op.drop_index("ix_history_records_user_id", table_name="history_records")
    op.drop_table("history_records")
    op.drop_table("users")
