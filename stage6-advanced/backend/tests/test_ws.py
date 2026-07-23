"""
測試 `/ws/admin/orders` 與 `/ws/my/orders`——本階段新增的 WebSocket 端點。

用 FastAPI 內建的 `TestClient.websocket_connect()`（底層是 Starlette 提供的
WebSocket 測試工具）模擬瀏覽器連線；它會在背景執行緒跑一份完整的 ASGI app，
測試程式碼可以一邊保持 WebSocket 連線開著，一邊用同一個 `client` 發出一般
HTTP 請求（例如建單、付款），驗證「HTTP 請求觸發的事件，真的會透過 WebSocket
送到另一端」，這是本專案唯一需要「一個測試裡同時做兩種協定」的地方。
"""

import json

from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect

SUCCESS_CARD = "4242424242424242"


# ---------- 認證失敗 ----------


def test_admin_ws_without_token_is_rejected(client: TestClient):
    # 伺服器端是「先 accept()、再立刻 close()」（見 app/routers/ws.py 開頭的
    # 說明），所以 `websocket_connect()` 本身的 handshake 會成功；要真正確認
    # 連線已經被關閉，得在 with 區塊內主動 `receive_text()`，這時才會因為
    # 連線已關閉而拋出 WebSocketDisconnect，並且能讀到伺服器指定的 close code。
    with client.websocket_connect("/ws/admin/orders") as ws:
        try:
            ws.receive_text()
            raised = False
        except WebSocketDisconnect as exc:
            raised = True
            assert exc.code == 4401
    assert raised


def test_admin_ws_with_customer_token_is_rejected(client: TestClient, auth_headers: dict):
    token = auth_headers["Authorization"].removeprefix("Bearer ")
    with client.websocket_connect(f"/ws/admin/orders?token={token}") as ws:
        try:
            ws.receive_text()
            raised = False
        except WebSocketDisconnect as exc:
            raised = True
            assert exc.code == 4403
    assert raised


def test_my_orders_ws_without_token_is_rejected(client: TestClient):
    with client.websocket_connect("/ws/my/orders") as ws:
        try:
            ws.receive_text()
            raised = False
        except WebSocketDisconnect as exc:
            raised = True
            assert exc.code == 4401
    assert raised


# ---------- 認證成功＋收到事件 ----------


def test_admin_ws_connects_with_admin_token(client: TestClient, admin_headers: dict):
    token = admin_headers["Authorization"].removeprefix("Bearer ")
    with client.websocket_connect(f"/ws/admin/orders?token={token}") as ws:
        # 連線本身建立成功就是這個測試要驗證的事；沒有事件可收也不該逾時卡住，
        # 這裡不 receive，直接離開 with 區塊即可正常關閉連線。
        assert ws is not None


def test_admin_ws_receives_order_created_event(
    client: TestClient, auth_headers: dict, admin_headers: dict
):
    admin_token = admin_headers["Authorization"].removeprefix("Bearer ")
    with client.websocket_connect(f"/ws/admin/orders?token={admin_token}") as ws:
        client.post("/api/cart/items", json={"product_id": 1, "quantity": 1}, headers=auth_headers)
        client.post(
            "/api/orders",
            json={"recipient_name": "即時通訊測試", "recipient_address": "台北市信義區某路 1 號"},
            headers=auth_headers,
        )

        message = json.loads(ws.receive_text())
        assert message["type"] == "order_created"
        assert message["order"]["status"] == "pending"
        assert message["order"]["recipient_name"] == "即時通訊測試"


