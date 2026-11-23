"""Key point judgement: build the LLM request and validate its output.

The LLM only labels each key point / scoring focus term as covered, partial or
missing and quotes evidence from the answer. Scores are still computed by the
formulas in scoring.matrix.
"""
import logging
import re
import unicodedata

from scoring.matrix import split_terms


logger = logging.getLogger(__name__)

STATUSES = ("covered", "partial", "missing")
EVIDENCE_MAX_LENGTH = 200
POINT_FIELDS = (("keyPoint", "keyPoints", "k"), ("scoringFocus", "scoringFocus", "f"))
NON_WORD_RE = re.compile(r"[^0-9a-z\u4e00-\u9fff]+")


def _compact(text: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", text or "").lower()
    return NON_WORD_RE.sub("", normalized)


def build_judgement_request(answers: list[dict]) -> list[dict]:
    """Return the questions to judge, each point carrying a stable id like q1-k2."""
    questions = []
    for q_index, item in enumerate(answers, start=1):
        main_answer = (item.get("answer") or "").strip()
        followup_answer = (item.get("followUpAnswer") or "").strip()
        if not main_answer and not followup_answer:
            continue
        points = []
        for kind, field, prefix in POINT_FIELDS:
            for p_index, term in enumerate(split_terms(item.get(field)), start=1):
                points.append({"id": f"q{q_index}-{prefix}{p_index}", "kind": kind, "point": term})
        if not points:
            continue
        questions.append({
            "index": q_index,
            "question": item.get("question", ""),
            "answer": main_answer,
            "followUpQuestion": item.get("followUpQuestion", ""),
            "followUpAnswer": followup_answer,
            "points": points,
        })
    return questions


def parse_judgement(request: list[dict], raw: dict) -> dict[int, dict[tuple[str, str], dict]]:
    """Validate LLM output against the request.

    Returns {question_index: {(kind, point): {"status", "evidence", "foundIn"}}}.
    A covered/partial claim whose evidence is not a verbatim excerpt of the
    answer is downgraded to missing. Duplicate valid ids keep the first entry.
    Points the model omitted are left out so the matrix falls back to lexical
    matching for them.
    """
    points_by_id = {}
    for question in request:
        for point in question["points"]:
            points_by_id[point["id"]] = (question, point)

    items = raw.get("judgements") if isinstance(raw, dict) else None
    result: dict[int, dict[tuple[str, str], dict]] = {}
    for entry in items if isinstance(items, list) else []:
        if not isinstance(entry, dict) or entry.get("id") not in points_by_id:
            continue
        question, point = points_by_id[entry["id"]]
        status = entry.get("status")
        if status not in STATUSES:
            continue
        question_bucket = result.setdefault(question["index"], {})
        point_key = (point["kind"], point["point"])
        if point_key in question_bucket:
            logger.warning("忽略重复的关键点判断 id=%s", entry.get("id"))
            continue
        evidence = str(entry.get("evidence") or "").strip()
        found_in = ""
        if status != "missing":
            compact_evidence = _compact(evidence)
            if compact_evidence and compact_evidence in _compact(question["answer"]):
                found_in = "main"
            elif compact_evidence and compact_evidence in _compact(question["followUpAnswer"]):
                found_in = "followup"
            else:
                status = "missing"
        if status == "missing":
            evidence = ""
        question_bucket[point_key] = {
            "status": status,
            "evidence": evidence[:EVIDENCE_MAX_LENGTH],
            "foundIn": found_in,
        }
    return result
