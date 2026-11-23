import json
from sqlalchemy.orm import Session
from models import (
    UserModel,
    HistoryRecordModel,
    InterviewQuestionModel,
    ResumeProfileModel,
    JobPostModel,
    ResumeVersionModel,
    JobFollowUpModel,
)
from collections import Counter
from services.career_rules import (  # noqa: F401 - 兼容旧导入路径
    SKILL_CATALOG,
    build_daily_action_plan,
    build_job_interview_questions,
    build_job_preparation,
    extract_skills,
    score_job_match,
)


def serialize_resume(item: ResumeProfileModel | None):
    if not item:
        return None
    return {
        "id": item.id,
        "userId": item.user_id,
        "resumeText": item.resume_text,
        "skills": json.loads(item.skills_json or "[]"),
        "targetRole": item.target_role or "",
        "updatedAt": item.updated_at.isoformat() if item.updated_at else ""
    }


def get_resume_profile(db: Session, user_id: int):
    return serialize_resume(
        db.query(ResumeProfileModel).filter(ResumeProfileModel.user_id == user_id).first()
    )


def save_resume_profile(db: Session, user_id: int, resume_text: str, target_role: str = ""):
    skills = extract_skills(resume_text)
    profile = db.query(ResumeProfileModel).filter(ResumeProfileModel.user_id == user_id).first()
    if profile:
        profile.resume_text = resume_text
        profile.skills_json = json.dumps(skills, ensure_ascii=False)
        profile.target_role = target_role
    else:
        profile = ResumeProfileModel(
            user_id=user_id,
            resume_text=resume_text,
            skills_json=json.dumps(skills, ensure_ascii=False),
            target_role=target_role,
        )
        db.add(profile)
    db.commit()
    db.refresh(profile)
    return serialize_resume(profile)


def serialize_job(item: JobPostModel):
    return {
        "id": item.id,
        "userId": item.user_id,
        "title": item.title,
        "company": item.company,
        "location": item.location or "",
        "salary": item.salary or "",
        "requiredSkills": item.required_skills or "",
        "description": item.description or "",
        "sourceUrl": item.source_url or "",
        "applicationStatus": item.application_status,
        "createdAt": item.created_at.isoformat() if item.created_at else ""
    }


def _build_job(user_id: int, data: dict):
    return JobPostModel(
        user_id=user_id,
        title=data["title"].strip(),
        company=data["company"].strip(),
        location=data.get("location", "").strip(),
        salary=data.get("salary", "").strip(),
        required_skills=data.get("requiredSkills", "").strip(),
        description=data.get("description", "").strip(),
        source_url=data.get("sourceUrl", "").strip(),
    )


def create_job(db: Session, user_id: int, data: dict):
    job = _build_job(user_id, data)
    db.add(job)
    db.commit()
    db.refresh(job)
    return serialize_job(job)


def create_jobs(db: Session, user_id: int, items: list[dict]):
    jobs = [_build_job(user_id, data) for data in items]
    db.add_all(jobs)
    db.commit()
    for job in jobs:
        db.refresh(job)
    return [serialize_job(job) for job in jobs]


def get_jobs_by_user(db: Session, user_id: int):
    records = (
        db.query(JobPostModel)
        .filter(JobPostModel.user_id == user_id)
        .order_by(JobPostModel.id.desc())
        .all()
    )
    return [serialize_job(item) for item in records]


def get_job_by_id(db: Session, user_id: int, job_id: int):
    item = (
        db.query(JobPostModel)
        .filter(JobPostModel.id == job_id, JobPostModel.user_id == user_id)
        .first()
    )
    return serialize_job(item) if item else None


def update_job_status(db: Session, user_id: int, job_id: int, status: str):
    job = (
        db.query(JobPostModel)
        .filter(JobPostModel.id == job_id, JobPostModel.user_id == user_id)
        .first()
    )
    if not job:
        return None
    job.application_status = status
    db.commit()
    db.refresh(job)
    return serialize_job(job)


def update_job(db: Session, user_id: int, job_id: int, data: dict):
    job = (
        db.query(JobPostModel)
        .filter(JobPostModel.id == job_id, JobPostModel.user_id == user_id)
        .first()
    )
    if not job:
        return None
    job.title = data["title"].strip()
    job.company = data["company"].strip()
    job.location = data.get("location", "").strip()
    job.salary = data.get("salary", "").strip()
    job.required_skills = data.get("requiredSkills", "").strip()
    job.description = data.get("description", "").strip()
    job.source_url = data.get("sourceUrl", "").strip()
    db.commit()
    db.refresh(job)
    return serialize_job(job)


def delete_job(db: Session, user_id: int, job_id: int):
    job = (
        db.query(JobPostModel)
        .filter(JobPostModel.id == job_id, JobPostModel.user_id == user_id)
        .first()
    )
    if not job:
        return False
    db.delete(job)
    db.commit()
    return True


