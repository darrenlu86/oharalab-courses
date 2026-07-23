"""
測試 /api/orders*：從購物車建立訂單、查詢訂單列表與詳情。

跟 meowshop 的「建單不扣庫存，付款才扣庫存」不同，本階段建單當下就直接扣庫存
（見 app/routers/orders.py 開頭的說明），所以這裡的測試直接驗證「建單」這一個動作
本身要負責的事：庫存正確減少、購物車被清空、多品項總額正確加總、庫存不足要
409 且不建立訂單、以及訂單只能被本人查到。
"""

import sqlite3

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


def test_create_order_success_decreases_stock_and_clears_cart(client: TestClient, auth_headers: dict):
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

    # 商品庫存實際減少（實測行為，不是猜測）
    after = client.get("/api/products/1").json()
    assert after["stock"] == 23

    # 購物車在建單成功後被清空
    cart = client.get("/api/cart", headers=auth_headers).json()
    assert cart["items"] == []


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


def test_create_order_insufficient_stock_returns_409_and_no_order_created(
    client: TestClient, auth_headers: dict, db_path
):
    # 商品 6 種子庫存是 3，先把 3 件加進購物車（此時加進購物車本身沒有超過庫存）。
    client.post("/api/cart/items", json={"product_id": 6, "quantity": 3}, headers=auth_headers)

    # 模擬「下單前，庫存被別的請求搶先扣走」的競態情境：直接在資料庫層把庫存改成 1，
    # 這是測試環境刻意製造的條件，不是這支 API 本身的行為——本專案沒有另外開一個
    # 真的並發請求去重現 race condition（那需要多執行緒/多程序測試工具），
    # 這裡只驗證「庫存不足時建單會被擋下來」這個結果，手法上是誠實的簡化。
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE products SET stock = 1 WHERE id = 6")
    conn.commit()
    conn.close()

    resp = client.post(
        "/api/orders",
        json={"recipient_name": "小華", "recipient_address": "高雄市前鎮區某路 3 號"},
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "庫存不足，目前只剩 1 件"

    # 建單失敗，不應該留下任何訂單
    orders = client.get("/api/orders", headers=auth_headers).json()
    assert orders["items"] == []

    # 也不應該扣到庫存（rollback 生效，庫存維持在測試手動設定的 1）
    product = client.get("/api/products/6").json()
    assert product["stock"] == 1


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


def test_get_order_with_oversized_id_returns_422_not_500(client: TestClient, auth_headers: dict):
    # 20 位數遠超過 SQLite INTEGER 欄位的 64-bit 範圍——修復前這種輸入會在
    # `sqlite3` 綁定參數時丟出未接住的 `OverflowError`，變成一支 500；
    # 修復後 FastAPI 在還沒碰到資料庫之前，就靠 `Path(..., le=SQLITE_INT64_MAX)`
    # 把它擋成 422（見 app/routers/orders.py、app/schemas.py `SQLITE_INT64_MAX`）。
    resp = client.get("/api/orders/99999999999999999999", headers=auth_headers)
    assert resp.status_code == 422
    assert resp.status_code != 500
