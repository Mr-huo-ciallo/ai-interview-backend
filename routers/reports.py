from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
import logging
import threading
import time

from fastapi import APIRouter, Depends

from crud import get_question_by_role_and_content, get_user_by_id, get_user_history_summary
from db import get_db
from dependencies import get_optional_current_user, require_current_user
from llm_client import call_llm_for_feedback, call_llm_for_profile_summary
from llm_payloads import build_question_context
from rate_limit import create_rate_limiter
from schemas import InterviewSubmitRequest
from scoring.matrix import blend_scores, build_feature_matrix
from scoring.rules import (
    calculate_expression_score,
    calculate_logic_score,
    calculate_match_score,
    calculate_tech_score,
    calculate_total_score,
    calculate_type_bonus,
    generate_strengths,
    generate_suggestions,
    generate_weaknesses,
)


logger = logging.getLogger(__name__)
router = APIRouter(tags=["reports"])
report_rate_limit = create_rate_limiter("report", "RATE_LIMIT_REPORT_MAX", 10)

PROFILE_AI_CACHE_TTL_SECONDS = 300
_profile_ai_cache_lock = threading.Lock()
_profile_ai_cache: dict[tuple, tuple[float, dict]] = {}


def _get_cached_profile_ai(cache_key: tuple) -> dict | None:
    now = time.monotonic()
    with _profile_ai_cache_lock:
        cached = _profile_ai_cache.get(cache_key)
        if not cached:
            return None
        expires_at, value = cached
        if expires_at <= now:
            _profile_ai_cache.pop(cache_key, None)
            return None
        return value


def _set_cached_profile_ai(cache_key: tuple, value: dict) -> None:
    with _profile_ai_cache_lock:
        _profile_ai_cache[cache_key] = (time.monotonic() + PROFILE_AI_CACHE_TTL_SECONDS, value)


@router.post("/api/report/generate")
def generate_report(
    data: InterviewSubmitRequest,
    _rate_limit=Depends(report_rate_limit),
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
        if not question_meta and (
            item.keyPoints or item.scoringFocus or item.tags or item.referenceAnswerBasic or item.referenceAnswerGood
        ):
            question_meta = {
                "difficulty": item.difficulty or "medium",
                "tags": item.tags,
                "keyPoints": item.keyPoints,
                "scoringFocus": item.scoringFocus,
                "referenceAnswerBasic": item.referenceAnswerBasic,
                "referenceAnswerGood": item.referenceAnswerGood,
            }

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
        legacy_match_score,
    )
    legacy_scores = {
        "techScore": legacy_tech_score,
        "expressionScore": legacy_expression_score,
        "logicScore": legacy_logic_score,
        "matchScore": legacy_match_score,
        "totalScore": legacy_total_score,
    }
    matrix_result = build_feature_matrix(data.role, enriched_answers)
    final_scores = blend_scores(matrix_result["scores"], legacy_scores, matrix_weight=0.7)
    feature_matrix = matrix_result["questionRows"]

    tech_score = final_scores["techScore"]
    expression_score = final_scores["expressionScore"]
    logic_score = final_scores["logicScore"]
    match_score = final_scores["matchScore"]
    total_score = final_scores["totalScore"]

    summary = (
        "整体能够完成本次模拟面试，但部分回答仍需补充用户证据、决策依据和效果验证。"
        if data.role == "product_manager"
        else "整体能够完成本次模拟面试，但部分回答仍可进一步补充技术细节和表达层次。"
    )
    historical_insight = ""
    historical_suggestions = []

    strengths = generate_strengths(
        data.role, tech_score, expression_score, logic_score, match_score
    )
    weaknesses = generate_weaknesses(
        data.role, tech_score, expression_score, logic_score, match_score
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
            "advice": (
                "建议补充用户与业务目标、方案取舍依据，以及可检验的结果指标。"
                if data.role == "product_manager"
                else "建议优先补充缺失关键点，并结合原理、边界条件、实际场景或验证方式展开。"
            ),
        })

    profile_summary = {}
    profile_ai_payload = None
    profile_cache_key = None
    user_id = current_user.id if current_user else None
    if user_id:
        try:
            profile_summary = get_user_history_summary(db, user_id)
            user = get_user_by_id(db, user_id)
            if user:
                profile_cache_key = (
                    user_id,
                    profile_summary.get("interviewCount", 0),
                    profile_summary.get("avgScore", 0),
                )
                cached_profile_ai = _get_cached_profile_ai(profile_cache_key)
                if cached_profile_ai:
                    profile_summary["aiSummary"] = cached_profile_ai.get("aiSummary", "")
                    profile_summary["aiSuggestions"] = cached_profile_ai.get("aiSuggestions", [])
                elif profile_summary.get("interviewCount", 0) > 0:
                    profile_ai_payload = {
                        "username": user.username,
                        **profile_summary,
                    }
        except Exception:
            logger.warning("读取历史摘要失败", exc_info=True)

    feedback_payload = {
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
            "matrixWeight": final_scores.get("matrixWeight", 0),
        },
        "legacyScores": legacy_scores,
        "matrixScores": matrix_result["scores"],
        "featureMatrix": feature_matrix,
    }

    try:
        if profile_ai_payload:
            feedback_ctx = copy_context()
            profile_ctx = copy_context()
            with ThreadPoolExecutor(max_workers=2) as executor:
                feedback_future = executor.submit(feedback_ctx.run, call_llm_for_feedback, feedback_payload)
                profile_future = executor.submit(profile_ctx.run, call_llm_for_profile_summary, profile_ai_payload)
                llm_result = feedback_future.result()
                try:
                    profile_llm_result = profile_future.result(timeout=1.0)
                    if profile_cache_key and profile_llm_result:
                        _set_cached_profile_ai(profile_cache_key, profile_llm_result)
                except Exception:
                    logger.warning("历史摘要 AI 并行生成未完成或失败，继续返回本次报告", exc_info=True)
        else:
            llm_result = call_llm_for_feedback(feedback_payload)

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
        "jobId": data.jobId,
        "jobTitle": data.jobTitle,
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
            "matrixScores": matrix_result["scores"],
        },
    }


@router.get("/api/profile/summary")
def get_profile_summary(current_user=Depends(require_current_user), db=Depends(get_db)):
    user = current_user
    summary = get_user_history_summary(db, user.id)
    cache_key = (user.id, summary.get("interviewCount", 0), summary.get("avgScore", 0))
    cached = _get_cached_profile_ai(cache_key)

    ai_summary = ""
    ai_suggestions = []

    if cached:
        ai_summary = cached.get("aiSummary", "")
        ai_suggestions = cached.get("aiSuggestions", [])
    else:
        try:
            llm_result = call_llm_for_profile_summary({
                "username": user.username,
                **summary,
            })
            ai_summary = llm_result.get("aiSummary", "")
            ai_suggestions = llm_result.get("aiSuggestions", [])
            _set_cached_profile_ai(cache_key, llm_result)
        except Exception:
            logger.warning("个人成长摘要 AI 生成失败，已回退到规则摘要", exc_info=True)

    return {
        "userId": user.id,
        "username": user.username,
        **summary,
        "aiSummary": ai_summary,
        "aiSuggestions": ai_suggestions,
    }