def serialize_resume_version(item: ResumeVersionModel):
    return {
        "id": item.id,
        "userId": item.user_id,
        "jobId": item.job_id,
        "title": item.title,
        "content": item.content,
        "source": item.source,
        "createdAt": item.created_at.isoformat() if item.created_at else ""
    }


def create_resume_version(db: Session, user_id: int, data: dict):
    version = ResumeVersionModel(
        user_id=user_id,
        job_id=data.get("jobId"),
        title=data["title"].strip(),
        content=data["content"].strip(),
        source=data.get("source", "manual")
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return serialize_resume_version(version)


def get_resume_versions(db: Session, user_id: int, limit: int = 6):
    versions = (
        db.query(ResumeVersionModel)
        .filter(ResumeVersionModel.user_id == user_id)
        .order_by(ResumeVersionModel.id.desc())
        .limit(limit)
        .all()
    )
    return [serialize_resume_version(item) for item in versions]


def serialize_follow_up(item: JobFollowUpModel, job: JobPostModel | None = None):
    return {
        "id": item.id,
        "jobId": item.job_id,
        "jobTitle": job.title if job else "",
        "company": job.company if job else "",
        "dueAt": item.due_at,
        "note": item.note,
        "completed": item.completed,
        "createdAt": item.created_at.isoformat() if item.created_at else ""
    }


def create_follow_up(db: Session, user_id: int, job_id: int, due_at: str, note: str):
    item = JobFollowUpModel(user_id=user_id, job_id=job_id, due_at=due_at, note=note)
    db.add(item)
    db.commit()
    db.refresh(item)
    job = db.query(JobPostModel).filter(JobPostModel.id == job_id).first()
    return serialize_follow_up(item, job)


def get_pending_follow_ups(db: Session, user_id: int, limit: int = 8):
    records = (
        db.query(JobFollowUpModel, JobPostModel)
        .outerjoin(JobPostModel, JobFollowUpModel.job_id == JobPostModel.id)
        .filter(JobFollowUpModel.user_id == user_id, JobFollowUpModel.completed.is_(False))
        .order_by(JobFollowUpModel.due_at.asc(), JobFollowUpModel.id.asc())
        .limit(limit)
        .all()
    )
    return [serialize_follow_up(item, job) for item, job in records]


def complete_follow_up(db: Session, user_id: int, follow_up_id: int):
    item = (
        db.query(JobFollowUpModel)
        .filter(JobFollowUpModel.id == follow_up_id, JobFollowUpModel.user_id == user_id)
        .first()
    )
    if not item:
        return None
    item.completed = True
    db.commit()
    db.refresh(item)
    job = db.query(JobPostModel).filter(JobPostModel.id == item.job_id).first()
    return serialize_follow_up(item, job)


def add_history_record(db: Session, record: dict):
    job_id = record.get("jobId")
    if job_id is not None:
        exists = db.query(JobPostModel.id).filter(JobPostModel.id == job_id).first()
        if not exists:
            job_id = None
    history = HistoryRecordModel(
        user_id=record.get("userId"),
        job_id=job_id,
        job_title=(record.get("jobTitle") or "").strip() or None,
        role=record["role"],
        role_name=record["roleName"],
        total_score=record["totalScore"],
        answer_count=record["answerCount"],
        submit_time=record["submitTime"],
        answers_json=json.dumps(record["answers"], ensure_ascii=False),
        feature_matrix_json=json.dumps(record.get("featureMatrix") or [], ensure_ascii=False),
        score_meta_json=json.dumps(record.get("scoreMeta") or {}, ensure_ascii=False)
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    return history


def get_history_list(db: Session, user_id: int | None = None, job_id: int | None = None):
    query = db.query(HistoryRecordModel)

    if user_id is not None:
        query = query.filter(HistoryRecordModel.user_id == user_id)
    if job_id is not None:
        query = query.filter(HistoryRecordModel.job_id == job_id)

    records = query.order_by(HistoryRecordModel.id.desc()).all()

    result = []
    for item in records:
        result.append({
            "id": item.id,
            "userId": item.user_id,
            "jobId": item.job_id,
            "jobTitle": item.job_title or "",
            "role": item.role,
            "roleName": item.role_name,
            "totalScore": item.total_score,
            "answerCount": item.answer_count,
            "submitTime": item.submit_time,
            "answers": json.loads(item.answers_json),
            "featureMatrix": json.loads(item.feature_matrix_json or "[]"),
            "scoreMeta": json.loads(item.score_meta_json or "{}")
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
def create_user(db: Session, username: str, password_hash: str, is_admin: bool = False):
    user = UserModel(
        username=username,
        password_hash=password_hash,
        is_admin=is_admin,
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
