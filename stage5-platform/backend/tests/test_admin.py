"""
測試 /api/admin/*：stage5 新增的後台端點——全部都需要 admin 權限。

涵蓋：權限矩陣（沒登入 401 / customer 打 403 / admin 正常 200）、商品 CRUD 與
上下架對前台可見性的影響、訂單狀態機（合法/非法轉移）、summary 聚合正確性
（造數據自己驗算，不是假設後端數字一定對）、會員清單不含密碼欄位。
"""

from fastapi.testclient import TestClient

SUCCESS_CARD = "4242424242424242"


# ---------- 權限矩陣 ----------


def test_admin_summary_without_login_returns_401(client: TestClient):
    resp = client.get("/api/admin/summary")
    assert resp.status_code == 401


def test_admin_summary_as_customer_returns_403(client: TestClient, auth_headers: dict):
    resp = client.get("/api/admin/summary", headers=auth_headers)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "需要管理員權限"


def test_admin_summary_as_admin_returns_200(client: TestClient, admin_headers: dict):
    resp = client.get("/api/admin/summary", headers=admin_headers)
    assert resp.status_code == 200


def test_admin_orders_as_customer_returns_403(client: TestClient, auth_headers: dict):
    resp = client.get("/api/admin/orders", headers=auth_headers)
    assert resp.status_code == 403


def test_admin_users_as_customer_returns_403(client: TestClient, auth_headers: dict):
    resp = client.get("/api/admin/users", headers=auth_headers)
    assert resp.status_code == 403


# ---------- 商品列表（後台，含已下架） ----------


