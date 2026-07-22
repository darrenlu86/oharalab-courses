"""
認證路由——/api/auth/*：註冊、登入、查詢自己的資料。

在架構中的位置：路由層（HTTP 進出的第一線），只負責「解析 request → 呼叫
repository/security → 組成 response」，不直接碰 SQL，也不直接處理 bcrypt/JWT
的底層細節（那些在 security.py）。
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import Repos, get_current_user, get_repos
from app.repositories.base import DuplicateEmailError
from app.schemas import TokenOut, UserCreate, UserLogin, UserOut, UserPublic
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, repos: Repos = Depends(get_repos)) -> UserOut:
    # 密碼一定要在存進資料庫之前就雜湊完成，repository 層完全看不到明文密碼。
    password_hash = hash_password(payload.password)
    try:
        user = repos.users.create(payload.email, password_hash, payload.name)
    except DuplicateEmailError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="這個 email 已經註冊過了",
        )
    return UserOut(**user)


@router.post("/login", response_model=TokenOut)
def login(payload: UserLogin, repos: Repos = Depends(get_repos)) -> TokenOut:
    user = repos.users.get_by_email(payload.email)
    # 注意（教學安全點）：「查無此 email」跟「密碼錯誤」要回一模一樣的錯誤訊息與狀態碼。
    # 如果分開回不同訊息（例如「這個 email 不存在」），等於變相讓攻擊者可以
    # 一個一個 email 去試探「這個帳號到底存不存在」，是常見的帳號列舉（enumeration）漏洞。
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="email 或密碼錯誤",
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
