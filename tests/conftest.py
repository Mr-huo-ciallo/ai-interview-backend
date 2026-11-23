import os
import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient


TEST_DB_PATH = Path(tempfile.gettempdir()) / "ai_interview_api_tests.db"
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["AUTH_SECRET"] = "test-only-secret"

ALEMBIC_CONFIG = Config(str(Path(__file__).parents[1] / "alembic.ini"))
command.upgrade(ALEMBIC_CONFIG, "head")

import main  # noqa: E402
from db import SessionLocal  # noqa: E402
from models import (  # noqa: E402
    HistoryRecordModel,
    InterviewQuestionModel,
    JobFollowUpModel,
    JobPostModel,
    ResumeProfileModel,
    ResumeVersionModel,
    UserLlmConfigModel,
    UserModel,
)
from rate_limit import reset_rate_limits  # noqa: E402


@pytest.fixture()
def client():
    reset_rate_limits()
    db = SessionLocal()
    try:
        for model in (
            JobFollowUpModel,
            ResumeVersionModel,
            JobPostModel,
            ResumeProfileModel,
            HistoryRecordModel,
            InterviewQuestionModel,
            UserLlmConfigModel,
            UserModel,
        ):
            db.query(model).delete()
        db.commit()
    finally:
        db.close()

    with TestClient(main.app) as test_client:
        yield test_client
