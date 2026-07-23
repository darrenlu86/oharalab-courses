"""
WebSocket 路由——`/ws/admin/orders`（後台即時訂單看板）與 `/ws/my/orders`
（顧客本人訂單即時更新）。本階段新增，stage5 完全沒有這個檔案。

## 為什麼 JWT 放在 query string，不是 Authorization header

一般 REST API（見 app/deps.py 的 `get_current_user`）都是把 JWT 放進
`Authorization: Bearer <token>` header，這是業界標準做法。但瀏覽器原生的
`WebSocket` 建構子（`new WebSocket(url)`）**沒有辦法附加自訂 header**——
這是瀏覽器 WebSocket API 的先天限制，不是本專案的設計選擇。實務上常見的兩種
繞過方式：(a) 把 token 放進網址的 query string（`?token=xxx`）、(b) 先用一般
HTTP 請求換一個一次性的短效 ws-token 再拿去連線。本課程選 (a)——更簡單、
更容易懂，缺點是 token 會被記錄進伺服器的存取日誌（access log）；(b) 更安全但
多一輪 HTTP 往返，正式產品如果在意 token 出現在日誌裡，建議改用 (b) 或改用
只在 WebSocket handshake 當下有效的一次性票證，這裡誠實標示為教學簡化。

## 認證失敗的處理方式

WebSocket 的「連線被拒絕」在協定層沒有像 HTTP 401/403 那麼明確的狀態碼可以用，
這裡採用的做法是：**先 `accept()`，緊接著用自訂 close code 關閉**——
FastAPI/Starlette 的測試工具（`TestClient.websocket_connect`）對「還沒 accept
就 close」的行為在不同版本間不一致，「先 accept 再立刻 close」是比較穩定、
容易寫測試斷言的做法。本專案用 `4401`（4000-4999 是 WebSocket 協定保留給
應用程式自訂的區間）代表「未登入或 token 無效」，`4403` 代表「登入了但不是
admin」，讓前端可以依照 close code 判斷要不要導去登入頁、要不要重連
（見 docs/REALTIME.md「重連策略」一節——認證失敗不應該無限重連，只有網路
瞬斷才應該重連）。
"""

import sqlite3

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.db.database import get_connection, get_user_by_id
from app.security import decode_access_token
from app.ws_manager import manager

router = APIRouter(tags=["realtime"])

CLOSE_UNAUTHENTICATED = 4401
CLOSE_FORBIDDEN = 4403


def _authenticate_ws_token(token: str | None) -> dict | None:
    """驗證 query string 帶進來的 token，回傳使用者 dict 或 None（驗證失敗）。

    跟 app/deps.py 的 `get_current_user` 是同一套驗證邏輯（解碼 JWT、查使用者），
    刻意不共用同一支函式：`get_current_user` 是 FastAPI 的 Depends，設計上會
    直接拋 HTTPException（給一般 HTTP 路由用），WebSocket 路由需要的是「回傳
    None 讓呼叫端自己決定要怎麼關閉連線」，兩種控制流程不一樣，硬要共用反而
    要多包一層 try/except 去「吃掉」HTTPException，可讀性更差。
    """
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub"))
    except Exception:  # noqa: BLE001 — token 格式錯、過期、簽章不對，統一視為驗證失敗
        return None

    conn: sqlite3.Connection = get_connection()
    try:
        return get_user_by_id(conn, user_id)
    finally:
        conn.close()


@router.websocket("/ws/admin/orders")
async def admin_orders_ws(websocket: WebSocket, token: str | None = None) -> None:
    user = _authenticate_ws_token(token)
    if user is None:
        await websocket.accept()
        await websocket.close(code=CLOSE_UNAUTHENTICATED, reason="請先登入")
        return
    if user["role"] != "admin":
        await websocket.accept()
        await websocket.close(code=CLOSE_FORBIDDEN, reason="需要管理員權限")
        return

    await manager.connect_admin(websocket)
    try:
        while True:
            # 這個連線本身是「伺服器單向推播給瀏覽器」，不需要瀏覽器傳任何內容
            # 過來；但還是要呼叫 `receive_text()` 卡在這裡等待，一來讓這個
            # coroutine 保持存活（不然函式一結束，Starlette 就會關閉連線），
            # 二來這是偵測「瀏覽器已經關閉分頁/斷線」最直接的方式——對方斷線時
            # 這裡會拋出 WebSocketDisconnect。前端目前不會主動送任何文字訊息，
            # 但保留這個迴圈能收，方便未來擴充「心跳 ping」（見 docs/REALTIME.md）。
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect_admin(websocket)


@router.websocket("/ws/my/orders")
async def my_orders_ws(websocket: WebSocket, token: str | None = None) -> None:
    user = _authenticate_ws_token(token)
    if user is None:
        await websocket.accept()
        await websocket.close(code=CLOSE_UNAUTHENTICATED, reason="請先登入")
        return

    user_id = user["id"]
    await manager.connect_user(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect_user(user_id, websocket)
