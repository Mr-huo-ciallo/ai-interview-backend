import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


TEST_DB_PATH = Path(tempfile.gettempdir()) / "ai_interview_api_tests.db"
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["AUTH_SECRET"] = "test-only-secret"
os.environ["AUTO_CREATE_TABLES"] = "true"

import main  # noqa: E402
from db import SessionLocal  # noqa: E402
from models import (  # noqa: E402
    HistoryRecordModel,
    InterviewQuestionModel,
    JobFollowUpModel,
    JobPostModel,
    ResumeProfileModel,
    ResumeVersionModel,
    UserModel,
)


@pytest.fixture()
def client():
    db = SessionLocal()
    try:
        for model in (
            JobFollowUpModel,
            ResumeVersionModel,
            JobPostModel,
            ResumeProfileModel,
            HistoryRecordModel,
            InterviewQuestionModel,
            UserModel,
        ):
            db.query(model).delete()
        db.commit()
    finally:
        db.close()

    with TestClient(main.app) as test_client:
        yield test_client
