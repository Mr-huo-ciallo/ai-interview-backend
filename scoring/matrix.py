import re
from statistics import mean

from scoring.config import ROLE_SCORE_WEIGHTS


SPLIT_PATTERN = re.compile(r"[、,，;；|/\n\r]+")
WORD_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.\-']*")
CHINESE_PATTERN = re.compile(r"[\u4e00-\u9fff]+")

TECH_DEPTH_TERMS = [
    "原理", "机制", "底层", "源码", "复杂度", "事务", "索引", "缓存", "并发",
    "一致性", "锁", "线程", "进程", "内存", "性能", "优化", "瓶颈", "边界",
    "限制", "风险", "取舍", "trade-off", "tradeoff", "principle", "mechanism",
    "complexity", "performance", "consistency", "transaction", "index", "cache",
]

LOGIC_TERMS = [
    "首先", "其次", "然后", "最后", "因为", "所以", "因此", "如果", "否则",
    "步骤", "排查", "定位", "分析", "验证", "方案", "假设", "对比", "取舍",
    "first", "second", "then", "finally", "because", "therefore", "if", "else",
    "analyze", "verify", "validate", "trade-off", "assumption",
]

EXAMPLE_TERMS = [
    "例如", "比如", "在项目中", "实际开发", "举例", "场景", "案例",
    "for example", "such as", "in practice", "in a project",
]


def _normalize_text(value: str | None) -> str:
    return (value or "").strip().lower()


def _split_terms(value: str | None) -> list[str]:
    terms = []
    for item in SPLIT_PATTERN.split(value or ""):
        item = item.strip()
        if item and item not in terms:
            terms.append(item)
    return terms


def _tokenize(value: str | None) -> set[str]:
    text = _normalize_text(value)
    tokens = {
        token.strip("'.-")
        for token in WORD_PATTERN.findall(text)
        if len(token.strip("'.-")) >= 3
    }
    for chinese_text in CHINESE_PATTERN.findall(text):
        if len(chinese_text) == 1:
            tokens.add(chinese_text)
        else:
            tokens.update(chinese_text[index:index + 2] for index in range(len(chinese_text) - 1))
    return tokens


def _hit_terms(answer_text: str, terms: list[str]) -> list[str]:
    normalized_answer = _normalize_text(answer_text)
    hits = []
    for term in terms:
        normalized_term = _normalize_text(term)
        if not normalized_term:
            continue
        if normalized_term in normalized_answer:
            hits.append(term)
            continue
        term_tokens = _tokenize(normalized_term)
        answer_tokens = _tokenize(normalized_answer)
        if term_tokens and len(term_tokens & answer_tokens) / len(term_tokens) >= 0.6:
            hits.append(term)
    return hits


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(max(0.0, min(1.0, part / total)), 3)


def _term_coverage(answer_text: str, terms: list[str]) -> tuple[float, list[str], list[str]]:
    if not terms:
        return 0.0, [], []
    hits = _hit_terms(answer_text, terms)
    misses = [term for term in terms if term not in hits]
    return _ratio(len(hits), len(terms)), hits, misses


