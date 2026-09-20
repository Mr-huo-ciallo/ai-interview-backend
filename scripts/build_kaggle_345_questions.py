import ast
import csv
import json
import re
from collections import Counter
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_DIR = BASE_DIR.parent
DATABASE_DIR = WORKSPACE_DIR / "database"
OUTPUT_DIR = BASE_DIR / "data"

SOURCE_QA = DATABASE_DIR / "archive (3)" / "data.csv"
SOURCE_PYTHON = DATABASE_DIR / "archive (4)" / "Dataset_Python_Question_Answer.csv"
SOURCE_CS = DATABASE_DIR / "archive (5)" / "intents.json"

SQL_OUTPUT = OUTPUT_DIR / "import_kaggle_345_interview_questions.sql"
JSON_OUTPUT = OUTPUT_DIR / "kaggle_345_interview_questions_preview.json"
SUMMARY_OUTPUT = OUTPUT_DIR / "kaggle_345_interview_questions_summary.json"


STOPWORDS = {
    "the", "and", "are", "for", "has", "have", "had", "can", "will", "not", "all", "its",
    "they", "them", "than", "then", "also", "only", "more", "most", "some", "such",
    "what", "which", "when", "where", "why", "how", "does", "with", "from", "that", "this",
    "into", "your", "about", "would", "could", "should", "there", "their", "these", "those",
    "sure", "here", "let", "know", "hope", "helps", "means", "called", "specific",
    "different", "various", "following", "single", "multiple", "available", "used",
    "explain", "define", "difference", "between", "example", "examples", "used", "using",
    "function", "functions", "method", "methods", "class", "object", "program", "programming",
    "python", "software", "quality", "assurance", "testing",
}

ROLE_CONFIG = {
    "qa": {
        "default_tags": ["QA", "Testing", "Software Quality"],
        "focus": "能解释测试或质量保障概念；能覆盖核心术语；能结合测试流程、缺陷定位、用例设计或质量风险说明；较难题需体现工具、策略和工程权衡",
        "followup": "围绕测试场景继续追问测试策略、缺陷定位、自动化方案和质量风险",
    },
    "python": {
        "default_tags": ["Python", "Programming", "Backend"],
        "focus": "能准确解释 Python 概念；能覆盖题目关键点；能说明适用场景、边界条件、常见误区或与相近概念的区别；较难题需体现原理深度和实践权衡",
        "followup": "围绕 Python 实际开发继续追问原理、边界条件、性能影响和项目用法",
    },
    "cs_basic": {
        "default_tags": ["Computer Science", "Software Engineering", "Programming Fundamentals"],
        "focus": "能准确解释计算机基础或软件工程概念；能覆盖核心定义、适用场景和常见误区；较难题需结合实现原理、复杂度、工程限制或实践案例",
        "followup": "围绕计算机基础继续追问原理、适用场景、限制条件和工程实践",
    },
}


def clean_text(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\uf020", " ").replace("\uf0b7", " ").replace("\uf076", " ")
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_answer_list(value: str) -> str:
    value = clean_text(value)
    try:
        parsed = ast.literal_eval(value)
    except Exception:
        return value
    if isinstance(parsed, list):
        return clean_text(" ".join(str(item) for item in parsed))
    return clean_text(parsed)


def split_sentences(value: str, max_sentences: int = 3) -> str:
    parts = re.split(r"(?<=[.!?])\s+", clean_text(value))
    return clean_text(" ".join(part for part in parts[:max_sentences] if part))


def extract_terms(question: str, answer: str, defaults: list[str], limit: int = 8) -> list[str]:
    text = f"{question} {answer}".lower()
    candidates = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.\-]{2,}", text)
    counts = Counter(
        token.strip(".-")
        for token in candidates
        if token.strip(".-") and token.strip(".-") not in STOPWORDS and len(token.strip(".-")) >= 3
    )
    terms = []
    for term in defaults:
        if term not in terms:
            terms.append(term)
    for term, _ in counts.most_common(limit * 2):
        normalized = term.upper() if term in {"qa", "api", "sql", "srs", "frs", "brs"} else term
        if normalized not in terms:
            terms.append(normalized)
        if len(terms) >= limit:
            break
    return terms[:limit]


