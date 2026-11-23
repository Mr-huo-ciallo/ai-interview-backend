import re


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
