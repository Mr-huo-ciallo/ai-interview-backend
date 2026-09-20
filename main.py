import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import logging

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, List, Optional
from auth_utils import (
    create_access_token,
    decode_access_token,
    hash_password,
    is_legacy_password_hash,
    verify_password,
)

from llm_client import (
    call_llm_for_feedback,
    call_llm_for_followup,
    call_llm_for_profile_summary,
    call_llm_for_job_preparation,
    call_llm_for_daily_action_plan,
    call_llm_for_tailored_resume,
    call_llm_for_job_interview_questions
)
from db import Base, engine, get_db
from config import AUTO_CREATE_TABLES, validate_runtime_config
from observability import RequestLoggingMiddleware, configure_logging, get_request_id
from models import HistoryRecordModel, InterviewQuestionModel
from crud import (
    create_user,
    get_user_by_username,
    get_user_by_id,
    add_history_record,
    get_history_list,
    clear_history_records,
    get_questions_by_role,
    get_all_questions,
    add_question,
    delete_question,
    get_question_by_id,
    update_question,
    get_question_by_role_and_content,
    get_user_history_summary,
    get_resume_profile,
    save_resume_profile,
    create_job,
    get_jobs_by_user,
    get_job_by_id,
    update_job_status,
    update_job,
    delete_job,
    score_job_match,
    build_job_preparation,
    build_daily_action_plan,
    build_job_interview_questions,
    create_resume_version,
    get_resume_versions,
    create_follow_up,
    get_pending_follow_ups,
    complete_follow_up,
)
from scoring.rules import (
    calculate_tech_score,
    calculate_expression_score,
    calculate_logic_score,
    calculate_match_score,
    calculate_total_score,
    generate_strengths,
    generate_weaknesses,
    generate_suggestions,
    calculate_type_bonus
)
from scoring.matrix import build_feature_matrix, blend_scores
from scoring.config import SUPPORTED_ROLES

app = FastAPI()

security = HTTPBearer(auto_error=False)

configure_logging()
validate_runtime_config()
if AUTO_CREATE_TABLES:
    Base.metadata.create_all(bind=engine)

raw_cors_origins = os.getenv("CORS_ORIGINS", "*")
cors_origins = [
    origin.strip()
    for origin in raw_cors_origins.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    response = {"detail": exc.detail, "requestId": get_request_id(request)}
    return JSONResponse(status_code=exc.status_code, content=response, headers=exc.headers)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logging.getLogger("api.error").exception(
        "unhandled request error requestId=%s path=%s", get_request_id(request), request.url.path
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "服务器内部错误", "requestId": get_request_id(request)},
    )


def require_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db=Depends(get_db),
):
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    return resolve_token_user(credentials, db)


def resolve_token_user(credentials: HTTPAuthorizationCredentials, db):
    try:
        payload = decode_access_token(credentials.credentials)
        user = get_user_by_id(db, int(payload["sub"]))
        if not user:
            raise ValueError("用户不存在")
        return user
    except (ValueError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效，请重新登录")


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db=Depends(get_db),
):
    if not credentials:
        return None
    if credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录凭证格式无效")
    return resolve_token_user(credentials, db)


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


@app.get("/")
def read_root():
    return {"message": "AI Interview Backend is running"}


@app.get("/api/questions")
def get_questions(role: str = "java", db=Depends(get_db)):
    questions = get_questions_by_role(db, role)

    if not questions and role not in SUPPORTED_ROLES:
        questions = get_questions_by_role(db, "java")

    return {
        "role": role,
        "questions": questions
    }


