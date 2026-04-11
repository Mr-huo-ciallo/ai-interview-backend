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


def build_followup_prompt(payload: dict) -> str:
    return f"""
你是一名技术面试官，请基于候选人的目标岗位、题目类型、当前题目和候选人的回答，生成一个更深入、更具体的追问问题。

要求：
1. 只输出一句追问问题
2. 追问必须和当前回答强相关
3. 追问要体现技术面试风格
4. 如果候选人回答太泛泛，就追问“具体负责什么/如何实现/遇到什么问题”
5. 如果候选人回答缺少技术细节，就追问“原理/实现/优化/排查”
6. 不要输出解释，不要输出编号，不要输出 JSON

目标岗位：{payload["roleName"]}
题型：{payload["type"]}
当前题目：{payload["question"]}
候选人回答：{payload["answer"]}
""".strip()


def call_llm_for_followup(payload: dict) -> str:
    if not LLM_API_KEY or not LLM_BASE_URL or not LLM_MODEL:
        raise RuntimeError("LLM 配置不完整，请设置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL")

    prompt = build_followup_prompt(payload)

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
    content = content.replace("```", "").strip()

    return content