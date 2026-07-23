"""
WebSocket 連線管理——本階段新增，stage5 完全沒有即時通訊。

## WebSocket vs Socket.IO

課程刻意選用 FastAPI 原生 WebSocket（Starlette 內建，不需要額外套件），自己寫
`ConnectionManager` 管連線清單、自己在前端寫斷線重連，而不是直接套一個
Socket.IO 套件（`python-socketio` + 前端 `socket.io-client`）。理由不是
「Socket.IO 不好」，而是教學順序：Socket.IO 是在原生 WebSocket 協定之上，
多加了幾層封裝——

- **房間（room）**：讓伺服器可以「只廣播給訂閱了某個頻道的連線」，本專案自己
  用兩個 Python 資料結構（`_admin_connections` 這個 set、`_user_connections`
  這個 dict）土法煉鋼做到一樣的效果，規模一大，Socket.IO 的房間 API 會更省事。
- **自動重連＋降級**：瀏覽器不支援 WebSocket，或是網路環境擋掉 WebSocket 協定時，
  Socket.IO 會自動退回 HTTP long-polling；本專案完全沒有降級機制，斷線重連
  邏輯是前端自己手刻的 exponential backoff（見 `frontend/src/hooks/useOrdersSocket.js`
  / `admin/src/hooks/useAdminOrdersSocket.js`），純教學示範不含降級。
- **ACK／事件命名空間**：Socket.IO 有內建的「送出事件並等待對方回覆」機制，
  本專案的訊息全部是單向推播（伺服器 → 瀏覽器），沒有這個需求。

**學這個階段的目的**：先看懂「一個 WebSocket 連線在伺服器端到底是什麼」（一個
需要自己追蹤生命週期、自己處理斷線的物件），之後如果專案規模變大真的需要
Socket.IO 那些便利功能，才知道自己引入的套件實際上幫你做了什麼、省下了多少
你剛剛自己動手寫過的程式碼。

## 訊息格式

所有訊息都是 JSON 字串，統一形狀：

```json
{"type": "order_created" | "order_paid" | "order_status_changed", "order": { ...OrderDetailOut 或 AdminOrderOut 的欄位... }}
```

`type` 讓前端知道要怎麼處理這個事件（例如 `order_created` 要在列表最上面插入
一筆新的、`order_status_changed` 要找到既有那一筆更新狀態），`order` 直接放
完整的訂單物件，前端不需要再另外打一次 API 補資料。完整的訊息型別與循序圖見
docs/REALTIME.md。

## 兩條頻道

- `/ws/admin/orders`：只有 `role == 'admin'` 能連上，收到「全站」的訂單事件
  （任何人建單、任何一筆訂單狀態變化都會推播給所有連線的後台）。
- `/ws/my/orders`：任何登入使用者都能連，但只會收到「自己」的訂單事件——
  伺服器端用 `user_id` 分頻道（`_user_connections: dict[int, set[WebSocket]]`），
  確保 A 使用者的瀏覽器永遠收不到 B 使用者的訂單通知，這是伺服器端強制的
  隔離，不是前端「連上去之後自己篩選」。
"""

import json
import logging

from fastapi import WebSocket

logger = logging.getLogger("app.ws")


class ConnectionManager:
    def __init__(self) -> None:
        self._admin_connections: set[WebSocket] = set()
        self._user_connections: dict[int, set[WebSocket]] = {}

    # ---------- admin 頻道 ----------

    async def connect_admin(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._admin_connections.add(websocket)

    def disconnect_admin(self, websocket: WebSocket) -> None:
        self._admin_connections.discard(websocket)

    async def broadcast_admin(self, message: dict) -> None:
        """推播給所有連線的後台管理員。

        逐一 send，任何一個連線送失敗（例如對方其實已經斷線，只是伺服器還沒
        收到斷線通知——這在 WebSocket 是常見的競態）就把它從清單移除，不讓
        一個壞掉的連線擋住其他人收訊息。這裡刻意不用 `asyncio.gather`
        平行送出：教學規模的連線數（課堂 demo 大概幾個到幾十個）循序送出的
        延遲可以忽略不計，循序寫法比平行寫法更容易看懂每一步在做什麼。
        """
        payload = json.dumps(message, ensure_ascii=False)
        dead: list[WebSocket] = []
        for connection in self._admin_connections:
            try:
                await connection.send_text(payload)
            except Exception:  # noqa: BLE001 — 連線已死的原因很多種，全部視為同一種處理
                dead.append(connection)
        for connection in dead:
            self._admin_connections.discard(connection)

    def admin_connection_count(self) -> int:
        return len(self._admin_connections)

    # ---------- 個人訂單頻道 ----------

    async def connect_user(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._user_connections.setdefault(user_id, set()).add(websocket)

    def disconnect_user(self, user_id: int, websocket: WebSocket) -> None:
        connections = self._user_connections.get(user_id)
        if connections is None:
            return
        connections.discard(websocket)
        if not connections:
            del self._user_connections[user_id]

    async def send_to_user(self, user_id: int, message: dict) -> None:
        connections = self._user_connections.get(user_id)
        if not connections:
            return  # 使用者沒有開著訂單頁——很正常，不是錯誤，安靜地什麼都不做即可
        payload = json.dumps(message, ensure_ascii=False)
        dead: list[WebSocket] = []
        for connection in connections:
            try:
                await connection.send_text(payload)
            except Exception:  # noqa: BLE001
                dead.append(connection)
        for connection in dead:
            connections.discard(connection)

    def user_connection_count(self, user_id: int) -> int:
        return len(self._user_connections.get(user_id, ()))


# 全站共用單例——跟 app/cache.py 的 products_cache 同一套理由：連線清單本來就該
# 是「整個 process 共用一份」，不是每次 import 就重新生一個空的。
manager = ConnectionManager()
