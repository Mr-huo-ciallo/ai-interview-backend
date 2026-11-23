"""add foreign keys and cascade rules

Revision ID: 20261123_0004
Revises: 20261123_0003
Create Date: 2026-11-23 15:20:00
"""

from alembic import op


revision = "20261123_0004"
down_revision = "20261123_0003"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("history_records") as batch_op:
        batch_op.create_foreign_key(
            "fk_history_records_user_id",
            "users",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("resume_profiles") as batch_op:
        batch_op.create_foreign_key(
            "fk_resume_profiles_user_id",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("job_posts") as batch_op:
        batch_op.create_foreign_key(
            "fk_job_posts_user_id",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("resume_versions") as batch_op:
        batch_op.create_foreign_key(
            "fk_resume_versions_user_id",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_resume_versions_job_id",
            "job_posts",
            ["job_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("job_follow_ups") as batch_op:
        batch_op.create_foreign_key(
            "fk_job_follow_ups_user_id",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_job_follow_ups_job_id",
            "job_posts",
            ["job_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("user_llm_configs") as batch_op:
        batch_op.create_foreign_key(
            "fk_user_llm_configs_user_id",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade():
    with op.batch_alter_table("user_llm_configs") as batch_op:
        batch_op.drop_constraint("fk_user_llm_configs_user_id", type_="foreignkey")

    with op.batch_alter_table("job_follow_ups") as batch_op:
        batch_op.drop_constraint("fk_job_follow_ups_job_id", type_="foreignkey")
        batch_op.drop_constraint("fk_job_follow_ups_user_id", type_="foreignkey")

    with op.batch_alter_table("resume_versions") as batch_op:
        batch_op.drop_constraint("fk_resume_versions_job_id", type_="foreignkey")
        batch_op.drop_constraint("fk_resume_versions_user_id", type_="foreignkey")

    with op.batch_alter_table("job_posts") as batch_op:
        batch_op.drop_constraint("fk_job_posts_user_id", type_="foreignkey")

    with op.batch_alter_table("resume_profiles") as batch_op:
        batch_op.drop_constraint("fk_resume_profiles_user_id", type_="foreignkey")

    with op.batch_alter_table("history_records") as batch_op:
        batch_op.drop_constraint("fk_history_records_user_id", type_="foreignkey")
