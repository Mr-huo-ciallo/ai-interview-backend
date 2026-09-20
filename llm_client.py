import os
import json
import httpx

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")


def build_prompt(payload: dict) -> str:
    role_name = payload.get("roleName") or payload.get("role") or "目标岗位"
    answers = payload.get("answers", [])
    scores = payload.get("scores", {})
    legacy_scores = payload.get("legacyScores", {})
    matrix_scores = payload.get("matrixScores", {})
    feature_matrix = payload.get("featureMatrix", [])
    profile_summary = payload.get("profileSummary", {})

    answer_text = []
    for index, item in enumerate(answers, start=1):
        answer_text.append(
            f"""
题目 {index}：
- 题目：{item.get("question", "")}
- 题型：{item.get("type", "")}
- 难度：{item.get("difficulty", "")}
- 候选人回答：{item.get("answer", "")}
- 追问回答：{item.get("followUpAnswer", "")}
- 题库关键点：{item.get("keyPoints", "")}
- 评分重点：{item.get("scoringFocus", "")}
- 基础参考答案：{item.get("referenceAnswerBasic", "")}
- 优秀参考答案：{item.get("referenceAnswerGood", "")}
""".strip()
        )

    return f"""
你是一名技术面试评估助手。请基于候选人回答、题库关键点和规则版特征矩阵，生成结构化中文反馈。

重要约束：
1. 分数已经由后端规则和特征矩阵计算完成，你只能解释分数依据，不允许重新打分或修改分数。
2. 必须优先参考 featureMatrix 中的覆盖情况、缺失关键点、题型分项分和 confidence。
3. 对每道题说明“已覆盖什么、缺失什么、下一步如何补强”，避免空泛评价。
4. 只输出合法 JSON，不要输出 markdown、代码块或额外说明。

目标岗位：{role_name}

最终分数：
{json.dumps(scores, ensure_ascii=False, indent=2)}

旧规则分：
{json.dumps(legacy_scores, ensure_ascii=False, indent=2)}

矩阵分：
{json.dumps(matrix_scores, ensure_ascii=False, indent=2)}

逐题特征矩阵：
{json.dumps(feature_matrix, ensure_ascii=False, indent=2)}

历史表现摘要：
{json.dumps(profile_summary, ensure_ascii=False, indent=2)}

候选人作答：
{chr(10).join(answer_text)}

请严格输出如下 JSON 结构：
{{
  "summary": "总评，说明整体能力水平、主要依据和最需要提升的方向",
  "historicalInsight": "结合历史摘要给出的趋势观察；没有历史数据则返回空字符串",
  "strengths": ["优势1", "优势2", "优势3"],
  "weaknesses": ["短板1", "短板2", "短板3"],
  "suggestions": ["建议1", "建议2", "建议3"],
  "historicalSuggestions": ["历史维度建议1", "历史维度建议2"],
  "questionReports": [
    {{
      "question": "题目原文",
      "comment": "结合矩阵特征说明本题表现",
      "coveredKeyPoints": ["已覆盖关键点"],
      "missingKeyPoints": ["缺失关键点"],
      "advice": "下一步补强建议"
    }}
  ]
}}
""".strip()


