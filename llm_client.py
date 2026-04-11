import os
import json
import httpx


LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")


def build_prompt(payload: dict) -> str:
    role_name = payload["roleName"]
    answers = payload["answers"]
    scores = payload["scores"]

    answer_text = []
    for idx, item in enumerate(answers, start=1):
        answer_text.append(
            f"第{idx}题\n"
            f"题型：{item.get('type', '')}\n"
            f"问题：{item.get('question', '')}\n"
            f"回答：{item.get('answer', '')}\n"
            f"追问回答：{item.get('followUpAnswer', '')}\n"
        )

    answer_block = "\n".join(answer_text)

    prompt = f"""
你是一名技术面试评估助手。请根据候选人的岗位、题目、回答内容，以及系统提供的规则评分，生成结构化评估结果。

目标岗位：{role_name}

规则评分：
- 技术能力分：{scores["techScore"]}
- 表达能力分：{scores["expressionScore"]}
- 逻辑严谨性分：{scores["logicScore"]}
- 岗位匹配度分：{scores["matchScore"]}
- 综合得分：{scores["totalScore"]}

作答内容：
{answer_block}

请严格输出 JSON，且不要输出任何额外解释。格式如下：
{{
  "strengths": ["亮点1", "亮点2", "亮点3"],
  "weaknesses": ["不足1", "不足2", "不足3"],
  "suggestions": ["建议1", "建议2", "建议3"]
}}

要求：
1. strengths / weaknesses / suggestions 都返回数组
2. 每个数组建议 2 到 4 条
3. 内容必须贴合计算机技术岗位面试场景
4. 语言简洁、具体、可执行
5. 不要输出 markdown，不要加代码块
""".strip()

    return prompt


def call_llm_for_feedback(payload: dict):
    if not LLM_API_KEY or not LLM_BASE_URL or not LLM_MODEL:
        raise RuntimeError("LLM 配置不完整，请设置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL")

    prompt = build_prompt(payload)

    body = {
        "model": LLM_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是一个严格输出 JSON 的技术面试评估助手。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3
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
        "strengths": result.get("strengths", []),
        "weaknesses": result.get("weaknesses", []),
        "suggestions": result.get("suggestions", [])
    }


def detect_followup_mode(payload: dict) -> str:
    answer = payload["answer"].strip()
    q_type = payload["type"]

    answer_lower = answer.lower()

    short_threshold = len(answer) < 40
    has_project_signals = any(word in answer for word in ["项目", "负责", "实现", "优化", "模块"])
    has_logic_signals = any(word in answer for word in ["首先", "其次", "然后", "最后", "排查", "分析", "方案"])
    has_principle_signals = any(word in answer_lower for word in [
        "redis", "mysql", "spring", "vue", "react", "索引", "缓存", "事务", "组件", "性能"
    ])

    if q_type == "project":
        if short_threshold or not has_project_signals:
            return "project_detail"
        return "verification"

    if q_type == "technical":
        if short_threshold or not has_principle_signals:
            return "technical_principle"
        return "verification"

    if q_type == "scenario":
        if short_threshold or not has_logic_signals:
            return "scenario_analysis"
        return "verification"

    return "verification"


def build_followup_prompt(payload: dict) -> str:
    followup_mode = payload["followUpMode"]

    mode_instruction_map = {
        "project_detail": """
请优先生成“项目深挖型追问”。
重点追问：
- 候选人在项目中的具体职责
- 技术难点
- 技术方案选择原因
- 实际优化效果
""".strip(),

        "technical_principle": """
请优先生成“技术原理型追问”。
重点追问：
- 底层原理
- 为什么这样设计
- 适用场景
- 优缺点或局限
""".strip(),

        "scenario_analysis": """
请优先生成“场景分析型追问”。
重点追问：
- 排查顺序
- 分析思路
- 解决方案
- 取舍和验证方式
""".strip(),

        "verification": """
请优先生成“反问验证型追问”。
重点追问：
- 候选人是否真正理解刚才的回答
- 方案可能的风险或改进点
- 如果条件变化，方案是否仍成立
""".strip()
    }

    mode_instruction = mode_instruction_map.get(
        followup_mode,
        mode_instruction_map["verification"]
    )

    return f"""
你是一名技术面试官，请基于候选人的目标岗位、题目类型、当前题目和候选人的回答，生成一个更深入、更具体的追问问题。

本次追问类型：{followup_mode}

附加要求：
{mode_instruction}

通用要求：
1. 只输出一句追问问题
2. 追问必须和当前回答强相关
3. 追问要体现技术面试风格
4. 不要输出解释，不要输出编号，不要输出 JSON
5. 不要总是重复“你能详细介绍如何在项目中应用吗”这类表达
6. 尽量让追问更自然、更有针对性

目标岗位：{payload["roleName"]}
题型：{payload["type"]}
当前题目：{payload["question"]}
候选人回答：{payload["answer"]}
""".strip()


def call_llm_for_followup(payload: dict) -> str:
    if not LLM_API_KEY or not LLM_BASE_URL or not LLM_MODEL:
        raise RuntimeError("LLM 配置不完整，请设置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL")

    followup_mode = detect_followup_mode(payload)

    prompt = build_followup_prompt({
        **payload,
        "followUpMode": followup_mode
    })

    body = {
        "model": LLM_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是一名技术面试官，请输出一句简洁、具体、贴合回答内容的追问问题。"
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
    content = content.replace("```", "").strip()

    return content