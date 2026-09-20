from typing import Any, List, Optional

from pydantic import BaseModel


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class FollowUpRequest(BaseModel):
    role: str
    roleName: str
    question: str
    type: str
    answer: str


class AnswerItem(BaseModel):
    question: str
    type: str
    answer: str
    followUpQuestion: str = ""
    followUpAnswer: str = ""


class InterviewSubmitRequest(BaseModel):
    userId: int | None = None
    role: str
    roleName: str
    answers: List[AnswerItem]
    submitTime: str


class HistoryRecord(BaseModel):
    userId: int | None = None
    role: str
    roleName: str
    totalScore: int
    answerCount: int
    submitTime: str
    answers: List[AnswerItem]
    featureMatrix: Optional[List[dict[str, Any]]] = None
    scoreMeta: Optional[dict[str, Any]] = None


class QuestionCreateRequest(BaseModel):
    role: str
    type: str
    content: str
    sortOrder: int = 1
    difficulty: str = "medium"
    tags: str = ""
    keyPoints: str = ""
    scoringFocus: str = ""
    referenceAnswerBasic: str = ""
    referenceAnswerGood: str = ""
    followupFocus: str = ""
    followupExamples: str = ""


class ResumeProfileRequest(BaseModel):
    resumeText: str
    targetRole: str = ""


class JobCreateRequest(BaseModel):
    title: str
    company: str
    location: str = ""
    salary: str = ""
    requiredSkills: str = ""
    description: str = ""
    sourceUrl: str = ""


class JobStatusRequest(BaseModel):
    applicationStatus: str


class CareerUserRequest(BaseModel):
    pass


class ResumeVersionCreateRequest(BaseModel):
    jobId: int | None = None
    title: str
    content: str
    source: str = "manual"


class FollowUpCreateRequest(BaseModel):
    dueAt: str
    note: str
