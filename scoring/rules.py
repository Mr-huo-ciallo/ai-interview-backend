from scoring.config import (
    ROLE_KEYWORDS,
    ROLE_TECH_FEEDBACK,
    STRUCTURE_WORDS,
    LOGIC_WORDS,
    ROLE_SCORE_WEIGHTS
)


def count_keyword_hits(text: str, keywords: list[str]) -> int:
    text_lower = text.lower()
    hits = 0
    for kw in keywords:
        if kw.lower() in text_lower:
            hits += 1
    return hits


def calculate_tech_score(role: str, answers: list[str]) -> int:
    full_text = " ".join(answers)
    keywords = ROLE_KEYWORDS.get(role, ROLE_KEYWORDS["java"])["tech"]

    hits = count_keyword_hits(full_text, keywords)
    coverage = hits / len(keywords) if keywords else 0

    score = 50

    if coverage >= 0.2:
        score += 10
    if coverage >= 0.4:
        score += 10
    if coverage >= 0.6:
        score += 10

    if len(full_text) > 100:
        score += 5
    if len(full_text) > 200:
        score += 5

    return min(score, 95)


def calculate_expression_score(answers: list[str]) -> int:
    full_text = " ".join(answers)
    length = len(full_text)

    score = 55

    if length > 50:
        score += 10
    if length > 120:
        score += 10
    if length > 200:
        score += 10

    example_words = ["例如", "比如", "在项目中", "实际开发中"]
    example_hits = count_keyword_hits(full_text, example_words)
    score += min(example_hits * 5, 10)

    structure_hits = count_keyword_hits(full_text, STRUCTURE_WORDS)
    score += min(structure_hits * 2, 10)

    return min(score, 95)


def calculate_logic_score(answers: list[str]) -> int:
    full_text = " ".join(answers)
    hits = count_keyword_hits(full_text, LOGIC_WORDS)

    score = 50 + hits * 6

    if "首先" in full_text and "其次" in full_text:
        score += 8
    if "因为" in full_text and "所以" in full_text:
        score += 8

    return min(score, 95)


def calculate_match_score(role: str, answers: list[str]) -> int:
    full_text = " ".join(answers)
    keywords = ROLE_KEYWORDS.get(role, ROLE_KEYWORDS["java"])["match"]

    hits = count_keyword_hits(full_text, keywords)
    score = 55 + hits * 6

    return min(score, 95)


def calculate_project_bonus(answer: str) -> int:
    bonus_words = ["项目", "负责", "实现", "优化", "在项目中", "我负责", "最终"]
    hits = count_keyword_hits(answer, bonus_words)

    score = 0
    if len(answer) > 80:
        score += 5
    if len(answer) > 150:
        score += 5

    score += min(hits * 2, 10)
    return min(score, 15)


def calculate_technical_bonus(answer: str, role: str) -> int:
    keywords = ROLE_KEYWORDS.get(role, ROLE_KEYWORDS["java"])["tech"]
    hits = count_keyword_hits(answer, keywords)
    score = min(hits * 2, 15)
    return score


def calculate_scenario_bonus(answer: str) -> int:
    scenario_words = ["首先", "其次", "然后", "最后", "分析", "优化", "排查", "方案"]
    hits = count_keyword_hits(answer, scenario_words)

    score = 0
    if "首先" in answer and "其次" in answer:
        score += 5
    if "分析" in answer or "排查" in answer:
        score += 5

    score += min(hits, 5)
    return min(score, 15)


def calculate_type_bonus(role: str, answers: list[dict]) -> dict:
    tech_bonus = 0
    expression_bonus = 0
    logic_bonus = 0
    match_bonus = 0

    for item in answers:
        q_type = item.get("type", "")
        answer = item.get("answer", "")

        if q_type == "project":
            bonus = calculate_project_bonus(answer)
            expression_bonus += bonus
            match_bonus += bonus // 2

        elif q_type == "technical":
            bonus = calculate_technical_bonus(answer, role)
            tech_bonus += bonus

        elif q_type == "scenario":
            bonus = calculate_scenario_bonus(answer)
            logic_bonus += bonus
            expression_bonus += bonus // 2

    return {
        "tech_bonus": min(tech_bonus, 15),
        "expression_bonus": min(expression_bonus, 15),
        "logic_bonus": min(logic_bonus, 15),
        "match_bonus": min(match_bonus, 10)
    }


def calculate_total_score(
    role: str,
    tech_score: int,
    expression_score: int,
    logic_score: int,
    match_score: int
) -> int:
    weights = ROLE_SCORE_WEIGHTS.get(role, ROLE_SCORE_WEIGHTS["java"])

    return int(
        tech_score * weights["tech"] +
        expression_score * weights["expression"] +
        logic_score * weights["logic"] +
        match_score * weights["match"]
    )


def generate_strengths(
    role: str,
    tech_score: int,
    expression_score: int,
    logic_score: int,
    match_score: int
) -> list[str]:
    result = []

    if tech_score >= 75:
        result.append("对目标岗位的核心技术点覆盖较好。")
    if expression_score >= 75:
        result.append("整体表达较清晰，回答比较完整。")
    if logic_score >= 75:
        result.append("回答具有一定层次性和逻辑性。")
    if match_score >= 75:
        result.append("回答内容与目标岗位要求匹配度较高。")

    role_feedback = ROLE_TECH_FEEDBACK.get(role)
    if role_feedback and tech_score >= 80:
        result.append(role_feedback["strength"])

    if not result:
        result.append("能够完成基础作答，具备进一步提升空间。")

    return result


def generate_weaknesses(
    role: str,
    tech_score: int,
    expression_score: int,
    logic_score: int,
    match_score: int
) -> list[str]:
    result = []

    if tech_score < 75:
        result.append("岗位核心知识点覆盖不足，技术回答深度仍需提升。")
    if expression_score < 75:
        result.append("回答长度或表达完整性不足，建议进一步展开。")
    if logic_score < 75:
        result.append("回答层次感不够明显，逻辑衔接可以进一步加强。")
    if match_score < 75:
        result.append("回答与目标岗位的针对性还不够强。")

    role_feedback = ROLE_TECH_FEEDBACK.get(role)
    if role_feedback and tech_score < 75:
        result.append(role_feedback["weakness"])

    if not result:
        result.append("整体表现较均衡，但仍可进一步打磨细节。")

    return result


def generate_suggestions(role: str) -> list[str]:
    return ROLE_KEYWORDS.get(role, ROLE_KEYWORDS["java"])["suggestions"]
