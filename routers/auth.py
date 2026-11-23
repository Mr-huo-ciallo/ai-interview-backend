from fastapi import APIRouter, Depends, HTTPException, status

from auth_utils import (
    create_access_token,
    hash_password,
    is_legacy_password_hash,
    verify_password,
)
from crud import create_user, get_user_by_username
from db import get_db
from dependencies import get_admin_usernames, is_admin_user, require_current_user
from schemas import LoginRequest, RegisterRequest


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
def register(data: RegisterRequest, db=Depends(get_db)):
    existing_user = get_user_by_username(db, data.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = create_user(
        db,
        username=data.username,
        password_hash=hash_password(data.password),
        is_admin=data.username.strip().lower() in get_admin_usernames(),
    )

    return {
        "message": "register success",
        "user": {
            "id": user.id,
            "username": user.username,
            "isAdmin": is_admin_user(user),
        },
    }


@router.post("/login")
def login(data: LoginRequest, db=Depends(get_db)):
    user = get_user_by_username(db, data.username)
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if is_legacy_password_hash(user.password_hash):
        user.password_hash = hash_password(data.password)
        db.commit()

    return {
        "message": "login success",
        "accessToken": create_access_token(user.id, user.username),
        "user": {
            "id": user.id,
            "username": user.username,
            "isAdmin": is_admin_user(user),
        },
    }


@router.get("/user/{user_id}")
def get_current_user(user_id: int, current_user=Depends(require_current_user)):
    if user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问其他用户信息")
    return {
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "isAdmin": is_admin_user(current_user),
        }
    }
