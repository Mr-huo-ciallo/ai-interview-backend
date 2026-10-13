"""Validate and insert the initial product-manager question set without overwriting edits."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from db import SessionLocal
from models import InterviewQuestionModel


DATA_PATH = Path(__file__).with_name("product_manager_questions.json")
DIMENSIONS = {
    "用户研究", "需求优先级", "产品设计", "数据指标", "交付协作", "项目复盘"
}
REQUIRED_FIELDS = (
    "dimension", "source", "type", "difficulty", "content", "tags", "keyPoints",
    "scoringFocus", "referenceAnswerBasic", "referenceAnswerGood", "followupFocus",
    "followupExamples",
)


def load_questions() -> list[dict]:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    if data.get("role") != "product_manager":
        raise ValueError("Question set has an unexpected role")

    sources = data.get("sources", {})
    questions = data.get("questions", [])
    if len(questions) != 30:
        raise ValueError("The first question set must contain 30 questions")

    seen = set()
    for index, question in enumerate(questions, start=1):
        for field in REQUIRED_FIELDS:
            if not isinstance(question.get(field), str) or not question[field].strip():
                raise ValueError(f"Question {index} has an empty {field}")
        if question["dimension"] not in DIMENSIONS:
            raise ValueError(f"Question {index} has an unknown dimension")
        if question["type"] not in {"project", "technical", "scenario"}:
            raise ValueError(f"Question {index} has an unknown type")
        if question["difficulty"] not in {"easy", "medium", "hard"}:
            raise ValueError(f"Question {index} has an unknown difficulty")
        if not str(sources.get(question["source"], "")).startswith("https://"):
            raise ValueError(f"Question {index} has no traceable source")
        content_key = question["content"].strip().casefold()
        if content_key in seen:
            raise ValueError(f"Question {index} duplicates another question")
        seen.add(content_key)

    if Counter(q["dimension"] for q in questions) != Counter({name: 5 for name in DIMENSIONS}):
        raise ValueError("Question set must cover all six dimensions equally")
    if Counter(q["difficulty"] for q in questions) != {"easy": 6, "medium": 15, "hard": 9}:
        raise ValueError("Question set has an unexpected difficulty distribution")
    return questions


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Insert missing questions into the configured database")
    args = parser.parse_args()
    questions = load_questions()

    with SessionLocal.begin() as db:
        existing_contents = {
            content.strip().casefold()
            for (content,) in db.query(InterviewQuestionModel.content)
            .filter(InterviewQuestionModel.role == "product_manager")
            .all()
        }
        missing = [
            (index, question)
            for index, question in enumerate(questions, start=1)
            if question["content"].strip().casefold() not in existing_contents
        ]
        if args.apply:
            for index, question in missing:
                db.add(InterviewQuestionModel(
                    role="product_manager",
                    type=question["type"],
                    content=question["content"],
                    sort_order=index,
                    difficulty=question["difficulty"],
                    tags=question["tags"],
                    key_points=question["keyPoints"],
                    scoring_focus=question["scoringFocus"],
                    reference_answer_basic=question["referenceAnswerBasic"],
                    reference_answer_good=question["referenceAnswerGood"],
                    followup_focus=question["followupFocus"],
                    followup_examples=question["followupExamples"],
                ))

    action = "Inserted" if args.apply else "Would insert"
    print(f"{action} {len(missing)} product-manager questions; {len(questions) - len(missing)} already present")


if __name__ == "__main__":
    main()
