from fastapi import APIRouter, Depends

from db import get_db
from dependencies import require_current_user
from rate_limit import create_rate_limiter
from schemas import LlmConfigTestRequest, LlmConfigUpdateRequest
from services.llm_settings import (
    LLM_PROVIDER_PRESETS,
    delete_user_llm_config,
    get_llm_settings_payload,
    test_user_llm_config,
    upsert_user_llm_config,
)


router = APIRouter(prefix="/api/settings/llm", tags=["llm-settings"])
llm_test_rate_limit = create_rate_limiter("llm_test", "RATE_LIMIT_LLM_TEST_MAX", 10)


@router.get("/providers")
def list_llm_providers():
    return {"providers": LLM_PROVIDER_PRESETS}


@router.get("")
def get_llm_settings(current_user=Depends(require_current_user), db=Depends(get_db)):
    return get_llm_settings_payload(db, current_user.id)


@router.put("")
def update_llm_settings(
    data: LlmConfigUpdateRequest,
    current_user=Depends(require_current_user),
    db=Depends(get_db),
):
    return upsert_user_llm_config(db, current_user.id, data.model_dump())


@router.post("/test")
def test_llm_settings(
    data: LlmConfigTestRequest,
    _rate_limit=Depends(llm_test_rate_limit),
    current_user=Depends(require_current_user),
    db=Depends(get_db),
):
    return test_user_llm_config(db, current_user.id, data.model_dump())


@router.delete("")
def clear_llm_settings(current_user=Depends(require_current_user), db=Depends(get_db)):
    return delete_user_llm_config(db, current_user.id)
