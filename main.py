import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import logging

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from auth_utils import (
    create_access_token,
    hash_password,
    is_legacy_password_hash,
    verify_password,
)

from llm_client import (
    call_llm_for_feedback,
    call_llm_for_profile_summary,
)
from llm_payloads import build_question_context
from db import get_db
from dependencies import get_optional_current_user, require_current_user
from config import validate_runtime_config
from observability import RequestLoggingMiddleware, configure_logging, get_request_id
from crud import (
    create_user,
    get_user_by_username,
    get_user_by_id,
    add_history_record,
    get_history_list,
    clear_history_records,
    get_question_by_role_and_content,
    get_user_history_summary,
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
from routers.career import router as career_router
from routers.questions import router as questions_router
from schemas import (
    HistoryRecord,
    InterviewSubmitRequest,
    LoginRequest,
    RegisterRequest,
)

logger = logging.getLogger(__name__)

app = FastAPI()

configure_logging()
validate_runtime_config()

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
app.include_router(career_router)
app.include_router(questions_router)


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


@app.get("/")
def read_root():
    return {"message": "AI Interview Backend is running"}


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
            **build_question_context(question_meta),
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
                except Exception:
                    logger.warning("历史摘要 AI 生成失败，继续使用规则摘要", exc_info=True)
        except Exception:
            logger.warning("读取历史摘要失败", exc_info=True)

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

    except Exception:
        logger.warning("LLM 调用失败，已回退到规则反馈", exc_info=True)

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
    except Exception:
        logger.warning("个人成长摘要 AI 生成失败，已回退到规则摘要", exc_info=True)

    return {
        "userId": user.id,
        "username": user.username,
        **summary,
        "aiSummary": ai_summary,
        "aiSuggestions": ai_suggestions
    }
