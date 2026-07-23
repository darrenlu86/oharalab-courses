"""
依賴注入層（FastAPI dependencies）。

`get_db`：每個 request 開一條 SQLite 連線給路由函式用，request 處理完（不管成功或
拋例外）自動關閉——用 FastAPI 的 generator dependency 寫法（`yield` 一次）確保這件事。

`get_current_user`：解析 `Authorization: Bearer <token>`，驗證 JWT，查出目前登入的
使用者，任何「需要登入」的端點都掛這個依賴即可。跟 meowshop 的 deps.py 同一套設計：
不管是「完全沒帶 token」「格式不對」「token 過期」還是「使用者已不存在」，一律回
同一句「請先登入」，不對外區分驗證失敗的細節。

`require_admin`：stage5 新增。所有 `/api/admin/*` 端點都掛這個依賴——它疊在
`get_current_user` 之上（先確定「有登入」，再確定「登入的是 admin」），角色不對
回 403（不是 401：401 代表「你根本沒登入」，403 代表「你登入了，但沒有權限」，
兩者語意不同，見 docs/SYSTEM_DESIGN.md「權限矩陣」一節）。
"""

import sqlite3
from typing import Generator

from fastapi import Depends, Header, HTTPException, status

from app.db.database import get_connection, get_user_by_id
from app.security import decode_access_token


def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def get_current_user(
    authorization: str | None = Header(default=None),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="請先登入")

    if not authorization or not authorization.startswith("Bearer "):
        raise unauthorized

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise unauthorized

    try:
        payload = decode_access_token(token)
    except Exception as exc:  # PyJWT 對「過期」「簽章不對」「格式錯」丟出不同子類別例外，統一接住
        raise unauthorized from exc

    user_id_raw = payload.get("sub")
    try:
        # sub 欄位在簽章驗證上沒問題，不代表內容一定能被 int() 解析；
        # None 或非數字字串都應該跟 decode 失敗共用同一個 401 分支，不能讓例外一路炸成 500。
        user_id = int(user_id_raw)
    except (TypeError, ValueError) as exc:
        raise unauthorized from exc

    user = get_user_by_id(conn, user_id)
    if user is None:
        raise unauthorized

    return user


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理員權限")
    return current_user