@app.post("/api/interview/follow-up")
def generate_followup(data: FollowUpRequest, db=Depends(get_db)):
    fallback_map = {
        "project": "你在这个项目中具体负责哪些模块？遇到过什么技术难点？",
        "technical": "你能进一步解释一下这个技术点背后的原理或适用场景吗？",
        "scenario": "如果让你一步步落地解决，你会先从哪一步开始排查？"
    }

    follow_up_question = fallback_map.get(
        data.type,
        "你可以结合具体项目经验，再进一步展开说明吗？"
    )

    try:
        question_meta = get_question_by_role_and_content(db, data.role, data.question)
        print("追问题库信息：", question_meta)

        llm_question = call_llm_for_followup({
            "role": data.role,
            "roleName": data.roleName,
            "question": data.question,
            "type": data.type,
            "answer": data.answer,
            "difficulty": question_meta.get("difficulty") if question_meta else "",
            "tags": question_meta.get("tags") if question_meta else "",
            "keyPoints": question_meta.get("keyPoints") if question_meta else "",
            "scoringFocus": question_meta.get("scoringFocus") if question_meta else "",
            "referenceAnswerBasic": question_meta.get("referenceAnswerBasic") if question_meta else "",
            "referenceAnswerGood": question_meta.get("referenceAnswerGood") if question_meta else "",
            "followupFocus": question_meta.get("followupFocus") if question_meta else "",
            "followupExamples": question_meta.get("followupExamples") if question_meta else ""
        })

        if llm_question:
            follow_up_question = llm_question

    except Exception as e:
        print("追问生成失败，已回退到默认追问：", e)

    return {
        "followUpQuestion": follow_up_question
    }


