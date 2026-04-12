import json
from sqlalchemy.orm import Session
from models import UserModel, HistoryRecordModel, InterviewQuestionModel
from collections import Counter


def add_history_record(db: Session, record: dict):
    history = HistoryRecordModel(
        user_id=record.get("userId"),
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


def get_history_list(db: Session, user_id: int | None = None):
    query = db.query(HistoryRecordModel)

    if user_id is not None:
        query = query.filter(HistoryRecordModel.user_id == user_id)

    records = query.order_by(HistoryRecordModel.id.desc()).all()

    result = []
    for item in records:
        result.append({
            "id": item.id,
            "userId": item.user_id,
            "role": item.role,
            "roleName": item.role_name,
            "totalScore": item.total_score,
            "answerCount": item.answer_count,
            "submitTime": item.submit_time,
            "answers": json.loads(item.answers_json)
        })
    return result


def clear_history_records(db: Session, user_id: int | None = None):
    query = db.query(HistoryRecordModel)

    if user_id is not None:
        query = query.filter(HistoryRecordModel.user_id == user_id)

    query.delete()
    db.commit()


def serialize_question(item: InterviewQuestionModel):
    return {
        "id": item.id,
        "role": item.role,
        "type": item.type,
        "content": item.content,
        "sortOrder": item.sort_order,
        "difficulty": item.difficulty,
        "tags": item.tags,
        "keyPoints": item.key_points,
        "scoringFocus": item.scoring_focus,
        "referenceAnswerBasic": item.reference_answer_basic,
        "referenceAnswerGood": item.reference_answer_good,
        "followupFocus": item.followup_focus,
        "followupExamples": item.followup_examples
    }


def get_questions_by_role(db: Session, role: str):
    records = (
        db.query(InterviewQuestionModel)
        .filter(InterviewQuestionModel.role == role)
        .order_by(InterviewQuestionModel.sort_order.asc(), InterviewQuestionModel.id.asc())
        .all()
    )

    return [serialize_question(item) for item in records]


def get_all_questions(db: Session, role: str | None = None):
    query = db.query(InterviewQuestionModel)

    if role:
        query = query.filter(InterviewQuestionModel.role == role)

    records = query.order_by(
        InterviewQuestionModel.role.asc(),
        InterviewQuestionModel.sort_order.asc(),
        InterviewQuestionModel.id.asc()
    ).all()

    return [serialize_question(item) for item in records]


def add_question(db: Session, question_data: dict):
    question = InterviewQuestionModel(
        role=question_data["role"],
        type=question_data["type"],
        content=question_data["content"],
        sort_order=question_data.get("sortOrder", 1),
        difficulty=question_data.get("difficulty", "medium"),
        tags=question_data.get("tags"),
        key_points=question_data.get("keyPoints"),
        scoring_focus=question_data.get("scoringFocus"),
        reference_answer_basic=question_data.get("referenceAnswerBasic"),
        reference_answer_good=question_data.get("referenceAnswerGood"),
        followup_focus=question_data.get("followupFocus"),
        followup_examples=question_data.get("followupExamples")
    )
    db.add(question)
    db.commit()
    db.refresh(question)

    return serialize_question(question)


def get_question_by_id(db: Session, question_id: int):
    item = db.query(InterviewQuestionModel).filter(
        InterviewQuestionModel.id == question_id
    ).first()

    if not item:
        return None

    return serialize_question(item)


def update_question(db: Session, question_id: int, question_data: dict):
    item = db.query(InterviewQuestionModel).filter(
        InterviewQuestionModel.id == question_id
    ).first()

    if not item:
        return None

    item.role = question_data["role"]
    item.type = question_data["type"]
    item.content = question_data["content"]
    item.sort_order = question_data.get("sortOrder", 1)
    item.difficulty = question_data.get("difficulty", "medium")
    item.tags = question_data.get("tags")
    item.key_points = question_data.get("keyPoints")
    item.scoring_focus = question_data.get("scoringFocus")
    item.reference_answer_basic = question_data.get("referenceAnswerBasic")
    item.reference_answer_good = question_data.get("referenceAnswerGood")
    item.followup_focus = question_data.get("followupFocus")
    item.followup_examples = question_data.get("followupExamples")

    db.commit()
    db.refresh(item)

    return serialize_question(item)


def delete_question(db: Session, question_id: int):
    question = db.query(InterviewQuestionModel).filter(
        InterviewQuestionModel.id == question_id
    ).first()

    if not question:
        return False

    db.delete(question)
    db.commit()
    return True


def get_question_by_role_and_content(db: Session, role: str, content: str):
    item = (
        db.query(InterviewQuestionModel)
        .filter(
            InterviewQuestionModel.role == role,
            InterviewQuestionModel.content == content
        )
        .first()
    )

    if not item:
        return None

    return serialize_question(item)
def create_user(db: Session, username: str, password_hash: str):
    user = UserModel(
        username=username,
        password_hash=password_hash
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_username(db: Session, username: str):
    return db.query(UserModel).filter(UserModel.username == username).first()


def get_user_by_id(db: Session, user_id: int):
    return db.query(UserModel).filter(UserModel.id == user_id).first()

def get_user_history_summary(db: Session, user_id: int):
    records = (
        db.query(HistoryRecordModel)
        .filter(HistoryRecordModel.user_id == user_id)
        .order_by(HistoryRecordModel.id.desc())
        .all()
    )

    if not records:
        return {
            "interviewCount": 0,
            "avgScore": 0,
            "bestScore": 0,
            "worstScore": 0,
            "topRoles": [],
            "topQuestionTypes": [],
            "topTags": [],
            "recommendedFocus": []
        }

    total_scores = [item.total_score for item in records]
    avg_score = round(sum(total_scores) / len(total_scores), 1)
    best_score = max(total_scores)
    worst_score = min(total_scores)

    role_counter = Counter()
    question_type_counter = Counter()
    tag_counter = Counter()

    for record in records:
        role_counter[record.role] += 1

        answers = json.loads(record.answers_json)
        for answer in answers:
            q_type = answer.get("type")
            question = answer.get("question")

            if q_type:
                question_type_counter[q_type] += 1

            if question and record.role:
                question_meta = (
                    db.query(InterviewQuestionModel)
                    .filter(
                        InterviewQuestionModel.role == record.role,
                        InterviewQuestionModel.content == question
                    )
                    .first()
                )

                if question_meta and question_meta.tags:
                    raw_tags = question_meta.tags.replace("；", ",").replace("，", ",")
                    tag_list = [tag.strip() for tag in raw_tags.split(",") if tag.strip()]
                    for tag in tag_list:
                        tag_counter[tag] += 1

    top_roles = [item[0] for item in role_counter.most_common(3)]
    top_question_types = [item[0] for item in question_type_counter.most_common(3)]
    top_tags = [item[0] for item in tag_counter.most_common(5)]

    recommended_focus = []

    if "Redis" in top_tags or "缓存" in top_tags:
        recommended_focus.append("建议继续强化 Redis、缓存一致性与高并发场景相关知识点。")
    if "MySQL" in top_tags or "索引" in top_tags:
        recommended_focus.append("建议重点复习 MySQL 索引、执行计划与 SQL 优化。")
    if "前端性能优化" in top_tags or "性能优化" in top_tags:
        recommended_focus.append("建议继续训练性能优化题，强化加载优化与渲染优化表达。")
    if "项目经历" in top_tags or "项目题" in top_question_types:
        recommended_focus.append("建议项目题继续按照“背景-职责-难点-结果”结构展开。")
    if "scenario" in top_question_types:
        recommended_focus.append("建议场景题回答中强化“排查顺序-分析依据-解决方案-验证结果”的表达。")

    if not recommended_focus:
        recommended_focus.append("建议继续扩大练习题覆盖范围，并针对薄弱知识点进行专项训练。")

    return {
        "interviewCount": len(records),
        "avgScore": avg_score,
        "bestScore": best_score,
        "worstScore": worst_score,
        "topRoles": top_roles,
        "topQuestionTypes": top_question_types,
        "topTags": top_tags,
        "recommendedFocus": recommended_focus
    }