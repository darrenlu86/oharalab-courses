"""認證路由——/api/auth/*：註冊、登入、查詢自己的資料。"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status

from app.db.database import DuplicateEmailError, create_user, get_user_by_email
from app.deps import get_current_user, get_db
from app.schemas import TokenOut, UserCreate, UserLogin, UserOut, UserPublic
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, conn: sqlite3.Connection = Depends(get_db)) -> UserOut:
    # 密碼一定要在存進資料庫之前就雜湊完成，database.py 完全看不到明文密碼。
    password_hash = hash_password(payload.password)
    try:
        user = create_user(conn, payload.email, password_hash, payload.name)
    except DuplicateEmailError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="這個 email 已經註冊過了")
    return UserOut(**user)


@router.post("/login", response_model=TokenOut)
def login(payload: UserLogin, conn: sqlite3.Connection = Depends(get_db)) -> TokenOut:
    user = get_user_by_email(conn, payload.email)
    # 「查無此 email」跟「密碼錯誤」要回一模一樣的訊息與狀態碼，避免帳號列舉攻擊。
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="email 或密碼錯誤"
    )
    if user is None:
        raise invalid_credentials
    if not verify_password(payload.password, user["password_hash"]):
        raise invalid_credentials

    token = create_access_token(user_id=user["id"], email=user["email"])
    return TokenOut(
        access_token=token,
        user=UserPublic(id=user["id"], email=user["email"], name=user["name"]),
    )


@router.get("/me", response_model=UserOut)
def read_me(current_user: dict = Depends(get_current_user)) -> UserOut:
    return UserOut(**current_user)