@app.post("/api/report/generate")
def generate_report(
    data: InterviewSubmitRequest,
    current_user=Depends(get_optional_current_user),
    db=Depends(get_db),
):
    answer_texts = []
    for item in data.answers:
        merged_text = item.answer
        follow_up_answer = getattr(item, "followUpAnswer", "")
        if follow_up_answer:
            merged_text += " " + follow_up_answer
        answer_texts.append(merged_text)

    enriched_answers = []

    for item in data.answers:
        question_meta = get_question_by_role_and_content(db, data.role, item.question)

        enriched_answers.append({
            "question": item.question,
            "type": item.type,
            "answer": item.answer,
            "followUpQuestion": item.followUpQuestion,
            "followUpAnswer": item.followUpAnswer,
            "difficulty": question_meta.get("difficulty") if question_meta else "",
            "tags": question_meta.get("tags") if question_meta else "",
            "keyPoints": question_meta.get("keyPoints") if question_meta else "",
            "scoringFocus": question_meta.get("scoringFocus") if question_meta else "",
            "referenceAnswerBasic": question_meta.get("referenceAnswerBasic") if question_meta else "",
            "referenceAnswerGood": question_meta.get("referenceAnswerGood") if question_meta else "",
            "followupFocus": question_meta.get("followupFocus") if question_meta else "",
            "followupExamples": question_meta.get("followupExamples") if question_meta else ""
        })

    legacy_tech_score = calculate_tech_score(data.role, answer_texts)
    legacy_expression_score = calculate_expression_score(answer_texts)
    legacy_logic_score = calculate_logic_score(answer_texts)
    legacy_match_score = calculate_match_score(data.role, answer_texts)

    bonus_result = calculate_type_bonus(data.role, [item.model_dump() for item in data.answers])

    legacy_tech_score = min(legacy_tech_score + bonus_result["tech_bonus"], 95)
    legacy_expression_score = min(legacy_expression_score + bonus_result["expression_bonus"], 95)
    legacy_logic_score = min(legacy_logic_score + bonus_result["logic_bonus"], 95)
    legacy_match_score = min(legacy_match_score + bonus_result["match_bonus"], 95)

    legacy_total_score = calculate_total_score(
        data.role,
        legacy_tech_score,
        legacy_expression_score,
        legacy_logic_score,
        legacy_match_score
    )
    legacy_scores = {
        "techScore": legacy_tech_score,
        "expressionScore": legacy_expression_score,
        "logicScore": legacy_logic_score,
        "matchScore": legacy_match_score,
        "totalScore": legacy_total_score
    }

    matrix_result = build_feature_matrix(data.role, enriched_answers)
    final_scores = blend_scores(matrix_result["scores"], legacy_scores, matrix_weight=0.7)
    feature_matrix = matrix_result["questionRows"]

    tech_score = final_scores["techScore"]
    expression_score = final_scores["expressionScore"]
    logic_score = final_scores["logicScore"]
    match_score = final_scores["matchScore"]
    total_score = final_scores["totalScore"]

    summary = "整体能够完成本次模拟面试，但部分回答仍可进一步补充技术细节和表达层次。"
    historical_insight = ""
    historical_suggestions = []

    strengths = generate_strengths(
        data.role,
        tech_score,
        expression_score,
        logic_score,
        match_score
    )

    weaknesses = generate_weaknesses(
        data.role,
        tech_score,
        expression_score,
        logic_score,
        match_score
    )

    suggestions = generate_suggestions(data.role)

    question_reports = []
    for index, item in enumerate(enriched_answers):
        matrix_row = feature_matrix[index] if index < len(feature_matrix) else {}
        features = matrix_row.get("features", {})
        question_reports.append({
            "question": item["question"],
            "comment": "本题已完成作答，系统已结合关键点覆盖、评分重点命中、参考答案相似度和回答结构进行评估。",
            "coveredKeyPoints": features.get("coveredKeyPoints", []),
            "missingKeyPoints": features.get("missingKeyPoints", []),
            "advice": "建议优先补充缺失关键点，并结合原理、边界条件、实际场景或验证方式展开。"
        })

    profile_summary = {}
    user_id = current_user.id if current_user else None
    if user_id:
        try:
            profile_summary = get_user_history_summary(db, user_id)
            user = get_user_by_id(db, user_id)
            if user:
                try:
                    profile_llm_result = call_llm_for_profile_summary({
                        "username": user.username,
                        **profile_summary
                    })
                    profile_summary["aiSummary"] = profile_llm_result.get("aiSummary", "")
                    profile_summary["aiSuggestions"] = profile_llm_result.get("aiSuggestions", [])
                except Exception as e:
                    print("历史摘要 AI 生成失败，继续使用规则摘要：", e)
        except Exception as e:
            print("读取历史摘要失败：", e)

    try:
        llm_result = call_llm_for_feedback({
            "role": data.role,
            "roleName": data.roleName,
            "answers": enriched_answers,
            "profileSummary": profile_summary,
            "scores": {
                "techScore": tech_score,
                "expressionScore": expression_score,
                "logicScore": logic_score,
                "matchScore": match_score,
                "totalScore": total_score,
                "confidence": final_scores.get("confidence", 0),
                "scoreSource": final_scores.get("scoreSource", ""),
                "matrixWeight": final_scores.get("matrixWeight", 0)
            },
            "legacyScores": legacy_scores,
            "matrixScores": matrix_result["scores"],
            "featureMatrix": feature_matrix
        })

        if llm_result.get("summary"):
            summary = llm_result["summary"]

        if llm_result.get("historicalInsight"):
            historical_insight = llm_result["historicalInsight"]

        if llm_result.get("strengths"):
            strengths = llm_result["strengths"]

        if llm_result.get("weaknesses"):
            weaknesses = llm_result["weaknesses"]

        if llm_result.get("suggestions"):
            suggestions = llm_result["suggestions"]

        if llm_result.get("historicalSuggestions"):
            historical_suggestions = llm_result["historicalSuggestions"]

        if llm_result.get("questionReports"):
            question_reports = llm_result["questionReports"]

    except Exception as e:
        print("LLM 调用失败，已回退到规则反馈：", e)

    return {
        "role": data.role,
        "roleName": data.roleName,
        "submitTime": data.submitTime,
        "answerCount": len(data.answers),
        "totalScore": total_score,
        "techScore": tech_score,
        "expressionScore": expression_score,
        "logicScore": logic_score,
        "matchScore": match_score,
        "summary": summary,
        "historicalInsight": historical_insight,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "suggestions": suggestions,
        "historicalSuggestions": historical_suggestions,
        "questionReports": question_reports,
        "featureMatrix": feature_matrix,
        "scoreMeta": {
            "scoreSource": final_scores.get("scoreSource", ""),
            "matrixWeight": final_scores.get("matrixWeight", 0),
            "confidence": final_scores.get("confidence", 0),
            "legacyScores": legacy_scores,
            "matrixScores": matrix_result["scores"]
        }
    }


@app.post("/api/history/add")
def add_history(
    record: HistoryRecord,
    current_user=Depends(require_current_user),
    db=Depends(get_db),
):
    record_data = record.model_dump()
    record_data["userId"] = current_user.id
    add_history_record(db, record_data)
    return {
        "message": "history saved successfully"
    }


@app.get("/api/history/list")
def get_history(current_user=Depends(require_current_user), db=Depends(get_db)):
    history = get_history_list(db, current_user.id)
    return {
        "history": history
    }


