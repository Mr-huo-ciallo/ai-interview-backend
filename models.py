from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from db import Base


class HistoryRecordModel(Base):
    __tablename__ = "history_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    role = Column(String(50), nullable=False)
    role_name = Column(String(100), nullable=False)
    total_score = Column(Integer, nullable=False)
    answer_count = Column(Integer, nullable=False)
    submit_time = Column(String(100), nullable=False)
    answers_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class InterviewQuestionModel(Base):
    __tablename__ = "interview_questions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    role = Column(String(50), nullable=False)
    type = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    sort_order = Column(Integer, nullable=False, default=1)

    difficulty = Column(String(20), nullable=False, default="medium")
    tags = Column(Text, nullable=True)
    key_points = Column(Text, nullable=True)
    scoring_focus = Column(Text, nullable=True)
    reference_answer_basic = Column(Text, nullable=True)
    reference_answer_good = Column(Text, nullable=True)
    followup_focus = Column(Text, nullable=True)
    followup_examples = Column(Text, nullable=True)