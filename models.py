from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, UniqueConstraint

from db import Base


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("username", name="uq_users_username"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class HistoryRecordModel(Base):
    __tablename__ = "history_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True, index=True)
    role = Column(String(50), nullable=False)
    role_name = Column(String(100), nullable=False)
    total_score = Column(Integer, nullable=False)
    answer_count = Column(Integer, nullable=False)
    submit_time = Column(String(100), nullable=False)
    answers_json = Column(Text, nullable=False)
    feature_matrix_json = Column(Text, nullable=True)
    score_meta_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class InterviewQuestionModel(Base):
    __tablename__ = "interview_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role = Column(String(50), nullable=False)
    type = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    sort_order = Column(Integer, nullable=False, default=1, server_default="1")

    difficulty = Column(String(20), nullable=False, default="medium", server_default="medium")
    tags = Column(Text, nullable=True)
    key_points = Column(Text, nullable=True)
    scoring_focus = Column(Text, nullable=True)
    reference_answer_basic = Column(Text, nullable=True)
    reference_answer_good = Column(Text, nullable=True)
    followup_focus = Column(Text, nullable=True)
    followup_examples = Column(Text, nullable=True)


class ResumeProfileModel(Base):
    __tablename__ = "resume_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_resume_profiles_user_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    resume_text = Column(Text, nullable=False)
    skills_json = Column(Text, nullable=False, default="[]")
    target_role = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class JobPostModel(Base):
    __tablename__ = "job_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    title = Column(String(150), nullable=False)
    company = Column(String(150), nullable=False)
    location = Column(String(100), nullable=True)
    salary = Column(String(100), nullable=True)
    required_skills = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    source_url = Column(String(500), nullable=True)
    application_status = Column(String(30), nullable=False, default="saved", server_default="saved")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ResumeVersionModel(Base):
    __tablename__ = "resume_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    job_id = Column(Integer, nullable=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    source = Column(String(30), nullable=False, default="manual", server_default="manual")
    created_at = Column(DateTime, default=datetime.now)


class JobFollowUpModel(Base):
    __tablename__ = "job_follow_ups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    job_id = Column(Integer, nullable=False, index=True)
    due_at = Column(String(40), nullable=False, index=True)
    note = Column(Text, nullable=False)
    completed = Column(Boolean, nullable=False, default=False, server_default="0")
    created_at = Column(DateTime, default=datetime.now)


class UserLlmConfigModel(Base):
    __tablename__ = "user_llm_configs"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_llm_configs_user_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    provider = Column(String(50), nullable=False, default="custom", server_default="custom")
    api_format = Column(String(20), nullable=False, default="openai", server_default="openai")
    base_url = Column(String(500), nullable=False)
    model = Column(String(150), nullable=False)
    api_key_encrypted = Column(Text, nullable=False, default="")
    enabled = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