@app.delete("/api/history/clear")
def clear_history(current_user=Depends(require_current_user), db=Depends(get_db)):
    clear_history_records(db, current_user.id)
    return {
        "message": "history cleared successfully"
    }


@app.get("/api/admin/questions")
def admin_get_questions(role: Optional[str] = None, db=Depends(get_db)):
    questions = get_all_questions(db, role)
    return {
        "questions": questions
    }


@app.post("/api/admin/questions")
def admin_add_question(data: QuestionCreateRequest, db=Depends(get_db)):
    question = add_question(db, data.model_dump())
    return {
        "message": "question added successfully",
        "question": question
    }


@app.put("/api/admin/questions/{question_id}")
def admin_update_question(question_id: int, data: QuestionCreateRequest, db=Depends(get_db)):
    question = update_question(db, question_id, data.model_dump())
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    return {
        "message": "question updated successfully",
        "question": question
    }


@app.delete("/api/admin/questions/{question_id}")
def admin_delete_question(question_id: int, db=Depends(get_db)):
    success = delete_question(db, question_id)
    if not success:
        raise HTTPException(status_code=404, detail="Question not found")

    return {
        "message": "question deleted successfully"
    }


@app.post("/api/auth/register")
def register(data: RegisterRequest, db=Depends(get_db)):
    existing_user = get_user_by_username(db, data.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = create_user(
        db,
        username=data.username,
        password_hash=hash_password(data.password)
    )

    return {
        "message": "register success",
        "user": {
            "id": user.id,
            "username": user.username
        }
    }


@app.post("/api/auth/login")
def login(data: LoginRequest, db=Depends(get_db)):
    user = get_user_by_username(db, data.username)
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if is_legacy_password_hash(user.password_hash):
        user.password_hash = hash_password(data.password)
        db.commit()

    return {
        "message": "login success",
        "accessToken": create_access_token(user.id, user.username),
        "user": {
            "id": user.id,
            "username": user.username
        }
    }


@app.get("/api/auth/user/{user_id}")
def get_current_user(user_id: int, current_user=Depends(require_current_user)):
    if user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问其他用户信息")
    return {"user": {"id": current_user.id, "username": current_user.username}}


@app.get("/api/profile/summary")
def get_profile_summary(current_user=Depends(require_current_user), db=Depends(get_db)):
    user = current_user

    summary = get_user_history_summary(db, user.id)

    ai_summary = ""
    ai_suggestions = []

    try:
        llm_result = call_llm_for_profile_summary({
            "username": user.username,
            **summary
        })
        ai_summary = llm_result.get("aiSummary", "")
        ai_suggestions = llm_result.get("aiSuggestions", [])
    except Exception as e:
        print("个人成长摘要 AI 生成失败，已回退到规则摘要：", e)

    return {
        "userId": user.id,
        "username": user.username,
        **summary,
        "aiSummary": ai_summary,
        "aiSuggestions": ai_suggestions
    }


@app.get("/api/career/dashboard")
def get_career_dashboard(current_user=Depends(require_current_user), db=Depends(get_db)):
    user_id = current_user.id
    resume = get_resume_profile(db, user_id)
    jobs = get_jobs_by_user(db, user_id)
    enriched_jobs = [{**job, "match": score_job_match(resume, job)} for job in jobs]
    status_counts = {status: 0 for status in ("saved", "applied", "interviewing", "offer", "rejected")}
    for job in enriched_jobs:
        status = job["applicationStatus"]
        status_counts[status] = status_counts.get(status, 0) + 1
    average_match = round(sum(job["match"]["score"] for job in enriched_jobs) / len(enriched_jobs)) if enriched_jobs else 0
    progressed_count = status_counts["applied"] + status_counts["interviewing"] + status_counts["offer"] + status_counts["rejected"]
    interview_count = status_counts["interviewing"] + status_counts["offer"]
    funnel = {
        "stages": [
            {"key": "saved", "label": "已收藏", "count": status_counts["saved"]},
            {"key": "applied", "label": "已投递", "count": status_counts["applied"]},
            {"key": "interviewing", "label": "进入面试", "count": status_counts["interviewing"]},
            {"key": "offer", "label": "已获 Offer", "count": status_counts["offer"]}
        ],
        "progressedCount": progressed_count,
        "interviewRate": round(interview_count / progressed_count * 100) if progressed_count else 0,
        "offerRate": round(status_counts["offer"] / progressed_count * 100) if progressed_count else 0
    }
    return {
        "resume": resume,
        "jobs": enriched_jobs,
        "resumeVersions": get_resume_versions(db, user_id),
        "followUps": get_pending_follow_ups(db, user_id),
        "summary": {
            "jobCount": len(enriched_jobs),
            "averageMatch": average_match,
            "statusCounts": status_counts,
            "funnel": funnel
        }
    }


@app.put("/api/career/resume")
def upsert_resume(data: ResumeProfileRequest, current_user=Depends(require_current_user), db=Depends(get_db)):
    if not data.resumeText.strip():
        raise HTTPException(status_code=400, detail="简历内容不能为空")
    return {"resume": save_resume_profile(db, current_user.id, data.resumeText.strip(), data.targetRole.strip())}


@app.post("/api/career/jobs")
def add_career_job(data: JobCreateRequest, current_user=Depends(require_current_user), db=Depends(get_db)):
    if not data.title.strip() or not data.company.strip():
        raise HTTPException(status_code=400, detail="职位名称和公司名称不能为空")
    job = create_job(db, current_user.id, data.model_dump())
    resume = get_resume_profile(db, current_user.id)
    return {"job": {**job, "match": score_job_match(resume, job)}}


@app.patch("/api/career/jobs/{job_id}/status")
def change_career_job_status(
    job_id: int,
    data: JobStatusRequest,
    current_user=Depends(require_current_user),
    db=Depends(get_db),
):
    allowed_statuses = {"saved", "applied", "interviewing", "offer", "rejected"}
    if data.applicationStatus not in allowed_statuses:
        raise HTTPException(status_code=400, detail="不支持的职位状态")
    job = update_job_status(db, current_user.id, job_id, data.applicationStatus)
    if not job:
        raise HTTPException(status_code=404, detail="职位不存在")
    resume = get_resume_profile(db, current_user.id)
    return {"job": {**job, "match": score_job_match(resume, job)}}


@app.put("/api/career/jobs/{job_id}")
def update_career_job(
    job_id: int,
    data: JobCreateRequest,
    current_user=Depends(require_current_user),
    db=Depends(get_db),
):
    if not data.title.strip() or not data.company.strip():
        raise HTTPException(status_code=400, detail="职位名称和公司名称不能为空")
    job = update_job(db, current_user.id, job_id, data.model_dump())
    if not job:
        raise HTTPException(status_code=404, detail="职位不存在")
    resume = get_resume_profile(db, current_user.id)
    return {"job": {**job, "match": score_job_match(resume, job)}}


@app.delete("/api/career/jobs/{job_id}")
def delete_career_job(job_id: int, current_user=Depends(require_current_user), db=Depends(get_db)):
    if not delete_job(db, current_user.id, job_id):
        raise HTTPException(status_code=404, detail="职位不存在")
    return {"message": "职位已删除"}


@app.post("/api/career/jobs/{job_id}/follow-ups")
def add_job_follow_up(
    job_id: int,
    data: FollowUpCreateRequest,
    current_user=Depends(require_current_user),
    db=Depends(get_db),
):
    if not data.dueAt.strip() or not data.note.strip():
        raise HTTPException(status_code=400, detail="请填写跟进时间和跟进事项")
    if not get_job_by_id(db, current_user.id, job_id):
        raise HTTPException(status_code=404, detail="职位不存在")
    return {"followUp": create_follow_up(db, current_user.id, job_id, data.dueAt.strip(), data.note.strip())}


@app.patch("/api/career/follow-ups/{follow_up_id}/complete")
def finish_job_follow_up(follow_up_id: int, current_user=Depends(require_current_user), db=Depends(get_db)):
    follow_up = complete_follow_up(db, current_user.id, follow_up_id)
    if not follow_up:
        raise HTTPException(status_code=404, detail="跟进事项不存在")
    return {"followUp": follow_up}


@app.post("/api/career/jobs/{job_id}/prepare")
def prepare_for_career_job(
    job_id: int,
    data: JobStatusRequest,
    current_user=Depends(require_current_user),
    db=Depends(get_db),
):
    resume = get_resume_profile(db, current_user.id)
    if not resume:
        raise HTTPException(status_code=400, detail="请先保存简历，再生成职位准备建议")
    job = get_job_by_id(db, current_user.id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="职位不存在")

    match = score_job_match(resume, job)
    preparation = build_job_preparation(resume, job, match)
    try:
        llm_result = call_llm_for_job_preparation({
            "resumeText": resume["resumeText"],
            "jobTitle": job["title"],
            "company": job["company"],
            "jobRequirements": job["requiredSkills"],
            "jobDescription": job["description"],
            "match": match
        })
        if llm_result.get("summary"):
            preparation = llm_result
    except Exception as error:
        print("职位准备建议 AI 生成失败，已回退到规则建议：", error)

    return {"jobId": job_id, "preparation": preparation}


@app.post("/api/career/jobs/{job_id}/resume-draft")
def generate_tailored_resume_draft(
    job_id: int,
    data: CareerUserRequest,
    current_user=Depends(require_current_user),
    db=Depends(get_db),
):
    resume = get_resume_profile(db, current_user.id)
    if not resume:
        raise HTTPException(status_code=400, detail="请先保存原始简历，再生成定制草稿")
    job = get_job_by_id(db, current_user.id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="职位不存在")
    match = score_job_match(resume, job)
    draft = {
        "source": "rule",
        "title": f"{job['company']} · {job['title']} · 简历草稿",
        "content": resume["resumeText"]
    }
    try:
        llm_result = call_llm_for_tailored_resume({
            "resumeText": resume["resumeText"],
            "jobTitle": job["title"],
            "company": job["company"],
            "jobRequirements": job["requiredSkills"],
            "jobDescription": job["description"],
            "match": match
        })
        draft = llm_result
    except Exception as error:
        print("定制简历草稿 AI 生成失败，已回退到原始简历：", error)
    return {"jobId": job_id, "draft": draft}


@app.post("/api/career/jobs/{job_id}/interview-questions")
def generate_job_interview_questions(
    job_id: int,
    data: CareerUserRequest,
    current_user=Depends(require_current_user),
    db=Depends(get_db),
):
    resume = get_resume_profile(db, current_user.id)
    if not resume:
        raise HTTPException(status_code=400, detail="请先保存简历，再生成 JD 专项面试题")
    job = get_job_by_id(db, current_user.id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="职位不存在")
    match = score_job_match(resume, job)
    questions = build_job_interview_questions(job, match)
    source = "rule"
    try:
        llm_questions = call_llm_for_job_interview_questions({
            "resumeText": resume["resumeText"],
            "jobTitle": job["title"],
            "company": job["company"],
            "jobRequirements": job["requiredSkills"],
            "jobDescription": job["description"],
            "match": match
        })
        if llm_questions:
            questions = llm_questions
            source = "llm"
    except Exception as error:
        print("JD 专项面试题 AI 生成失败，已回退到规则题目：", error)
    return {"jobId": job_id, "source": source, "questions": questions}


@app.post("/api/career/resume-versions")
def save_resume_version(
    data: ResumeVersionCreateRequest,
    current_user=Depends(require_current_user),
    db=Depends(get_db),
):
    if not data.title.strip() or not data.content.strip():
        raise HTTPException(status_code=400, detail="版本名称和简历内容不能为空")
    if data.jobId and not get_job_by_id(db, current_user.id, data.jobId):
        raise HTTPException(status_code=404, detail="关联职位不存在")
    version = create_resume_version(db, current_user.id, data.model_dump())
    return {"version": version}


@app.get("/api/career/action-plan")
def get_career_action_plan(current_user=Depends(require_current_user), db=Depends(get_db)):
    user_id = current_user.id
    resume = get_resume_profile(db, user_id)
    jobs = get_jobs_by_user(db, user_id)
    enriched_jobs = [{**job, "match": score_job_match(resume, job)} for job in jobs]
    plan = build_daily_action_plan(resume, enriched_jobs)
    try:
        llm_result = call_llm_for_daily_action_plan({
            "resume": resume,
            "jobs": enriched_jobs,
            "rulePlan": plan
        })
        if llm_result.get("summary"):
            plan = llm_result
    except Exception as error:
        print("每日行动计划 AI 生成失败，已回退到规则计划：", error)
    return {"plan": plan}
