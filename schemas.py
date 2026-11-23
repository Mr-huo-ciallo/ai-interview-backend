from typing import Any, List, Optional

from pydantic import BaseModel, Field


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
    difficulty: str = ""
    tags: str = ""
    keyPoints: str = ""
    scoringFocus: str = ""
    followupFocus: str = ""


class AnswerItem(BaseModel):
    question: str
    type: str
    answer: str
    followUpQuestion: str = ""
    followUpAnswer: str = ""
    difficulty: str = ""
    tags: str = ""
    keyPoints: str = ""
    scoringFocus: str = ""
    referenceAnswerBasic: str = ""
    referenceAnswerGood: str = ""


class InterviewSubmitRequest(BaseModel):
    userId: int | None = None
    jobId: int | None = None
    jobTitle: str = ""
    role: str
    roleName: str
    answers: List[AnswerItem]
    submitTime: str


class HistoryRecord(BaseModel):
    userId: int | None = None
    jobId: int | None = None
    jobTitle: str = ""
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


class ResumeVersionCreateRequest(BaseModel):
    jobId: int | None = None
    title: str
    content: str
    source: str = "manual"


class FollowUpCreateRequest(BaseModel):
    dueAt: str
    note: str


class ResumeExperience(BaseModel):
    company: str = ""
    title: str = ""
    startDate: str = ""
    endDate: str = ""
    highlights: list[str] = Field(default_factory=list)


class ResumeEducation(BaseModel):
    school: str = ""
    degree: str = ""
    major: str = ""
    startDate: str = ""
    endDate: str = ""


class ResumeProject(BaseModel):
    name: str = ""
    role: str = ""
    technologies: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)


class ResumeStructuredData(BaseModel):
    fullName: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    summary: str = ""
    targetRole: str = ""
    skills: list[str] = Field(default_factory=list)
    education: list[ResumeEducation] = Field(default_factory=list)
    experience: list[ResumeExperience] = Field(default_factory=list)
    projects: list[ResumeProject] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


class ResumeExtractionResult(BaseModel):
    rawText: str
    structured: ResumeStructuredData
    warnings: list[str] = Field(default_factory=list)
    extractionMethod: str
    pageCount: int
    confidence: float


class JobImportRequest(BaseModel):
    jobs: list[dict[str, Any]]


class JobImportConfirmRequest(BaseModel):
    jobs: list[JobCreateRequest]


class LlmConfigUpdateRequest(BaseModel):
    provider: str = "custom"
    apiFormat: str = "openai"
    baseUrl: str
    model: str
    apiKey: str = ""
    enabled: bool = True


class LlmConfigTestRequest(BaseModel):
    provider: str = "custom"
    apiFormat: str = "openai"
    baseUrl: str
    model: str
    apiKey: str = ""


class JobJdParseRequest(BaseModel):
    rawText: str
    sourceUrl: str = ""
