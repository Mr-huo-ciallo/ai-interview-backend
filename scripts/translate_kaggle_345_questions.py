import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

import httpx
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_JSON = BASE_DIR / "data" / "kaggle_345_interview_questions_preview.json"
OUTPUT_JSON = BASE_DIR / "data" / "kaggle_345_interview_questions_zh_preview.json"
OUTPUT_SQL = BASE_DIR / "data" / "import_kaggle_345_interview_questions_zh.sql"
OUTPUT_SUMMARY = BASE_DIR / "data" / "kaggle_345_interview_questions_zh_summary.json"
CACHE_JSON = BASE_DIR / "data" / "kaggle_345_translation_cache.json"

TRANSLATED_FIELDS = [
    "content",
    "tags",
    "keyPoints",
    "scoringFocus",
    "referenceAnswerBasic",
    "referenceAnswerGood",
    "followupFocus",
    "followupExamples",
]


def load_llm_config() -> tuple[str, str, str]:
    load_dotenv(BASE_DIR / ".env")
    import os

    api_key = os.getenv("LLM_API_KEY", "").strip()
    base_url = os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
    model = os.getenv("LLM_MODEL", "").strip()
    if not api_key or not base_url or not model:
        raise RuntimeError("LLM 配置不完整，请检查 .env 中的 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL")
    return api_key, base_url, model


def load_cache() -> dict[str, dict]:
    if not CACHE_JSON.exists():
        return {}
    return json.loads(CACHE_JSON.read_text(encoding="utf-8"))


def save_cache(cache: dict[str, dict]) -> None:
    CACHE_JSON.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def make_cache_key(record: dict) -> str:
    return f"{record['role']}::{record['sortOrder']}::{record['content']}"


def clean_json_content(content: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        content = content.replace("```json", "").replace("```", "").strip()
    match = re.search(r"\[[\s\S]*\]", content)
    return match.group(0) if match else content


def build_prompt(items: list[dict]) -> str:
    compact_items = []
    for item in items:
        compact_items.append({
            "id": item["_translationId"],
            **{field: item.get(field, "") for field in TRANSLATED_FIELDS},
        })

    return f"""
你是技术面试题库本地化助手。请把下面 JSON 数组中的英文技术面试题库字段翻译成自然、准确、适合中文面试系统展示的中文。

要求：
1. 只输出 JSON 数组，不要输出 markdown、解释或代码块。
2. 每个对象必须保留 id，并返回这些字段：{", ".join(TRANSLATED_FIELDS)}。
3. content 翻译为中文题目。
4. tags 和 keyPoints 翻译为中文术语；保留必要英文缩写或技术名词，例如 QA、API、SQL、SRS、Python、Django、FastAPI、OOP、GIL。
5. keyPoints 必须继续使用中文顿号“、”分隔。
6. referenceAnswerBasic 和 referenceAnswerGood 翻译为中文参考答案，删除 “Sure / I hope this helps / Let me know” 这类聊天套话。
7. 代码片段、函数名、类名、协议名、库名保持原样。
8. 不要新增事实，不要缩写原答案的技术含义。

待翻译 JSON：
{json.dumps(compact_items, ensure_ascii=False)}
""".strip()


def translate_batch(client: httpx.Client, api_key: str, base_url: str, model: str, batch: list[dict]) -> list[dict]:
    response = client.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是严格输出 JSON 的中英技术内容翻译助手。",
                },
                {
                    "role": "user",
                    "content": build_prompt(batch),
                },
            ],
            "temperature": 0.1,
        },
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    parsed = json.loads(clean_json_content(content))
    if not isinstance(parsed, list):
        raise ValueError("LLM 返回内容不是 JSON 数组")
    return parsed


def merge_translation(record: dict, translated: dict) -> dict:
    result = {key: value for key, value in record.items() if key != "_translationId"}
    for field in TRANSLATED_FIELDS:
        value = translated.get(field)
        if isinstance(value, str) and value.strip():
            result[field] = value.strip()
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
        "-- Generated Chinese interview_questions import from Kaggle archives 3/4/5",
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
    OUTPUT_SQL.write_text("\n".join(lines) + "\n", encoding="utf-8")


def dedupe_translated_records(records: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for record in records:
        key = (record["role"], record["content"].strip())
        if key in seen:
            continue
        seen.add(key)
        result.append(record)

    role_counts = Counter()
    for record in result:
        role_counts[record["role"]] += 1
        record["sortOrder"] = role_counts[record["role"]]
    return result


def write_outputs(records: list[dict]) -> None:
    records = dedupe_translated_records(records)
    OUTPUT_JSON.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "total": len(records),
        "byRole": dict(Counter(record["role"] for record in records)),
        "bySource": dict(Counter(record.get("source", "") for record in records)),
        "byDifficulty": dict(Counter(record["difficulty"] for record in records)),
        "byType": dict(Counter(record["type"] for record in records)),
        "sampleByRole": {
            role: [record for record in records if record["role"] == role][:3]
            for role in ["qa", "python", "cs_basic"]
        },
        "outputs": {
            "sql": str(OUTPUT_SQL),
            "jsonPreview": str(OUTPUT_JSON),
            "cache": str(CACHE_JSON),
        },
    }
    OUTPUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_sql(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--sleep", type=float, default=0.2)
    args = parser.parse_args()

    api_key, base_url, model = load_llm_config()
    source_records = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    if args.limit:
        source_records = source_records[:args.limit]

    cache = load_cache()
    translated_records = []
    pending = []

    for index, record in enumerate(source_records, start=1):
        item = dict(record)
        item["_translationId"] = index
        key = make_cache_key(item)
        if key in cache:
            translated_records.append(cache[key])
        else:
            pending.append(item)

    print(f"Total: {len(source_records)}, cached: {len(translated_records)}, pending: {len(pending)}")

    with httpx.Client(timeout=120.0) as client:
        for start in range(0, len(pending), args.batch_size):
            batch = pending[start:start + args.batch_size]
            for attempt in range(1, 4):
                try:
                    translated_batch = translate_batch(client, api_key, base_url, model, batch)
                    by_id = {item.get("id"): item for item in translated_batch}
                    for original in batch:
                        translated = by_id.get(original["_translationId"])
                        if not translated:
                            raise ValueError(f"缺少翻译结果 id={original['_translationId']}")
                        merged = merge_translation(original, translated)
                        cache[make_cache_key(original)] = merged
                        translated_records.append(merged)
                    save_cache(cache)
                    print(f"Translated {min(start + len(batch), len(pending))}/{len(pending)} pending")
                    time.sleep(args.sleep)
                    break
                except Exception as exc:
                    if attempt >= 3:
                        raise
                    print(f"Batch failed, retry {attempt}/3: {exc}")
                    time.sleep(2 * attempt)

    ordered_records = []
    for record in source_records:
        key = make_cache_key(record)
        if key not in cache:
            raise RuntimeError(f"缓存缺少记录：{key}")
        ordered_records.append(cache[key])

    write_outputs(ordered_records)
    print(json.dumps({
        "total": len(ordered_records),
        "jsonPreview": str(OUTPUT_JSON),
        "sql": str(OUTPUT_SQL),
        "summary": str(OUTPUT_SUMMARY),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
