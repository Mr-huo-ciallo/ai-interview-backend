import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from crud import (
    add_question,
    delete_question,
    get_all_questions,
    get_question_by_role_and_content,
    get_questions_by_role,
    update_question,
)
from db import get_db
from llm_client import call_llm_for_followup
from llm_payloads import build_question_context
from schemas import FollowUpRequest, QuestionCreateRequest
from scoring.config import SUPPORTED_ROLES


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/questions")
def get_questions(role: str = "java", db=Depends(get_db)):
    questions = get_questions_by_role(db, role)

    if not questions and role not in SUPPORTED_ROLES:
        questions = get_questions_by_role(db, "java")

    return {"role": role, "questions": questions}


@router.post("/api/interview/follow-up")
def generate_followup(data: FollowUpRequest, db=Depends(get_db)):
    fallback_map = {
        "project": "你在这个项目中具体负责哪些模块？遇到过什么技术难点？",
        "technical": "你能进一步解释一下这个技术点背后的原理或适用场景吗？",
        "scenario": "如果让你一步步落地解决，你会先从哪一步开始排查？",
    }
    follow_up_question = fallback_map.get(
        data.type,
        "你可以结合具体项目经验，再进一步展开说明吗？",
    )
    if data.role == "product_manager":
        follow_up_question = {
            "project": "你如何确认用户问题，并验证最终方案产生了预期效果？",
            "technical": "你会用哪些证据支持这个产品判断？",
            "scenario": "在资源有限时，你会如何比较方案的价值、成本和风险？",
        }.get(data.type, "你会如何验证这个产品方案是否有效？")

    try:
        question_meta = get_question_by_role_and_content(db, data.role, data.question)
        logger.debug("追问题库信息已加载 role=%s found=%s", data.role, bool(question_meta))
        llm_question = call_llm_for_followup({
            "role": data.role,
            "roleName": data.roleName,
            "question": data.question,
            "type": data.type,
            "answer": data.answer,
            **build_question_context(question_meta),
        })
        if llm_question:
            follow_up_question = llm_question
    except Exception:
        logger.warning("追问生成失败，已回退到默认追问", exc_info=True)

    return {"followUpQuestion": follow_up_question}


@router.get("/api/admin/questions")
def admin_get_questions(role: Optional[str] = None, db=Depends(get_db)):
    return {"questions": get_all_questions(db, role)}


@router.post("/api/admin/questions")
def admin_add_question(data: QuestionCreateRequest, db=Depends(get_db)):
    return {
        "message": "question added successfully",
        "question": add_question(db, data.model_dump()),
    }


@router.put("/api/admin/questions/{question_id}")
def admin_update_question(question_id: int, data: QuestionCreateRequest, db=Depends(get_db)):
    question = update_question(db, question_id, data.model_dump())
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return {"message": "question updated successfully", "question": question}


@router.delete("/api/admin/questions/{question_id}")
def admin_delete_question(question_id: int, db=Depends(get_db)):
    if not delete_question(db, question_id):
        raise HTTPException(status_code=404, detail="Question not found")
    return {"message": "question deleted successfully"}
