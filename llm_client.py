import os
import json
import httpx


LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")


def build_followup_prompt(payload: dict) -> str:
    followup_mode = payload["followUpMode"]

    mode_instruction_map = {
        "project_brief": """
请生成“项目补细节型追问”。
目标：
- 补充候选人刚才没有说清楚的职责、模块、实现内容
- 优先问具体负责什么、怎么实现、做了什么优化
禁止：
- 不要问抽象空泛问题
- 不要问“能否详细介绍如何在项目中应用”这类宽泛句式
""".strip(),

        "project_detail": """
请生成“项目深挖型追问”。
目标：
- 深挖技术难点
- 深挖方案选择原因
- 深挖优化效果
禁止：
- 不要退回到只问“你具体负责什么”
""".strip(),

        "project_verification": """
请生成“项目验证型追问”。
目标：
- 验证候选人是否真的理解方案
- 追问改进点、局限性、边界情况、重做思路
强约束：
- 如果候选人的回答已经包含项目职责、技术方案或优化过程，请不要再追问“你具体做了什么”或“你如何应用”
- 应优先追问“为什么这样选”“如果重做会如何改进”“这种方案什么时候不适用”
""".strip(),

        "technical_usage": """
请生成“技术用途补充型追问”。
适用场景：
- 候选人只说了这个技术点“用来做什么”
- 但没有说项目中怎么落地、解决了什么具体问题
强约束：
- 不要问“原理是什么”
- 不要问“适用场景是什么”
""".strip(),

        "technical_principle": """
请生成“技术原理型追问”。
适用场景：
- 候选人已经提到了项目中如何用
- 但还没有讲清底层机制或为什么有效
强约束：
- 不要再问“项目里怎么用”
- 不要只问“适用场景”
""".strip(),

        "technical_verification": """
请生成“技术验证型追问”。
适用场景：
- 候选人已经提到了用途、实现方式，甚至还提到了过期时间、一致性、穿透、击穿、雪崩等内容
强约束：
- 如果候选人的回答已经提到了 Redis 的用途、缓存目标、过期时间或缓存问题，请不要再追问“原理或适用场景”
- 不要再问“它怎么应用”
- 不要再问“项目里怎么使用”
- 优先问局限、边界、风险、取舍、替代方案、改进点
""".strip(),

        "scenario_brief": """
请生成“场景补步骤型追问”。
目标：
- 补充排查顺序
- 补充分析步骤
- 补充落地方案
""".strip(),

        "scenario_analysis": """
请生成“场景分析型追问”。
目标：
- 深挖排查思路
- 深挖验证方法
- 深挖解决路径
""".strip(),

        "scenario_tradeoff": """
请生成“场景取舍型追问”。
目标：
- 追问方案之间的取舍
- 追问约束条件变化后的处理
- 追问线上环境限制下的决策
强约束：
- 不要再问“先做什么”
- 优先问“如果不能重启怎么办”“如果代价过高怎么办”“如何权衡方案”
""".strip(),

        "verification": """
请生成“反问验证型追问”。
目标：
- 检查候选人是否真正理解刚才的回答
- 优先问改进点、局限、风险、边界情况
""".strip()
    }

    mode_instruction = mode_instruction_map.get(
        followup_mode,
        mode_instruction_map["verification"]
    )

    return f"""
你是一名技术面试官，请基于候选人的目标岗位、题目类型、当前题目、候选人的回答，以及题库提供的追问参考信息，生成一个更深入、更具体的追问问题。

本次追问类型：{followup_mode}

附加要求：
{mode_instruction}

题库参考信息：
- 题目关键点：{payload.get("keyPoints", "")}
- 评分重点：{payload.get("scoringFocus", "")}
- 基础参考回答：{payload.get("referenceAnswerBasic", "")}
- 优秀参考回答：{payload.get("referenceAnswerGood", "")}
- 追问重点：{payload.get("followupFocus", "")}
- 追问示例：{payload.get("followupExamples", "")}

通用要求：
1. 只输出一句追问问题
2. 追问必须和当前回答强相关
3. 优先参考“追问重点”和“追问示例”，但不要照抄
4. 追问要体现技术面试风格
5. 不要输出解释，不要输出编号，不要输出 JSON
6. 不要总是重复“你能详细介绍如何在项目中应用吗”这类表达
7. 问法要自然，像真实面试官
8. 问题要尽量有区分度，不要和低质量回答时的追问过于相似

目标岗位：{payload["roleName"]}
题型：{payload["type"]}
当前题目：{payload["question"]}
候选人回答：{payload["answer"]}
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

    # 技术题更强的深度信号
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
        # 技术题要更强调“深度信号”
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
        # 技术题三段明确分流
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
    followup_mode = payload["followUpMode"]

    mode_instruction_map = {
        "project_brief": """
