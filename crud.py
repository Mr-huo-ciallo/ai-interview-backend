import json
from sqlalchemy.orm import Session
from models import HistoryRecordModel, InterviewQuestionModel


def add_history_record(db: Session, record: dict):
    history = HistoryRecordModel(
        role=record["role"],
        role_name=record["roleName"],
        total_score=record["totalScore"],
        answer_count=record["answerCount"],
        submit_time=record["submitTime"],
        answers_json=json.dumps(record["answers"], ensure_ascii=False)
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    return history


def get_history_list(db: Session):
    records = db.query(HistoryRecordModel).order_by(HistoryRecordModel.id.desc()).all()

    result = []
    for item in records:
        result.append({
            "id": item.id,
            "role": item.role,
            "roleName": item.role_name,
            "totalScore": item.total_score,
            "answerCount": item.answer_count,
            "submitTime": item.submit_time,
            "answers": json.loads(item.answers_json)
        })
    return result


def clear_history_records(db: Session):
    db.query(HistoryRecordModel).delete()
    db.commit()


def get_questions_by_role(db: Session, role: str):
    records = (
        db.query(InterviewQuestionModel)
        .filter(InterviewQuestionModel.role == role)
        .order_by(InterviewQuestionModel.sort_order.asc(), InterviewQuestionModel.id.asc())
        .all()
    )

    return [
        {
            "id": item.id,
            "role": item.role,
            "type": item.type,
            "content": item.content,
            "sortOrder": item.sort_order
        }
        for item in records
    ]


def get_all_questions(db: Session, role: str | None = None):
    query = db.query(InterviewQuestionModel)

    if role:
        query = query.filter(InterviewQuestionModel.role == role)

    records = query.order_by(
        InterviewQuestionModel.role.asc(),
        InterviewQuestionModel.sort_order.asc(),
        InterviewQuestionModel.id.asc()
    ).all()

    return [
        {
            "id": item.id,
            "role": item.role,
            "type": item.type,
            "content": item.content,
            "sortOrder": item.sort_order
        }
        for item in records
    ]


def add_question(db: Session, question_data: dict):
    question = InterviewQuestionModel(
        role=question_data["role"],
        type=question_data["type"],
        content=question_data["content"],
        sort_order=question_data["sortOrder"]
    )
    db.add(question)
    db.commit()
    db.refresh(question)

    return {
        "id": question.id,
        "role": question.role,
        "type": question.type,
        "content": question.content,
        "sortOrder": question.sort_order
    }


def delete_question(db: Session, question_id: int):
    question = db.query(InterviewQuestionModel).filter(
        InterviewQuestionModel.id == question_id
    ).first()

    if not question:
        return False

    db.delete(question)
    db.commit()
    return True