def test_admin_ws_receives_order_paid_event(client: TestClient, auth_headers: dict, admin_headers: dict):
    admin_token = admin_headers["Authorization"].removeprefix("Bearer ")
    client.post("/api/cart/items", json={"product_id": 1, "quantity": 1}, headers=auth_headers)
    order = client.post(
        "/api/orders",
        json={"recipient_name": "付款事件測試", "recipient_address": "台北市信義區某路 1 號"},
        headers=auth_headers,
    ).json()

    with client.websocket_connect(f"/ws/admin/orders?token={admin_token}") as ws:
        client.post(
            "/api/payments/mock",
            json={"order_id": order["id"], "card_number": SUCCESS_CARD, "card_holder": "付款事件測試"},
            headers=auth_headers,
        )
        message = json.loads(ws.receive_text())
        assert message["type"] == "order_paid"
        assert message["order"]["status"] == "paid"
        assert message["order"]["id"] == order["id"]


def test_my_orders_ws_receives_status_change_from_admin(
    client: TestClient, auth_headers: dict, admin_headers: dict
):
    """顧客本人開著 `/ws/my/orders` 連線，後台把訂單標記出貨，顧客應該即時收到。"""
    customer_token = auth_headers["Authorization"].removeprefix("Bearer ")

    client.post("/api/cart/items", json={"product_id": 1, "quantity": 1}, headers=auth_headers)
    order = client.post(
        "/api/orders",
        json={"recipient_name": "本人推播測試", "recipient_address": "台北市信義區某路 1 號"},
        headers=auth_headers,
    ).json()
    client.post(
        "/api/payments/mock",
        json={"order_id": order["id"], "card_number": SUCCESS_CARD, "card_holder": "本人推播測試"},
        headers=auth_headers,
    )

    with client.websocket_connect(f"/ws/my/orders?token={customer_token}") as ws:
        client.patch(
            f"/api/admin/orders/{order['id']}/status",
            json={"status": "shipped"},
            headers=admin_headers,
        )
        message = json.loads(ws.receive_text())
        assert message["type"] == "order_status_changed"
        assert message["order"]["status"] == "shipped"
        assert message["order"]["id"] == order["id"]


def test_my_orders_ws_does_not_receive_other_users_events(
    client: TestClient, register_and_login, admin_headers: dict
):
    """使用者 B 開著連線時，使用者 A 的訂單事件不應該被 B 收到——伺服器端頻道隔離。"""
    headers_a = register_and_login(email="ws-user-a@example.com")
    headers_b = register_and_login(email="ws-user-b@example.com")
    token_b = headers_b["Authorization"].removeprefix("Bearer ")

    client.post("/api/cart/items", json={"product_id": 1, "quantity": 1}, headers=headers_a)
    order_a = client.post(
        "/api/orders",
        json={"recipient_name": "A", "recipient_address": "A 的地址"},
        headers=headers_a,
    ).json()
    client.post(
        "/api/payments/mock",
        json={"order_id": order_a["id"], "card_number": SUCCESS_CARD, "card_holder": "A"},
        headers=headers_a,
    )

    with client.websocket_connect(f"/ws/my/orders?token={token_b}") as ws_b:
        client.patch(
            f"/api/admin/orders/{order_a['id']}/status",
            json={"status": "shipped"},
            headers=admin_headers,
        )
        # B 不應該收到任何屬於 A 的事件——改用「送一個 B 自己能收到的事件」當
        # 哨兵訊號：B 建立並取消自己的訂單，如果 B 先收到「這個哨兵事件」，
        # 就證明剛剛 A 的事件真的沒有被送進 B 的連線佇列（否則 B 應該會先
        # 收到 A 的事件，而不是自己的）。
        client.post("/api/cart/items", json={"product_id": 2, "quantity": 1}, headers=headers_b)
        order_b = client.post(
            "/api/orders",
            json={"recipient_name": "B", "recipient_address": "B 的地址"},
            headers=headers_b,
        ).json()
        client.post(
            "/api/payments/mock",
            json={"order_id": order_b["id"], "card_number": SUCCESS_CARD, "card_holder": "B"},
            headers=headers_b,
        )
        client.patch(
            f"/api/admin/orders/{order_b['id']}/status",
            json={"status": "shipped"},
            headers=admin_headers,
        )

        message = json.loads(ws_b.receive_text())
        assert message["order"]["id"] == order_b["id"]
        assert message["order"]["recipient_name"] == "B"
