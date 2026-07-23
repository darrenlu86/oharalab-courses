"""
測試 /api/orders*：從購物車建立訂單、查詢訂單列表與詳情、取消訂單。

跟 stage4 最大的差異：本階段建單「不」扣庫存（付款成功才扣，見
tests/test_payments.py），所以這裡的建單測試改成驗證「庫存維持不變」，
而不是「庫存正確減少」——那個行為已經搬到 test_payments.py 去驗證了。
"""

from fastapi.testclient import TestClient


def test_create_order_without_login_returns_401(client: TestClient):
    resp = client.post("/api/orders", json={"recipient_name": "小明", "recipient_address": "台北市信義區某路 1 號"})
    assert resp.status_code == 401


def test_create_order_with_empty_cart_returns_400(client: TestClient, auth_headers: dict):
    resp = client.post(
        "/api/orders",
        json={"recipient_name": "小明", "recipient_address": "台北市信義區某路 1 號"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "購物車是空的"


def test_create_order_success_does_not_decrease_stock_but_clears_cart(client: TestClient, auth_headers: dict):
    # 下單前查一次商品 1 的庫存（種子資料是 25）
    before = client.get("/api/products/1").json()
    assert before["stock"] == 25

    client.post("/api/cart/items", json={"product_id": 1, "quantity": 2}, headers=auth_headers)

    resp = client.post(
        "/api/orders",
        json={"recipient_name": "王小明", "recipient_address": "台北市信義區某路 1 號"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending"
    assert body["total_amount"] == 1040  # 520 * 2
    assert body["recipient_name"] == "王小明"
    assert len(body["items"]) == 1
    assert body["items"][0] == {
        "product_id": 1,
        "product_name": "耶加雪菲 淺焙單品豆 250g",
        "unit_price": 520,
        "quantity": 2,
    }

    # 跟 stage4 最大的差異：建單當下庫存維持不變（實測行為），要付款成功才會扣，
    # 見 tests/test_payments.py 的對照測試。
    after = client.get("/api/products/1").json()
    assert after["stock"] == 25

    # 購物車在建單成功後被清空
    cart = client.get("/api/cart", headers=auth_headers).json()
    assert cart["items"] == []


def test_create_order_can_exceed_stock_because_it_does_not_reserve_it(client: TestClient, auth_headers: dict):
    # 教學點：建單不再檢查庫存（跟購物車加入時的庫存檢查是兩件事），商品 6
    # 種子庫存只有 3，這裡把 3 件全部下單，下單本身不會因為「之後可能不夠付款」
    # 而被擋下來——庫存檢查真正生效的時間點在付款，見 test_payments.py。
    client.post("/api/cart/items", json={"product_id": 6, "quantity": 3}, headers=auth_headers)
    resp = client.post(
        "/api/orders",
        json={"recipient_name": "小華", "recipient_address": "高雄市前鎮區某路 3 號"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending"


def test_create_order_with_multiple_items_sums_total_amount(client: TestClient, auth_headers: dict):
    client.post("/api/cart/items", json={"product_id": 1, "quantity": 1}, headers=auth_headers)  # 520
    client.post("/api/cart/items", json={"product_id": 2, "quantity": 2}, headers=auth_headers)  # 460 * 2

    resp = client.post(
        "/api/orders",
        json={"recipient_name": "小美", "recipient_address": "台中市西區某路 2 號"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["total_amount"] == 520 + 460 * 2
    assert len(body["items"]) == 2


def test_create_order_with_delisted_item_returns_409(client: TestClient, auth_headers: dict, admin_headers: dict):
    # 購物車不會因為商品被下架而自動清掉這一項（見 app/db/database.py
    # `get_cart_items()`）——前端購物車頁會提早顯示「已下架」徽章、停用結帳
    # 按鈕（見 frontend/src/pages/Cart.jsx），但那只是體驗優化，不是安全邊界；
    # 這裡驗證的是就算跳過前端提示直接打 API，後端在建單這一刻仍然會親自
    # 重新查一次商品最新狀態，獨立擋下來。
    client.post("/api/cart/items", json={"product_id": 1, "quantity": 1}, headers=auth_headers)
    deactivate_resp = client.patch("/api/admin/products/1", json={"is_active": False}, headers=admin_headers)
    assert deactivate_resp.status_code == 200

    resp = client.post(
        "/api/orders",
        json={"recipient_name": "小明", "recipient_address": "台北市信義區某路 1 號"},
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "購物車內有商品已下架"

    # 建單失敗時購物車完全不動——不會被悄悄清空，使用者還可以自己決定要不要移除。
    cart = client.get("/api/cart", headers=auth_headers).json()
    assert len(cart["items"]) == 1
    assert cart["items"][0]["is_active"] is False


def test_list_orders_without_login_returns_401(client: TestClient):
    resp = client.get("/api/orders")
    assert resp.status_code == 401


def test_list_orders_returns_created_orders_newest_first(client: TestClient, auth_headers: dict):
    client.post("/api/cart/items", json={"product_id": 1, "quantity": 1}, headers=auth_headers)
    first = client.post(
        "/api/orders",
        json={"recipient_name": "客人一", "recipient_address": "地址一"},
        headers=auth_headers,
    ).json()

    client.post("/api/cart/items", json={"product_id": 2, "quantity": 1}, headers=auth_headers)
    second = client.post(
        "/api/orders",
        json={"recipient_name": "客人二", "recipient_address": "地址二"},
        headers=auth_headers,
    ).json()

    resp = client.get("/api/orders", headers=auth_headers)
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["items"]]
    assert ids == [second["id"], first["id"]]


def test_get_order_by_id(client: TestClient, auth_headers: dict):
    client.post("/api/cart/items", json={"product_id": 1, "quantity": 1}, headers=auth_headers)
    created = client.post(
        "/api/orders",
        json={"recipient_name": "客人", "recipient_address": "某地址"},
        headers=auth_headers,
    ).json()

    resp = client.get(f"/api/orders/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_order_not_found_returns_404(client: TestClient, auth_headers: dict):
    resp = client.get("/api/orders/9999", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "找不到這筆訂單"


def test_get_other_users_order_returns_404(client: TestClient, register_and_login):
    headers_a = register_and_login(email="order-a@example.com")
    headers_b = register_and_login(email="order-b@example.com")

    client.post("/api/cart/items", json={"product_id": 1, "quantity": 1}, headers=headers_a)
    order_a = client.post(
        "/api/orders",
        json={"recipient_name": "A", "recipient_address": "A 的地址"},
        headers=headers_a,
    ).json()

    # user B 拿 user A 的訂單 id 去查，應該回 404（不是 403），避免洩漏這筆訂單存在
    resp = client.get(f"/api/orders/{order_a['id']}", headers=headers_b)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "找不到這筆訂單"


# ---------- 取消訂單（stage5 新增） ----------


def test_cancel_pending_order_success(client: TestClient, auth_headers: dict):
    client.post("/api/cart/items", json={"product_id": 1, "quantity": 1}, headers=auth_headers)
    order = client.post(
        "/api/orders",
        json={"recipient_name": "客人", "recipient_address": "某地址"},
        headers=auth_headers,
    ).json()

    resp = client.post(f"/api/orders/{order['id']}/cancel", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_cancel_order_without_login_returns_401(client: TestClient):
    resp = client.post("/api/orders/1/cancel")
    assert resp.status_code == 401


def test_cancel_nonexistent_order_returns_404(client: TestClient, auth_headers: dict):
    resp = client.post("/api/orders/9999/cancel", headers=auth_headers)
    assert resp.status_code == 404


def test_cancel_paid_order_by_customer_returns_409(client: TestClient, auth_headers: dict):
    client.post("/api/cart/items", json={"product_id": 1, "quantity": 1}, headers=auth_headers)
    order = client.post(
        "/api/orders",
        json={"recipient_name": "客人", "recipient_address": "某地址"},
        headers=auth_headers,
    ).json()
    client.post(
        "/api/payments/mock",
        json={"order_id": order["id"], "card_number": "4242424242424242", "card_holder": "客人"},
        headers=auth_headers,
    )

    resp = client.post(f"/api/orders/{order['id']}/cancel", headers=auth_headers)
    assert resp.status_code == 409


def test_cancel_already_cancelled_order_returns_409(client: TestClient, auth_headers: dict):
    client.post("/api/cart/items", json={"product_id": 1, "quantity": 1}, headers=auth_headers)
    order = client.post(
        "/api/orders",
        json={"recipient_name": "客人", "recipient_address": "某地址"},
        headers=auth_headers,
    ).json()
    client.post(f"/api/orders/{order['id']}/cancel", headers=auth_headers)

    resp = client.post(f"/api/orders/{order['id']}/cancel", headers=auth_headers)
    assert resp.status_code == 409


def test_get_order_with_oversized_id_returns_422_not_500(client: TestClient, auth_headers: dict):
    # 20 位數遠超過 SQLite INTEGER 欄位的 64-bit 範圍——修復前這種輸入會在
    # `sqlite3` 綁定參數時丟出未接住的 `OverflowError`，變成一支 500；
    # 修復後 FastAPI 在還沒碰到資料庫之前，就靠 `Path(..., le=SQLITE_INT64_MAX)`
    # 把它擋成 422（見 app/routers/orders.py、app/schemas.py `SQLITE_INT64_MAX`）。
    resp = client.get("/api/orders/99999999999999999999", headers=auth_headers)
    assert resp.status_code == 422
    assert resp.status_code != 500
