from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth_utils import decode_access_token
from crud import get_user_by_id
from db import get_db
from llm_client import reset_runtime_llm_config, set_runtime_llm_config
from services.llm_settings import get_user_active_llm_runtime_config


security = HTTPBearer(auto_error=False)


def resolve_token_user(credentials: HTTPAuthorizationCredentials, db):
    try:
        payload = decode_access_token(credentials.credentials)
        user = get_user_by_id(db, int(payload["sub"]))
        if not user:
            raise ValueError("用户不存在")
        return user
    except (ValueError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效，请重新登录")


async def require_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db=Depends(get_db),
):
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    user = resolve_token_user(credentials, db)
    active_llm_config = get_user_active_llm_runtime_config(db, user.id)
    if not active_llm_config:
        yield user
        return
    token = set_runtime_llm_config(active_llm_config)
    try:
        yield user
    finally:
        reset_runtime_llm_config(token)


async def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db=Depends(get_db),
):
    if not credentials:
        yield None
        return
    if credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录凭证格式无效")
    user = resolve_token_user(credentials, db)
    active_llm_config = get_user_active_llm_runtime_config(db, user.id)
    if not active_llm_config:
        yield user
        return
    token = set_runtime_llm_config(active_llm_config)
    try:
        yield user
    finally:
        reset_runtime_llm_config(token)
