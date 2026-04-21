import json
from pathlib import Path

from crud import add_question, get_question_by_role_and_content, update_question
from db import SessionLocal


def main():
    source = Path(__file__).resolve().parents[1] / "data" / "interview_questions_export.json"
    if not source.exists():
        raise FileNotFoundError(f"Question export file not found: {source}")

    questions = json.loads(source.read_text(encoding="utf-8"))

    created = 0
    updated = 0
    db = SessionLocal()
    try:
        for question in questions:
            existing = get_question_by_role_and_content(
                db,
                question["role"],
                question["content"],
            )
            if existing:
                update_question(db, existing["id"], question)
                updated += 1
            else:
                add_question(db, question)
                created += 1
    finally:
        db.close()

    print(f"Imported questions from {source}. Created: {created}, updated: {updated}")


if __name__ == "__main__":
    main()
