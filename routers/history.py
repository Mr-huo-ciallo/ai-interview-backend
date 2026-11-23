from fastapi import APIRouter, Depends

from crud import add_history_record, clear_history_records, get_history_list
from db import get_db
from dependencies import require_current_user
from schemas import HistoryRecord


router = APIRouter(prefix="/api/history", tags=["history"])


@router.post("/add")
def add_history(
    record: HistoryRecord,
    current_user=Depends(require_current_user),
    db=Depends(get_db),
):
    record_data = record.model_dump()
    record_data["userId"] = current_user.id
    add_history_record(db, record_data)
    return {"message": "history saved successfully"}


@router.get("/list")
def get_history(current_user=Depends(require_current_user), db=Depends(get_db)):
    history = get_history_list(db, current_user.id)
    return {"history": history}


@router.delete("/clear")
def clear_history(current_user=Depends(require_current_user), db=Depends(get_db)):
    clear_history_records(db, current_user.id)
    return {"message": "history cleared successfully"}