请生成“项目补细节型追问”。
目标：
- 补充候选人刚才没有说清楚的职责、模块、实现内容
- 优先问具体负责什么、怎么实现、做了什么优化
禁止：
- 不要问抽象空泛问题
- 不要问“能否详细介绍如何在项目中应用”这类宽泛句式
""".strip(),

        "project_detail": """
请生成“项目深挖型追问”。
目标：
- 深挖技术难点
- 深挖方案选择原因
- 深挖优化效果
禁止：
- 不要退回到只问“你具体负责什么”
""".strip(),

        "project_verification": """
请生成“项目验证型追问”。
目标：
- 验证候选人是否真的理解方案
- 追问改进点、局限性、边界情况、重做思路
强约束：
- 如果候选人的回答已经包含项目职责、技术方案或优化过程，请不要再追问“你具体做了什么”或“你如何应用”
- 应优先追问“为什么这样选”“如果重做会如何改进”“这种方案什么时候不适用”
""".strip(),

        "technical_usage": """
请生成“技术用途补充型追问”。
适用场景：
- 候选人只说了这个技术点“用来做什么”
- 但没有说项目中怎么落地、解决了什么具体问题

目标：
- 追问项目中的具体使用方式
- 追问为什么需要用它
- 追问它解决了什么实际问题

强约束：
- 不要问“原理是什么”
- 不要问“适用场景是什么”
- 不要生成宽泛问题
优先问法：
- 你们项目里哪些数据会放到 Redis？
- 为什么这些数据适合放缓存？
- 你是如何设置缓存过期时间的？
""".strip(),

        "technical_principle": """
请生成“技术原理型追问”。
适用场景：
- 候选人已经提到了项目中如何用
- 但还没有讲清底层机制或为什么有效

目标：
- 追问底层原理
- 追问为什么这样设计
- 追问为什么能解决问题

强约束：
- 不要再问“项目里怎么用”
- 不要只问“适用场景”
优先问法：
- Redis 相比直接查 MySQL，为什么性能更高？
- 缓存为什么会带来一致性问题？
- 这个方案为什么能减少数据库压力？
""".strip(),

        "technical_verification": """
请生成“技术验证型追问”。
适用场景：
- 候选人已经提到了用途、实现方式，甚至还提到了过期时间、一致性、穿透、击穿、雪崩等内容

目标：
- 验证候选人是否真正理解该技术点
- 优先追问局限、边界、风险、取舍、替代方案、改进点

强约束：
- 如果候选人的回答已经提到了 Redis 的用途、缓存目标、过期时间或缓存问题，请不要再追问“原理或适用场景”
- 不要再问“它怎么应用”
- 不要再问“项目里怎么使用”
优先问法：
- 你们是如何处理缓存与数据库一致性的？
- 如果缓存大面积同时失效，会有什么风险？
- 在什么情况下 Redis 反而可能带来问题？
- 如果让你重新设计这套缓存方案，你会改进什么？
""".strip(),

        "scenario_brief": """
请生成“场景补步骤型追问”。
目标：
- 补充排查顺序
- 补充分析步骤
- 补充落地方案
""".strip(),

        "scenario_analysis": """
请生成“场景分析型追问”。
目标：
- 深挖排查思路
- 深挖验证方法
- 深挖解决路径
""".strip(),

        "scenario_tradeoff": """
请生成“场景取舍型追问”。
目标：
- 追问方案之间的取舍
- 追问约束条件变化后的处理
- 追问线上环境限制下的决策
强约束：
- 不要再问“先做什么”
- 优先问“如果不能重启怎么办”“如果代价过高怎么办”“如何权衡方案”
""".strip(),

        "verification": """
请生成“反问验证型追问”。
目标：
- 检查候选人是否真正理解刚才的回答
- 优先问改进点、局限、风险、边界情况
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
6. 问法要自然，像真实面试官
7. 问题要尽量有区分度，不要和低质量回答时的追问过于相似

目标岗位：{payload["roleName"]}
题型：{payload["type"]}
当前题目：{payload["question"]}
候选人回答：{payload["answer"]}
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
                "content": "你是一名技术面试官，请输出一句简洁、具体、贴合回答内容的追问问题。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.7
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