def classify_type(question: str) -> str:
    q = question.lower()
    scenario_terms = [
        "how would you", "how do you", "what steps", "steps", "process", "approach",
        "bug", "defect", "test case", "automation", "scenario", "project",
    ]
    return "scenario" if any(term in q for term in scenario_terms) else "technical"


def classify_difficulty(question: str, answer: str) -> str:
    q = question.lower()
    answer_len = len(answer)
    hard_terms = [
        "architecture", "optimization", "performance", "concurrency", "memory",
        "framework", "automation", "strategy", "complexity", "security",
    ]
    easy_terms = ["what is", "define", "meaning", "purpose"]
    if answer_len > 900 or any(term in q for term in hard_terms):
        return "hard"
    if answer_len < 280 and any(term in q for term in easy_terms):
        return "easy"
    return "medium"


def build_record(role: str, question: str, answer: str, sort_order: int, source: str) -> dict:
    question = clean_text(question)
    answer = clean_text(answer)
    config = ROLE_CONFIG[role]
    terms = extract_terms(question, answer, config["default_tags"])
    difficulty = classify_difficulty(question, answer)
    return {
        "role": role,
        "type": classify_type(question),
        "content": question,
        "sortOrder": sort_order,
        "difficulty": difficulty,
        "tags": ", ".join(terms[:6]),
        "keyPoints": "、".join(terms),
        "scoringFocus": f"{config['focus']}；重点关注：{'、'.join(terms[:5])}",
        "referenceAnswerBasic": split_sentences(answer, 2),
        "referenceAnswerGood": answer,
        "followupFocus": config["followup"],
        "followupExamples": "请结合一个真实项目或具体场景说明你的处理方式、判断依据和可能风险。",
        "source": source,
    }


def load_qa_questions(start_order: int) -> list[dict]:
    records = []
    with SOURCE_QA.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, delimiter=";")
        for row in reader:
            question = row.get("question", "")
            answer = row.get("answer", "")
            if clean_text(question) and clean_text(answer):
                records.append(build_record("qa", question, answer, start_order + len(records), "kaggle_archive_3_qa"))
    return records


def load_python_questions(start_order: int) -> list[dict]:
    records = []
    with SOURCE_PYTHON.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            question = row.get("Question", "")
            answer = parse_answer_list(row.get("Answer", ""))
            if clean_text(question) and clean_text(answer):
                records.append(build_record("python", question, answer, start_order + len(records), "kaggle_archive_4_python"))
    return records


def load_cs_questions(start_order: int) -> list[dict]:
    records = []
    data = json.loads(SOURCE_CS.read_text(encoding="utf-8-sig"))
    for item in data.get("intents", []):
        answer = clean_text(" ".join(item.get("responses") or []))
        for pattern in item.get("patterns") or []:
            if clean_text(pattern) and answer:
                record = build_record("cs_basic", pattern, answer, start_order + len(records), "kaggle_archive_5_intents")
                tag = clean_text(item.get("tag", ""))
                if tag:
                    tags = [tag, *[part.strip() for part in record["tags"].split(",") if part.strip()]]
                    record["tags"] = ", ".join(dict.fromkeys(tags))
                    key_points = [tag, *[part.strip() for part in record["keyPoints"].split("、") if part.strip()]]
                    record["keyPoints"] = "、".join(dict.fromkeys(key_points))
                records.append(record)
    return records


