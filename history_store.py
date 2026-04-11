import json
from pathlib import Path

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

HISTORY_FILE = DATA_DIR / "history.json"

if not HISTORY_FILE.exists():
    HISTORY_FILE.write_text("[]", encoding="utf-8")


def load_history():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_history(history_list):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history_list, f, ensure_ascii=False, indent=2)


def add_history_record(record: dict):
    history = load_history()
    history.insert(0, record)
    save_history(history)


def clear_history_records():
    save_history([])