def test_admin_list_products_includes_inactive(client: TestClient, admin_headers: dict):
    client.patch("/api/admin/products/2", json={"is_active": False}, headers=admin_headers)

    resp = client.get("/api/admin/products", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 12
    ids_and_active = {item["id"]: item["is_active"] for item in body["items"]}
    assert ids_and_active[2] is False


def test_admin_list_products_as_customer_returns_403(client: TestClient, auth_headers: dict):
    resp = client.get("/api/admin/products", headers=auth_headers)
    assert resp.status_code == 403


# ---------- 商品 CRUD 與上下架 ----------


def test_admin_create_product(client: TestClient, admin_headers: dict):
    resp = client.post(
        "/api/admin/products",
        json={
            "name": "限量聯名濾掛組",
            "description": "後台新增商品測試",
            "price": 399,
            "stock": 20,
            "category": "drip",
            "image_url": "/images/p5.svg",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] > 12  # master 型錄固定 1-12 號，新商品 id 一定大於 12
    assert body["is_active"] is True

    # 新商品立刻能在前台列表看到
    list_resp = client.get("/api/products")
    ids = [item["id"] for item in list_resp.json()["items"]]
    assert body["id"] in ids


def test_admin_create_product_as_customer_returns_403(client: TestClient, auth_headers: dict):
    resp = client.post(
        "/api/admin/products",
        json={
            "name": "應該被擋下來",
            "description": "x",
            "price": 100,
            "stock": 1,
            "category": "gear",
            "image_url": "/images/p7.svg",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 403


def test_admin_update_product_price_and_stock(client: TestClient, admin_headers: dict):
    resp = client.patch(
        "/api/admin/products/1", json={"price": 550, "stock": 40}, headers=admin_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["price"] == 550
    assert body["stock"] == 40
    assert body["name"] == "耶加雪菲 淺焙單品豆 250g"  # 沒傳的欄位維持不變


def test_admin_update_nonexistent_product_returns_404(client: TestClient, admin_headers: dict):
    resp = client.patch("/api/admin/products/9999", json={"price": 100}, headers=admin_headers)
    assert resp.status_code == 404


def test_admin_deactivate_product_hides_it_from_public_list_and_detail(
    client: TestClient, admin_headers: dict
):
    # 下架前：商品 2 在前台列表跟詳情都看得到
    before_list = client.get("/api/products")
    assert 2 in [item["id"] for item in before_list.json()["items"]]
    before_detail = client.get("/api/products/2")
    assert before_detail.status_code == 200

    resp = client.patch("/api/admin/products/2", json={"is_active": False}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    after_list = client.get("/api/products")
    assert 2 not in [item["id"] for item in after_list.json()["items"]]

    after_detail = client.get("/api/products/2")
    assert after_detail.status_code == 404
    assert after_detail.json()["detail"] == "找不到這個商品"


def test_admin_reactivate_product(client: TestClient, admin_headers: dict):
    client.patch("/api/admin/products/3", json={"is_active": False}, headers=admin_headers)
    resp = client.patch("/api/admin/products/3", json={"is_active": True}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True
    assert client.get("/api/products/3").status_code == 200


# ---------- 訂單管理與狀態機 ----------


def _create_and_pay_order(client: TestClient, headers: dict) -> dict:
    client.post("/api/cart/items", json={"product_id": 1, "quantity": 1}, headers=headers)
    order = client.post(
        "/api/orders",
        json={"recipient_name": "後台測試", "recipient_address": "台北市信義區某路 9 號"},
        headers=headers,
    ).json()
    resp = client.post(
        "/api/payments/mock",
        json={"order_id": order["id"], "card_number": SUCCESS_CARD, "card_holder": "後台測試"},
        headers=headers,
    )
    return resp.json()["order"]


def test_admin_list_orders_with_status_filter(client: TestClient, auth_headers: dict, admin_headers: dict):
    _create_and_pay_order(client, auth_headers)

    resp = client.get("/api/admin/orders", params={"order_status": "paid"}, headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) >= 1
    assert all(item["status"] == "paid" for item in body["items"])


def test_admin_ship_paid_order_then_complete(client: TestClient, auth_headers: dict, admin_headers: dict):
    order = _create_and_pay_order(client, auth_headers)
    assert order["status"] == "paid"

    shipped = client.patch(
        f"/api/admin/orders/{order['id']}/status", json={"status": "shipped"}, headers=admin_headers
    )
    assert shipped.status_code == 200
    assert shipped.json()["status"] == "shipped"

    completed = client.patch(
        f"/api/admin/orders/{order['id']}/status", json={"status": "completed"}, headers=admin_headers
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"


def test_admin_illegal_transition_pending_to_completed_returns_409(
    client: TestClient, auth_headers: dict, admin_headers: dict
):
    client.post("/api/cart/items", json={"product_id": 1, "quantity": 1}, headers=auth_headers)
    order = client.post(
        "/api/orders",
        json={"recipient_name": "測試", "recipient_address": "台北市信義區某路 9 號"},
        headers=auth_headers,
    ).json()

    resp = client.patch(
        f"/api/admin/orders/{order['id']}/status", json={"status": "completed"}, headers=admin_headers
    )
    assert resp.status_code == 409


def test_admin_illegal_transition_completed_to_shipped_returns_409(
    client: TestClient, auth_headers: dict, admin_headers: dict
):
    order = _create_and_pay_order(client, auth_headers)
    client.patch(f"/api/admin/orders/{order['id']}/status", json={"status": "shipped"}, headers=admin_headers)
    client.patch(f"/api/admin/orders/{order['id']}/status", json={"status": "completed"}, headers=admin_headers)

    # completed 是終態，不能再變成 shipped
    resp = client.patch(
        f"/api/admin/orders/{order['id']}/status", json={"status": "shipped"}, headers=admin_headers
    )
    assert resp.status_code == 409


def test_admin_cancel_paid_order(client: TestClient, auth_headers: dict, admin_headers: dict):
    order = _create_and_pay_order(client, auth_headers)
    resp = client.patch(
        f"/api/admin/orders/{order['id']}/status", json={"status": "cancelled"}, headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_admin_update_status_nonexistent_order_returns_404(client: TestClient, admin_headers: dict):
    resp = client.patch("/api/admin/orders/9999/status", json={"status": "shipped"}, headers=admin_headers)
    assert resp.status_code == 404


# ---------- 會員清單 ----------


def test_admin_list_users_excludes_password_hash(client: TestClient, auth_headers: dict, admin_headers: dict):
    resp = client.get("/api/admin/users", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) >= 1
    for user in body["items"]:
        assert "password_hash" not in user
        assert "password" not in user


# ---------- summary 聚合正確性（造數據自己驗算） ----------


def test_admin_summary_aggregation_matches_hand_calculated_numbers(
    client: TestClient, register_and_login, admin_headers: dict
):
    headers = register_and_login(email="summary-test@example.com")

    # 造 3 筆訂單：1 筆 paid（算進營收＋待出貨）、1 筆 shipped（算進營收，不算待出貨）、
    # 1 筆 pending（都不算）。手算預期營收與筆數，再跟 API 回傳比對。
    def pay(product_id: int, quantity: int, card: str) -> dict:
        client.post("/api/cart/items", json={"product_id": product_id, "quantity": quantity}, headers=headers)
        order = client.post(
            "/api/orders",
            json={"recipient_name": "彙總測試", "recipient_address": "台北市信義區某路 5 號"},
            headers=headers,
        ).json()
        pay_resp = client.post(
            "/api/payments/mock",
            json={"order_id": order["id"], "card_number": card, "card_holder": "彙總測試"},
            headers=headers,
        )
        return pay_resp.json()["order"]

    before = client.get("/api/admin/summary", headers=admin_headers).json()

    order_paid = pay(1, 1, SUCCESS_CARD)  # 520
    order_shipped = pay(2, 1, SUCCESS_CARD)  # 460
    client.patch(
        f"/api/admin/orders/{order_shipped['id']}/status", json={"status": "shipped"}, headers=admin_headers
    )

    client.post("/api/cart/items", json={"product_id": 3, "quantity": 1}, headers=headers)  # 480，不付款
    client.post(
        "/api/orders",
        json={"recipient_name": "彙總測試", "recipient_address": "台北市信義區某路 5 號"},
        headers=headers,
    )

    after = client.get("/api/admin/summary", headers=admin_headers).json()

    assert after["total_revenue"] == before["total_revenue"] + 520 + 460
    assert after["total_orders"] == before["total_orders"] + 3
    assert after["pending_shipment_orders"] == before["pending_shipment_orders"] + 1  # 只有 order_paid 還是 paid
    # register_and_login() 在「before」快照之前就已經建好會員帳號了，這裡的操作
    # 都沒有再建立新會員，member_count 應該維持不變。
    assert after["member_count"] == before["member_count"]

    assert order_paid["status"] == "paid"


def test_admin_summary_low_stock_products_includes_seed_samples(client: TestClient, admin_headers: dict):
    resp = client.get("/api/admin/summary", headers=admin_headers)
    body = resp.json()
    low_stock_ids = {item["id"] for item in body["low_stock_products"]}
    # 種子資料 id=6（庫存 3）、id=11（庫存 0）都低於門檻 5，一定要出現在清單裡。
    assert {6, 11}.issubset(low_stock_ids)


def test_update_product_with_oversized_id_in_path_returns_422_not_500(
    client: TestClient, admin_headers: dict
):
    # 20 位數遠超過 SQLite INTEGER 欄位的 64-bit 範圍——修復前這種輸入會在
    # `sqlite3` 綁定參數時丟出未接住的 `OverflowError`，變成一支 500；修復後
    # `Path(..., le=SQLITE_INT64_MAX)` 把它擋在 app/routers/admin.py 回 422
    # （見 app/schemas.py `SQLITE_INT64_MAX`）。
    resp = client.patch(
        "/api/admin/products/99999999999999999999",
        json={"price": 100},
        headers=admin_headers,
    )
    assert resp.status_code == 422
    assert resp.status_code != 500
