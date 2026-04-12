from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from llm_client import call_llm_for_feedback, call_llm_for_followup
from db import SessionLocal, engine, Base
from models import HistoryRecordModel, InterviewQuestionModel
from crud import (
    add_history_record,
    get_history_list,
    clear_history_records,
    get_questions_by_role,
    get_all_questions,
    add_question,
    delete_question,
    get_question_by_id,
    update_question,
    get_question_by_role_and_content
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

app = FastAPI()

Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    role: str
    roleName: str
    answers: List[AnswerItem]
    submitTime: str


class HistoryRecord(BaseModel):
    role: str
    roleName: str
    totalScore: int
    answerCount: int
    submitTime: str
    answers: List[AnswerItem]


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


@app.get("/")
def read_root():
    return {"message": "AI Interview Backend is running"}


@app.get("/api/questions")
def get_questions(role: str = "java"):
    db = SessionLocal()
    try:
        questions = get_questions_by_role(db, role)

        if not questions and role != "java":
            questions = get_questions_by_role(db, "java")

        return {
            "role": role,
            "questions": questions
        }
    finally:
        db.close()


@app.post("/api/interview/follow-up")
def generate_followup(data: FollowUpRequest):
    fallback_map = {
        "project": "你在这个项目中具体负责哪些模块？遇到过什么技术难点？",
        "technical": "你能进一步解释一下这个技术点背后的原理或适用场景吗？",
        "scenario": "如果让你一步步落地解决，你会先从哪一步开始排查？"
    }

    follow_up_question = fallback_map.get(
        data.type,
        "你可以结合具体项目经验，再进一步展开说明吗？"
    )

    db = SessionLocal()
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
    finally:
        db.close()

    return {
        "followUpQuestion": follow_up_question
    }
@app.post("/api/report/generate")
def generate_report(data: InterviewSubmitRequest):
    answer_texts = []
    for item in data.answers:
        merged_text = item.answer
        follow_up_answer = getattr(item, "followUpAnswer", "")
        if follow_up_answer:
            merged_text += " " + follow_up_answer
        answer_texts.append(merged_text)

    db = SessionLocal()
    try:
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

        tech_score = calculate_tech_score(data.role, answer_texts)
        expression_score = calculate_expression_score(answer_texts)
        logic_score = calculate_logic_score(answer_texts)
        match_score = calculate_match_score(data.role, answer_texts)

        bonus_result = calculate_type_bonus(data.role, [item.model_dump() for item in data.answers])

        tech_score = min(tech_score + bonus_result["tech_bonus"], 95)
        expression_score = min(expression_score + bonus_result["expression_bonus"], 95)
        logic_score = min(logic_score + bonus_result["logic_bonus"], 95)
        match_score = min(match_score + bonus_result["match_bonus"], 95)

        total_score = calculate_total_score(
            data.role,
            tech_score,
            expression_score,
            logic_score,
            match_score
        )

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

        try:
            llm_result = call_llm_for_feedback({
                "role": data.role,
                "roleName": data.roleName,
                "answers": enriched_answers,
                "scores": {
                    "techScore": tech_score,
                    "expressionScore": expression_score,
                    "logicScore": logic_score,
                    "matchScore": match_score,
                    "totalScore": total_score
                }
            })

            if llm_result.get("strengths"):
                strengths = llm_result["strengths"]

            if llm_result.get("weaknesses"):
                weaknesses = llm_result["weaknesses"]

            if llm_result.get("suggestions"):
                suggestions = llm_result["suggestions"]

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
            "strengths": strengths,
            "weaknesses": weaknesses,
            "suggestions": suggestions
        }
    finally:
        db.close()

@app.post("/api/history/add")
def add_history(record: HistoryRecord):
    db = SessionLocal()
    try:
        add_history_record(db, record.model_dump())
        return {
            "message": "history saved successfully"
        }
    finally:
        db.close()


@app.get("/api/history/list")
def get_history():
    db = SessionLocal()
    try:
        history = get_history_list(db)
        return {
            "history": history
        }
    finally:
        db.close()


@app.delete("/api/history/clear")
def clear_history():
    db = SessionLocal()
    try:
        clear_history_records(db)
        return {
            "message": "history cleared successfully"
        }
    finally:
        db.close()


@app.get("/api/admin/questions")
def admin_get_questions(role: Optional[str] = None):
    db = SessionLocal()
    try:
        questions = get_all_questions(db, role)
        return {
            "questions": questions
        }
    finally:
        db.close()


@app.post("/api/admin/questions")
def admin_add_question(data: QuestionCreateRequest):
    db = SessionLocal()
    try:
        question = add_question(db, data.model_dump())
        return {
            "message": "question added successfully",
            "question": question
        }
    finally:
        db.close()
        
@app.put("/api/admin/questions/{question_id}")
def admin_update_question(question_id: int, data: QuestionCreateRequest):
    db = SessionLocal()
    try:
        question = update_question(db, question_id, data.model_dump())
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        return {
            "message": "question updated successfully",
            "question": question
        }
    finally:
        db.close()

@app.delete("/api/admin/questions/{question_id}")
def admin_delete_question(question_id: int):
    db = SessionLocal()
    try:
        success = delete_question(db, question_id)
        if not success:
            raise HTTPException(status_code=404, detail="Question not found")

        return {
            "message": "question deleted successfully"
        }
    finally:
        db.close()