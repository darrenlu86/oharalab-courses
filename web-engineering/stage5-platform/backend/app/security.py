"""
安全層——密碼雜湊（bcrypt）與 JWT token 的簽發/解析（HS256，24 小時過期）。

跟 meowshop 教學範例的 security.py 是同一套實作與同一套設計理由（bcrypt 自動加鹽、
JWT payload 只放最小必要資訊、24 小時過期是安全性與體驗的折衷），這裡不重複展開，
細節見 meowshop-tutorial/backend/app/security.py 的註解，或本專案 docs/ARCHITECTURE.md。
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import get_settings

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        # bcrypt 演算法本身有 72 bytes 上限；正常流程下 schemas.py 的驗證器
        # 應該已經先擋下來，這裡是給「不經過 FastAPI schema 驗證」直接呼叫
        # 這個函式的呼叫端（例如未來的 CLI 工具）多一道防線。
        raise ValueError("密碼太長：最長 72 個位元組（bcrypt 演算法的限制）")
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: int, email: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": now,
        "exp": now + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