def dedupe(records: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for record in records:
        key = (record["role"], record["content"].lower())
        if key in seen:
            continue
        seen.add(key)
        result.append(record)
    role_counts = Counter()
    for record in result:
        role_counts[record["role"]] += 1
        record["sortOrder"] = role_counts[record["role"]]
    return result


def sql_escape(value: object) -> str:
    text = "" if value is None else str(value)
    return "'" + text.replace("\\", "\\\\").replace("'", "''") + "'"


def write_sql(records: list[dict]) -> None:
    columns = [
        "role", "type", "content", "sort_order", "difficulty", "tags", "key_points",
        "scoring_focus", "reference_answer_basic", "reference_answer_good",
        "followup_focus", "followup_examples",
    ]
    lines = [
        "-- Generated from Kaggle archives 3/4/5 in D:/++Dev-Cpp/Mr.huo/vue-projects/database",
        f"-- Question rows: {len(records)}",
        "-- Roles: qa, python, cs_basic",
        "-- Re-run behavior: deletes existing rows for these generated roles before insertion.",
        "SET NAMES utf8mb4;",
        "CREATE DATABASE IF NOT EXISTS ai_interview DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
        "USE ai_interview;",
        "",
        "CREATE TABLE IF NOT EXISTS interview_questions (",
        "  id INT NOT NULL AUTO_INCREMENT,",
        "  role VARCHAR(50) NOT NULL,",
        "  type VARCHAR(50) NOT NULL,",
        "  content TEXT NOT NULL,",
        "  sort_order INT NOT NULL DEFAULT 1,",
        "  difficulty VARCHAR(20) NOT NULL DEFAULT 'medium',",
        "  tags TEXT NULL,",
        "  key_points TEXT NULL,",
        "  scoring_focus TEXT NULL,",
        "  reference_answer_basic TEXT NULL,",
        "  reference_answer_good TEXT NULL,",
        "  followup_focus TEXT NULL,",
        "  followup_examples TEXT NULL,",
        "  PRIMARY KEY (id)",
        ") DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;",
        "",
        "DELETE FROM interview_questions WHERE role IN ('qa', 'python', 'cs_basic');",
        "",
        f"INSERT INTO interview_questions ({', '.join(columns)}) VALUES",
    ]
    values = []
    for record in records:
        row = [
            sql_escape(record["role"]),
            sql_escape(record["type"]),
            sql_escape(record["content"]),
            str(int(record["sortOrder"])),
            sql_escape(record["difficulty"]),
            sql_escape(record["tags"]),
            sql_escape(record["keyPoints"]),
            sql_escape(record["scoringFocus"]),
            sql_escape(record["referenceAnswerBasic"]),
            sql_escape(record["referenceAnswerGood"]),
            sql_escape(record["followupFocus"]),
            sql_escape(record["followupExamples"]),
        ]
        values.append("  (" + ", ".join(row) + ")")
    lines.append(",\n".join(values) + ";")
    SQL_OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_json(records: list[dict]) -> None:
    JSON_OUTPUT.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "total": len(records),
        "byRole": Counter(record["role"] for record in records),
        "bySource": Counter(record["source"] for record in records),
        "byDifficulty": Counter(record["difficulty"] for record in records),
        "byType": Counter(record["type"] for record in records),
        "sampleByRole": {
            role: [record for record in records if record["role"] == role][:5]
            for role in ["qa", "python", "cs_basic"]
        },
        "outputs": {
            "sql": str(SQL_OUTPUT),
            "jsonPreview": str(JSON_OUTPUT),
        },
    }
    SUMMARY_OUTPUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    records.extend(load_qa_questions(1))
    records.extend(load_python_questions(1))
    records.extend(load_cs_questions(1))
    records = dedupe(records)
    write_json(records)
    write_sql(records)
    print(json.dumps({
        "total": len(records),
        "byRole": Counter(record["role"] for record in records),
        "sql": str(SQL_OUTPUT),
        "jsonPreview": str(JSON_OUTPUT),
        "summary": str(SUMMARY_OUTPUT),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