def _jaccard_similarity(left: str, right: str) -> float:
    left_tokens = _tokenize(left)
    right_tokens = _tokenize(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return round(len(left_tokens & right_tokens) / len(left_tokens | right_tokens), 3)


def _keyword_density(answer_text: str, terms: list[str], max_hits: int = 6) -> float:
    if not answer_text.strip():
        return 0.0
    hits = len(_hit_terms(answer_text, terms))
    return _ratio(hits, max_hits)


def _length_quality(answer_text: str) -> float:
    length = len(answer_text.strip())
    if length <= 0:
        return 0.0
    if length < 30:
        return 0.25
    if length < 80:
        return 0.55
    if length < 180:
        return 0.82
    return 1.0


def _difficulty_factor(difficulty: str | None) -> float:
    return {
        "easy": 0.96,
        "medium": 1.0,
        "hard": 1.06,
    }.get((difficulty or "medium").lower(), 1.0)


def _score(value: float, difficulty: str | None = None) -> int:
    adjusted = value * _difficulty_factor(difficulty)
    if adjusted <= 0.02:
        return 0
    if adjusted < 0.15:
        return int(round(max(20, adjusted * 100)))
    return int(round(max(35, min(98, adjusted * 100))))


def _merge_answer(item: dict) -> tuple[str, str, str]:
    main_answer = item.get("answer", "") or ""
    followup_answer = item.get("followUpAnswer", "") or ""
    merged = " ".join(part for part in [main_answer, followup_answer] if part.strip())
    return main_answer, followup_answer, merged


def extract_features(role: str, item: dict) -> dict:
    main_answer, followup_answer, answer_text = _merge_answer(item)
    key_points = _split_terms(item.get("keyPoints"))
    scoring_focus_terms = _split_terms(item.get("scoringFocus"))
    tags = _split_terms(item.get("tags"))
    reference_answer = item.get("referenceAnswerGood") or item.get("referenceAnswerBasic") or ""

    key_coverage, covered_key_points, missing_key_points = _term_coverage(answer_text, key_points)
    focus_coverage, covered_focus, missing_focus = _term_coverage(answer_text, scoring_focus_terms)
    concept_richness = _ratio(len(set(covered_key_points + covered_focus)), 5)

    main_key_hits = set(_hit_terms(main_answer, key_points))
    merged_key_hits = set(covered_key_points)
    newly_covered = [term for term in key_points if term in merged_key_hits and term not in main_key_hits]
    followup_gain = _ratio(len(newly_covered), max(1, len(key_points) - len(main_key_hits)))
    if followup_answer and not key_points:
        followup_gain = min(1.0, _length_quality(followup_answer) * 0.6)

    reference_similarity = _jaccard_similarity(answer_text, reference_answer)
    technical_depth = _keyword_density(answer_text, TECH_DEPTH_TERMS)
    logic_structure = max(
        _keyword_density(answer_text, LOGIC_TERMS),
        min(0.65, concept_richness * 0.75),
    )
    role_match = _term_coverage(answer_text, tags)[0] if tags else round(
        key_coverage * 0.6 + focus_coverage * 0.4,
        3,
    )
    expression_completeness = round(
        _length_quality(answer_text) * 0.45
        + _keyword_density(answer_text, EXAMPLE_TERMS, max_hits=3) * 0.15
        + logic_structure * 0.2
        + concept_richness * 0.2,
        3,
    )

    confidence = round(
        key_coverage * 0.35
        + focus_coverage * 0.2
        + expression_completeness * 0.2
        + min(1.0, len(answer_text) / 120) * 0.25,
        3,
    )

    return {
        "keyPointCoverage": key_coverage,
        "scoringFocusCoverage": focus_coverage,
        "referenceSimilarity": reference_similarity,
        "conceptRichness": concept_richness,
        "technicalDepth": technical_depth,
        "logicStructure": logic_structure,
        "expressionCompleteness": expression_completeness,
        "followupGain": followup_gain,
        "roleMatch": role_match,
        "confidence": confidence,
        "coveredKeyPoints": covered_key_points,
        "missingKeyPoints": missing_key_points,
        "coveredScoringFocus": covered_focus,
        "missingScoringFocus": missing_focus,
        "newlyCoveredByFollowup": newly_covered,
    }


def calculate_question_scores(q_type: str, difficulty: str, features: dict) -> dict:
    key = features["keyPointCoverage"]
    focus = features["scoringFocusCoverage"]
    ref = features["referenceSimilarity"]
    depth = features["technicalDepth"]
    logic = features["logicStructure"]
    expression = features["expressionCompleteness"]
    followup = features["followupGain"]
    role_match = features["roleMatch"]

    if q_type == "scenario":
        tech_value = key * 0.3 + focus * 0.25 + depth * 0.25 + ref * 0.2
        logic_value = logic * 0.35 + focus * 0.25 + depth * 0.2 + followup * 0.2
    elif q_type == "project":
        tech_value = key * 0.25 + focus * 0.25 + depth * 0.2 + ref * 0.1 + followup * 0.2
        logic_value = logic * 0.25 + expression * 0.25 + focus * 0.25 + followup * 0.25
    else:
        tech_value = key * 0.35 + focus * 0.25 + ref * 0.2 + depth * 0.2
        logic_value = logic * 0.35 + focus * 0.2 + depth * 0.2 + key * 0.25

    expression_value = expression * 0.7 + logic * 0.2 + followup * 0.1
    match_value = role_match * 0.4 + key * 0.3 + focus * 0.3

    return {
        "tech": _score(tech_value, difficulty),
        "expression": _score(expression_value, difficulty),
        "logic": _score(logic_value, difficulty),
        "match": _score(match_value, difficulty),
    }


def _average_dimension(question_rows: list[dict], dimension: str) -> int:
    values = [row["dimensionScores"][dimension] for row in question_rows]
    return int(round(mean(values))) if values else 0


def aggregate_scores(role: str, question_rows: list[dict]) -> dict:
    tech_score = _average_dimension(question_rows, "tech")
    expression_score = _average_dimension(question_rows, "expression")
    logic_score = _average_dimension(question_rows, "logic")
    match_score = _average_dimension(question_rows, "match")

    weights = ROLE_SCORE_WEIGHTS.get(role, ROLE_SCORE_WEIGHTS["java"])
    total_score = int(round(
        tech_score * weights["tech"]
        + expression_score * weights["expression"]
        + logic_score * weights["logic"]
        + match_score * weights["match"]
    ))

    confidence_values = [row["features"]["confidence"] for row in question_rows]
    confidence = round(mean(confidence_values), 3) if confidence_values else 0.0

    return {
        "techScore": tech_score,
        "expressionScore": expression_score,
        "logicScore": logic_score,
        "matchScore": match_score,
        "totalScore": total_score,
        "confidence": confidence,
    }


def build_feature_matrix(role: str, answers: list[dict]) -> dict:
    question_rows = []
    for index, item in enumerate(answers, start=1):
        features = extract_features(role, item)
        dimension_scores = calculate_question_scores(
            item.get("type", "technical"),
            item.get("difficulty", "medium"),
            features,
        )
        question_rows.append({
            "index": index,
            "question": item.get("question", ""),
            "type": item.get("type", ""),
            "difficulty": item.get("difficulty", "medium"),
            "features": features,
            "dimensionScores": dimension_scores,
        })

    return {
        "questionRows": question_rows,
        "scores": aggregate_scores(role, question_rows),
    }


def blend_scores(matrix_scores: dict, legacy_scores: dict, matrix_weight: float = 0.7) -> dict:
    legacy_weight = 1 - matrix_weight
    result = {}
    for key in ["techScore", "expressionScore", "logicScore", "matchScore", "totalScore"]:
        result[key] = int(round(matrix_scores[key] * matrix_weight + legacy_scores[key] * legacy_weight))
    result["confidence"] = matrix_scores.get("confidence", 0.0)
    result["scoreSource"] = "feature_matrix_blended"
    result["matrixWeight"] = matrix_weight
    return result
