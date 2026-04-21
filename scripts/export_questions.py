import json
from pathlib import Path

from db import SessionLocal
from crud import get_all_questions


def main():
    output = Path(__file__).resolve().parents[1] / "data" / "interview_questions_export.json"
    output.parent.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        questions = get_all_questions(db)
    finally:
        db.close()

    output.write_text(
        json.dumps(questions, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Exported {len(questions)} questions to {output}")


if __name__ == "__main__":
    main()