def call_llm_for_feedback(payload: dict):
    if not LLM_API_KEY or not LLM_BASE_URL or not LLM_MODEL:
        raise RuntimeError("LLM 配置不完整，请设置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL")

    prompt = build_prompt(payload)

    body = {
        "model": LLM_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是严格输出 JSON 的技术面试评估助手。"
                    "后端已经完成打分，你只负责基于特征矩阵解释依据、总结优劣势并给出改进建议。"
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2
    }

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }

    api_url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"

    with httpx.Client(timeout=60.0) as client:
        response = client.post(api_url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"].strip()

    if content.startswith("```"):
        content = content.replace("```json", "").replace("```", "").strip()

    result = json.loads(content)

    return {
        "summary": result.get("summary", ""),
        "historicalInsight": result.get("historicalInsight", ""),
        "strengths": result.get("strengths", []),
        "weaknesses": result.get("weaknesses", []),
        "suggestions": result.get("suggestions", []),
        "historicalSuggestions": result.get("historicalSuggestions", []),
        "questionReports": result.get("questionReports", [])
    }


def analyze_answer_quality(payload: dict) -> dict:
    answer = payload["answer"].strip()
    q_type = payload["type"]
    answer_lower = answer.lower()

    length_score = len(answer)

    project_words = ["项目", "负责", "模块", "实现", "优化", "难点", "接口", "数据库", "缓存"]
    technical_words = [
        "redis", "mysql", "spring", "spring boot", "vue", "react",
        "索引", "缓存", "事务", "组件", "性能", "原理", "机制"
    ]
    scenario_words = ["首先", "其次", "然后", "最后", "排查", "分析", "方案", "优化", "验证", "定位"]

    technical_depth_words = [
        "过期时间", "一致性", "穿透", "击穿", "雪崩",
        "热点数据", "数据库压力", "单线程", "高并发",
        "持久化", "哨兵", "集群", "锁", "降级", "限流"
    ]

    def count_hits(words):
        return sum(1 for word in words if word.lower() in answer_lower or word in answer)

    project_hits = count_hits(project_words)
    technical_hits = count_hits(technical_words)
    scenario_hits = count_hits(scenario_words)
    technical_depth_hits = count_hits(technical_depth_words)

    if q_type == "project":
        if length_score < 35 or project_hits < 2:
            level = "brief"
        elif length_score < 100 or project_hits < 4:
            level = "medium"
        else:
            level = "complete"

    elif q_type == "technical":
        if length_score < 30 or technical_hits < 2:
            level = "brief"
        elif technical_depth_hits >= 2 or length_score >= 90:
            level = "complete"
        else:
            level = "medium"

    elif q_type == "scenario":
        if length_score < 35 or scenario_hits < 2:
            level = "brief"
        elif length_score < 100 or scenario_hits < 4:
            level = "medium"
        else:
            level = "complete"
    else:
        if length_score < 40:
            level = "brief"
        elif length_score < 100:
            level = "medium"
        else:
            level = "complete"

    return {
        "level": level,
        "project_hits": project_hits,
        "technical_hits": technical_hits,
        "scenario_hits": scenario_hits,
        "technical_depth_hits": technical_depth_hits,
        "length": length_score
    }


def detect_followup_mode(payload: dict) -> str:
    q_type = payload["type"]
    quality = analyze_answer_quality(payload)
    level = quality["level"]

    if q_type == "project":
        if level == "brief":
            return "project_brief"
        if level == "medium":
            return "project_detail"
        return "project_verification"

    if q_type == "technical":
        if level == "brief":
            return "technical_usage"
        if level == "medium":
            return "technical_principle"
        return "technical_verification"

    if q_type == "scenario":
        if level == "brief":
            return "scenario_brief"
        if level == "medium":
            return "scenario_analysis"
        return "scenario_tradeoff"

    return "verification"


def build_followup_prompt(payload: dict) -> str:
    mode = payload.get("followUpMode", "expand")
    mode_instruction = {
        "too_short": "候选人回答过短，请追问一个能引导其补充核心技术点、实现过程或项目细节的问题。",
        "too_generic": "候选人回答偏泛，请追问一个要求其说明具体方案、取舍依据或落地细节的问题。",
        "technical_depth": "候选人已经覆盖基础内容，请追问一个更深入的原理、边界条件、性能或可靠性问题。",
        "scenario_based": "候选人回答具备场景信息，请追问一个真实排查、优化、权衡或复盘类问题。",
        "project_detail": "候选人提到项目经历，请追问其个人职责、关键实现、难点处理或结果验证。",
        "normal": "请围绕当前题目和回答，提出一个自然、具体、有区分度的追问问题。"
    }.get(mode, "请围绕当前题目和回答，提出一个自然、具体、有区分度的追问问题。")

    return f"""
你是一名技术面试官，请根据题目、候选人回答和题库参考信息生成一个追问问题。

追问要求：
1. 只输出一个问题，不要解释原因。
2. 问题必须贴合候选人的当前回答，避免模板化。
3. 优先追问缺失关键点、实现细节、边界条件、性能权衡或项目落地结果。
4. 问题长度控制在 35 字以内。

追问策略：{mode_instruction}

目标岗位：{payload.get("roleName", "")}
题型：{payload.get("type", "")}
当前题目：{payload.get("question", "")}
候选人回答：{payload.get("answer", "")}
题库关键点：{payload.get("keyPoints", "")}
评分重点：{payload.get("scoringFocus", "")}
追问关注点：{payload.get("followupFocus", "")}
""".strip()


def call_llm_for_followup(payload: dict) -> str:
    if not LLM_API_KEY or not LLM_BASE_URL or not LLM_MODEL:
        raise RuntimeError("LLM 配置不完整，请设置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL")

    followup_mode = detect_followup_mode(payload)
    print("当前追问模式：", followup_mode)

    prompt = build_followup_prompt({
        **payload,
        "followUpMode": followup_mode
    })

    body = {
        "model": LLM_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是一名技术面试官。请只输出一个简洁、具体、贴合回答内容的追问问题。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.6
    }

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }

    api_url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"

    with httpx.Client(timeout=60.0) as client:
        response = client.post(api_url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"].strip()
    return content.replace("```", "").strip()


def build_profile_summary_prompt(payload: dict) -> str:
    return f"""
你是一名技术面试成长分析助手。请根据用户历史面试摘要，生成个性化成长总结。

用户信息：
- 用户名：{payload.get("username", "")}
- 面试总次数：{payload.get("interviewCount", 0)}
- 平均分：{payload.get("avgScore", 0)}
- 最高分：{payload.get("bestScore", 0)}
- 最低分：{payload.get("worstScore", 0)}
- 最近常练岗位：{", ".join(payload.get("topRoles", []))}
- 最近常见题型：{", ".join(payload.get("topQuestionTypes", []))}
- 高频知识点标签：{", ".join(payload.get("topTags", []))}
- 当前规则建议：{"；".join(payload.get("recommendedFocus", []))}

请严格输出 JSON，不要输出额外解释，格式如下：
{{
  "aiSummary": "一段个性化成长总结",
  "aiSuggestions": ["建议1", "建议2", "建议3"]
}}

要求：
1. aiSummary 要像对候选人的阶段性分析，语言自然
2. aiSuggestions 要具体、可执行，2到4条
3. 要结合历史练习倾向、知识点覆盖和分数情况
4. 不要输出 markdown，不要加代码块
""".strip()


def call_llm_for_profile_summary(payload: dict):
    if not LLM_API_KEY or not LLM_BASE_URL or not LLM_MODEL:
        raise RuntimeError("LLM 配置不完整，请设置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL")

    prompt = build_profile_summary_prompt(payload)

    body = {
        "model": LLM_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是一个严格输出 JSON 的技术面试成长分析助手。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.4
    }

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }

    api_url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"

    with httpx.Client(timeout=60.0) as client:
        response = client.post(api_url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"].strip()

    if content.startswith("```"):
        content = content.replace("```json", "").replace("```", "").strip()

    result = json.loads(content)

    return {
        "aiSummary": result.get("aiSummary", ""),
        "aiSuggestions": result.get("aiSuggestions", [])
    }


def call_llm_for_job_preparation(payload: dict):
    if not LLM_API_KEY or not LLM_BASE_URL or not LLM_MODEL:
        raise RuntimeError("LLM 配置不完整，请设置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL")

    prompt = f"""
你是一名求职辅导助手。请基于候选人简历、目标职位和规则匹配结果，生成求职准备建议。

约束：
1. 只能建议如何表达真实经历；严禁建议虚构项目、技能、学历或工作经历。
2. 不要代表用户投递或联系招聘方。
3. 只输出合法 JSON，不能使用 markdown 或代码块。

简历文本：{payload.get('resumeText', '')}
目标岗位：{payload.get('jobTitle', '')}
公司：{payload.get('company', '')}
职位要求：{payload.get('jobRequirements', '')}
职位描述：{payload.get('jobDescription', '')}
规则匹配结果：{json.dumps(payload.get('match', {}), ensure_ascii=False)}

输出：
{{
  "summary": "一句针对该职位的准备判断",
  "resumeActions": ["简历优化建议，2-4条"],
  "interviewFocus": ["面试准备点，2-4条"],
  "nextActions": ["下一步执行动作，2-4条"]
}}
""".strip()
    body = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "你是严格输出 JSON 的求职准备助手，不得建议虚构经历。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }
    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    api_url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"
    with httpx.Client(timeout=60.0) as client:
        response = client.post(api_url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()
    content = data["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = content.replace("```json", "").replace("```", "").strip()
    result = json.loads(content)
    return {
        "source": "llm",
        "summary": result.get("summary", ""),
        "resumeActions": result.get("resumeActions", []),
        "interviewFocus": result.get("interviewFocus", []),
        "nextActions": result.get("nextActions", [])
    }


def call_llm_for_daily_action_plan(payload: dict):
    if not LLM_API_KEY or not LLM_BASE_URL or not LLM_MODEL:
        raise RuntimeError("LLM 配置不完整，请设置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL")
    prompt = f"""
你是一名求职 Agent。请根据候选人简历状态、职位列表和规则初稿，给出今天最可执行的求职行动计划。

约束：
1. 不能建议虚构经历、自动投递、自动发送消息或绕过招聘平台。
2. 高优先级只留给正在面试、简历缺失或确实应立即处理的事项。
3. 只输出合法 JSON，不要使用 markdown。

简历是否已保存：{bool(payload.get('resume'))}
职位数据：{json.dumps(payload.get('jobs', []), ensure_ascii=False)}
规则初稿：{json.dumps(payload.get('rulePlan', {}), ensure_ascii=False)}

输出：
{{
  "summary": "一句今日策略总结",
  "actions": [
    {{"priority": "high|medium|low", "title": "简洁任务名", "description": "具体且可执行的说明", "jobId": 1}}
  ]
}}
""".strip()
    body = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "你是严格输出 JSON 的求职 Agent，始终尊重用户确认和真实经历。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.25
    }
    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    api_url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"
    with httpx.Client(timeout=60.0) as client:
        response = client.post(api_url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()
    content = data["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = content.replace("```json", "").replace("```", "").strip()
    result = json.loads(content)
    actions = result.get("actions", [])
    if not isinstance(actions, list):
        actions = []
    normalized_actions = []
    for action in actions[:4]:
        if not isinstance(action, dict) or not action.get("title") or not action.get("description"):
            continue
        priority = action.get("priority")
        normalized_actions.append({
            "priority": priority if priority in {"high", "medium", "low"} else "medium",
            "title": str(action["title"]),
            "description": str(action["description"]),
            "jobId": action.get("jobId")
        })
    if not normalized_actions:
        raise ValueError("LLM 未返回有效行动计划")
    return {"source": "llm", "summary": result.get("summary", ""), "actions": normalized_actions}


def call_llm_for_tailored_resume(payload: dict):
    if not LLM_API_KEY or not LLM_BASE_URL or not LLM_MODEL:
        raise RuntimeError("LLM 配置不完整，请设置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL")
    prompt = f"""
你是一名简历优化助手。请仅基于原始简历真实存在的信息，生成适配目标职位的中文简历草稿。

严格约束：
1. 不得编造公司、项目、学历、技能、业绩、年限或数据；无法确认的数据应删去或保留原表述。
2. 优化重点是排序、措辞、结构和与 JD 的真实关联，不是夸大。
3. 只输出合法 JSON，不要使用 markdown 代码块。

原始简历：{payload.get('resumeText', '')}
目标职位：{payload.get('jobTitle', '')}
公司：{payload.get('company', '')}
职位要求：{payload.get('jobRequirements', '')}
职位描述：{payload.get('jobDescription', '')}
匹配结果：{json.dumps(payload.get('match', {}), ensure_ascii=False)}

输出：
{{
  "title": "适配职位的简历版本名称",
  "content": "完整可编辑的中文简历草稿纯文本"
}}
""".strip()
    body = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "你是严格输出 JSON 的简历优化助手，绝不编造候选人经历。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }
    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    api_url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"
    with httpx.Client(timeout=60.0) as client:
        response = client.post(api_url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()
    content = data["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = content.replace("```json", "").replace("```", "").strip()
    result = json.loads(content)
    if not result.get("content"):
        raise ValueError("LLM 未返回简历草稿")
    return {"source": "llm", "title": result.get("title", "JD 定制简历草稿"), "content": result["content"]}


def call_llm_for_job_interview_questions(payload: dict):
    if not LLM_API_KEY or not LLM_BASE_URL or not LLM_MODEL:
        raise RuntimeError("LLM 配置不完整，请设置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL")
    prompt = f"""
你是一名技术面试官。请根据候选人的真实简历、目标 JD 和技能匹配结果，生成 5 道中文专项模拟面试题。

要求：
1. 题目必须围绕目标职位和候选人真实经历，不得假定候选人拥有简历中不存在的技能或项目。
2. 覆盖项目经历、技术深度和场景分析三类问题。
3. 只输出合法 JSON，不要 markdown。

候选人简历：{payload.get('resumeText', '')}
目标职位：{payload.get('jobTitle', '')}
公司：{payload.get('company', '')}
职位要求：{payload.get('jobRequirements', '')}
职位描述：{payload.get('jobDescription', '')}
匹配结果：{json.dumps(payload.get('match', {}), ensure_ascii=False)}

输出：
{{"questions":[{{"content":"题目", "type":"project|technical|scenario", "difficulty":"easy|medium|hard"}}]}}
""".strip()
    body = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "你是严格输出 JSON 的技术面试官，题目必须基于真实候选人信息。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.45
    }
    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    api_url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"
    with httpx.Client(timeout=60.0) as client:
        response = client.post(api_url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()
    content = data["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = content.replace("```json", "").replace("```", "").strip()
    result = json.loads(content)
    questions = result.get("questions", [])
    normalized = []
    for index, item in enumerate(questions[:5]):
        if not isinstance(item, dict) or not str(item.get("content", "")).strip():
            continue
        normalized.append({
            "id": f"job-ai-{index + 1}",
            "content": str(item["content"]).strip(),
            "type": item.get("type") if item.get("type") in {"project", "technical", "scenario"} else "technical",
            "difficulty": item.get("difficulty") if item.get("difficulty") in {"easy", "medium", "hard"} else "medium"
        })
    if len(normalized) < 3:
        raise ValueError("LLM 未返回足够的专项面试题")
    return normalized
