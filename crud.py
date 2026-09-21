import json
import re
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


SKILL_CATALOG = [
    "Java", "Python", "JavaScript", "TypeScript", "Vue", "React", "Node.js",
    "Spring Boot", "Spring", "MySQL", "Redis", "Docker", "Kubernetes", "Git",
    "Linux", "FastAPI", "SQL", "HTML", "CSS", "Nginx", "Kafka", "RabbitMQ",
    "机器学习", "数据分析", "产品设计", "测试", "自动化测试"
]


def extract_skills(text: str):
    normalized = (text or "").lower()
    result = []
    for skill in SKILL_CATALOG:
        skill_normalized = skill.lower()
        if re.search(r"[a-z]", skill_normalized):
            pattern = rf"(?<![a-z0-9+#.]){re.escape(skill_normalized)}(?![a-z0-9+#.])"
            if re.search(pattern, normalized):
                result.append(skill)
        elif skill_normalized in normalized:
            result.append(skill)
    return result


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


def score_job_match(resume: dict | None, job: dict):
    resume_skills = resume.get("skills", []) if resume else []
    source_text = " ".join([
        job.get("requiredSkills", ""), job.get("description", ""), job.get("title", "")
    ])
    required = extract_skills(source_text)
    if job.get("requiredSkills"):
        required = list(dict.fromkeys(required + extract_skills(job["requiredSkills"])))
    matched = [skill for skill in required if skill in resume_skills]
    missing = [skill for skill in required if skill not in resume_skills]
    target_role = (resume.get("targetRole", "") if resume else "").lower()
    title = job.get("title", "").lower()
    role_bonus = 10 if target_role and (target_role in title or title in target_role) else 0
    if not resume:
        score = 0
    elif required:
        score = min(95, round(len(matched) / len(required) * 85 + role_bonus))
    else:
        score = min(80, 45 + role_bonus + min(len(resume_skills) * 3, 25))
    return {
        "score": score,
        "matchedSkills": matched,
        "missingSkills": missing,
        "requiredSkills": required,
        "reason": "已根据简历技能与职位要求计算匹配度；保存简历后可获得更准确结果。" if resume else "请先在驾驶舱保存简历，系统才能计算匹配度。"
    }


def build_job_preparation(resume: dict, job: dict, match: dict):
    missing_skills = match.get("missingSkills", [])
    matched_skills = match.get("matchedSkills", [])
    title = job.get("title", "目标职位")
    resume_actions = []

    if matched_skills:
        resume_actions.append(
            f"在简历项目经历中突出 {'、'.join(matched_skills[:3])}，写清使用场景、个人职责和量化结果。"
        )
    if missing_skills:
        resume_actions.append(
            f"若有真实项目或学习成果，可补充 {'、'.join(missing_skills[:3])} 的相关经历；没有经历时不要虚构。"
        )
    if not resume_actions:
        resume_actions.append("将每段项目经历改写为“背景—职责—行动—结果”，并为结果补充可验证的数据。")

    interview_focus = missing_skills[:3] or matched_skills[:3] or ["岗位核心业务", "项目经历", "技术选型"]
    return {
        "source": "rule",
        "summary": f"{title} 当前匹配度为 {match.get('score', 0)} 分。优先补足职位明确要求的技能证据，再准备可量化的项目案例。",
        "resumeActions": resume_actions,
        "interviewFocus": [f"准备 {skill} 的应用场景、实现细节、边界条件和复盘案例。" for skill in interview_focus],
        "nextActions": [
            "确认职位要求与个人经历是否真实对应，再决定是否投递。",
            "按以上简历建议创建一个仅针对该职位的简历副本。",
            "进入模拟面试，围绕目标职位完成一次专项练习。"
        ]
    }


def build_daily_action_plan(resume: dict | None, jobs: list[dict]):
    actions = []
    if not resume:
        actions.append({
            "priority": "high",
            "title": "完成简历画像",
            "description": "粘贴并保存简历文本，让 Agent 能按真实技能评估每个职位。",
            "jobId": None
        })

    interviewing = [job for job in jobs if job.get("applicationStatus") == "interviewing"]
    for job in interviewing[:2]:
        actions.append({
            "priority": "high",
            "title": f"准备 {job['company']} · {job['title']} 面试",
            "description": "生成该职位的申请准备清单，并针对缺失技能完成一次专项模拟面试。",
            "jobId": job["id"]
        })

    saved_jobs = [job for job in jobs if job.get("applicationStatus") == "saved"]
    high_match_saved = sorted(saved_jobs, key=lambda job: job.get("match", {}).get("score", 0), reverse=True)
    for job in high_match_saved[:2]:
        score = job.get("match", {}).get("score", 0)
        missing = job.get("match", {}).get("missingSkills", [])
        if score >= 65:
            description = "核对简历中是否有真实项目证据，再创建该职位专用简历副本并决定是否投递。"
        elif missing:
            description = f"优先补充或学习 {'、'.join(missing[:2])} 的真实案例，再决定是否投递。"
        else:
            description = "先生成申请准备建议，补强项目表达和量化结果。"
        actions.append({
            "priority": "medium",
            "title": f"处理收藏职位：{job['title']}",
            "description": description,
            "jobId": job["id"]
        })

    if not jobs:
        actions.append({
            "priority": "medium",
            "title": "录入目标职位",
            "description": "添加 3 个真实感兴趣的职位，建立可比较的求职优先级。",
            "jobId": None
        })
    if not actions:
        actions.append({
            "priority": "low",
            "title": "复盘当前求职进度",
            "description": "更新职位状态，并针对近期目标岗位完成一次模拟面试。",
            "jobId": None
        })

    actions = actions[:4]
    high_count = sum(1 for action in actions if action["priority"] == "high")
    return {
        "source": "rule",
        "summary": f"今日共有 {len(actions)} 项行动，其中 {high_count} 项高优先级。优先处理正在推进的机会和匹配度较高的收藏职位。",
        "actions": actions
    }


def build_job_interview_questions(job: dict, match: dict):
    matched = match.get("matchedSkills", [])
    missing = match.get("missingSkills", [])
    focus = (matched + missing)[:3] or [job.get("title", "目标岗位")]
    primary_skill = focus[0]
    company = job.get("company", "目标公司")
    title = job.get("title", "目标职位")
    raw_questions = [
        ("project", "medium", f"请介绍一段与你申请 {company} 的 {title} 最相关的项目经历：你的职责、关键实现和结果分别是什么？"),
        ("technical", "medium", f"结合真实经历，说明你如何使用 {primary_skill} 解决具体问题；请补充技术选型和效果验证。"),
        ("scenario", "hard", f"如果 {company} 的线上核心功能出现性能或稳定性问题，你会如何定位、处理并验证结果？"),
        ("technical", "hard", f"针对 {primary_skill}，请说明一个边界条件、风险点或性能权衡，以及你的应对方案。"),
        ("project", "medium", f"该职位还关注 {'、'.join(missing[:2]) if missing else '业务理解与协作'}，你会如何基于真实经历证明自己的学习和交付能力？")
    ]
    return [
        {"id": f"job-{job['id']}-{index + 1}", "type": question_type, "difficulty": difficulty, "content": content}
        for index, (question_type, difficulty, content) in enumerate(raw_questions)
    ]


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
    history = HistoryRecordModel(
        user_id=record.get("userId"),
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
