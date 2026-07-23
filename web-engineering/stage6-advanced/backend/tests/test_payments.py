"""
測試 /api/payments/mock：stage5 新增的模擬付款流程。

涵蓋：付款成功才扣庫存（跟 test_orders.py「建單不扣庫存」互為對照）、失敗卡號、
失敗後可以重試、已付款訂單再付一次要 409、多品項訂單的原子性、找不到訂單。
"""

from fastapi.testclient import TestClient

FAILING_CARD = "4000000000000002"
SUCCESS_CARD = "4242424242424242"


def _create_order(client: TestClient, headers: dict, product_id: int, quantity: int) -> dict:
    client.post("/api/cart/items", json={"product_id": product_id, "quantity": quantity}, headers=headers)
    resp = client.post(
        "/api/orders",
        json={"recipient_name": "付款測試", "recipient_address": "台北市中山區某路 1 號"},
        headers=headers,
    )
    return resp.json()


def test_payment_without_login_returns_401(client: TestClient):
    resp = client.post(
        "/api/payments/mock", json={"order_id": 1, "card_number": SUCCESS_CARD, "card_holder": "測試"}
    )
    assert resp.status_code == 401


def test_payment_order_not_found_returns_404(client: TestClient, auth_headers: dict):
    resp = client.post(
        "/api/payments/mock",
        json={"order_id": 9999, "card_number": SUCCESS_CARD, "card_holder": "測試"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_payment_success_marks_order_paid_and_decreases_stock(client: TestClient, auth_headers: dict):
    before = client.get("/api/products/1").json()
    assert before["stock"] == 25

    order = _create_order(client, auth_headers, product_id=1, quantity=2)
    assert order["status"] == "pending"

    resp = client.post(
        "/api/payments/mock",
        json={"order_id": order["id"], "card_number": SUCCESS_CARD, "card_holder": "測試"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["payment"]["status"] == "success"
    assert body["payment"]["card_last4"] == "4242"
    assert body["payment"]["amount"] == order["total_amount"]
    assert body["order"]["status"] == "paid"

    # 這裡才是真正扣庫存的時間點（跟 test_orders.py 的「建單不扣庫存」對照）。
    after = client.get("/api/products/1").json()
    assert after["stock"] == 23


def test_payment_failing_card_marks_order_failed_and_keeps_stock(client: TestClient, auth_headers: dict):
    before = client.get("/api/products/1").json()

    order = _create_order(client, auth_headers, product_id=1, quantity=1)

    resp = client.post(
        "/api/payments/mock",
        json={"order_id": order["id"], "card_number": FAILING_CARD, "card_holder": "測試"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["payment"]["status"] == "failed"
    assert body["payment"]["card_last4"] == "0002"
    assert body["order"]["status"] == "failed"

    after = client.get("/api/products/1").json()
    assert after["stock"] == before["stock"]


def test_payment_retry_after_failure_succeeds(client: TestClient, auth_headers: dict):
    order = _create_order(client, auth_headers, product_id=2, quantity=1)

    failed_resp = client.post(
        "/api/payments/mock",
        json={"order_id": order["id"], "card_number": FAILING_CARD, "card_holder": "測試"},
        headers=auth_headers,
    )
    assert failed_resp.json()["order"]["status"] == "failed"

    retry_resp = client.post(
        "/api/payments/mock",
        json={"order_id": order["id"], "card_number": SUCCESS_CARD, "card_holder": "測試"},
        headers=auth_headers,
    )
    assert retry_resp.status_code == 200
    assert retry_resp.json()["order"]["status"] == "paid"


def test_payment_on_already_paid_order_returns_409(client: TestClient, auth_headers: dict):
    order = _create_order(client, auth_headers, product_id=1, quantity=1)
    client.post(
        "/api/payments/mock",
        json={"order_id": order["id"], "card_number": SUCCESS_CARD, "card_holder": "測試"},
        headers=auth_headers,
    )

    resp = client.post(
        "/api/payments/mock",
        json={"order_id": order["id"], "card_number": SUCCESS_CARD, "card_holder": "測試"},
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "這筆訂單已經付款完成"


def test_payment_on_cancelled_order_returns_409(client: TestClient, auth_headers: dict):
    order = _create_order(client, auth_headers, product_id=1, quantity=1)
    client.post(f"/api/orders/{order['id']}/cancel", headers=auth_headers)

    resp = client.post(
        "/api/payments/mock",
        json={"order_id": order["id"], "card_number": SUCCESS_CARD, "card_holder": "測試"},
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "這筆訂單已經取消，無法付款"


def test_payment_multi_item_order_decreases_all_items_stock(client: TestClient, auth_headers: dict):
    client.post("/api/cart/items", json={"product_id": 1, "quantity": 1}, headers=auth_headers)
    client.post("/api/cart/items", json={"product_id": 2, "quantity": 3}, headers=auth_headers)
    order = client.post(
        "/api/orders",
        json={"recipient_name": "多品項", "recipient_address": "台北市中山區某路 2 號"},
        headers=auth_headers,
    ).json()

    resp = client.post(
        "/api/payments/mock",
        json={"order_id": order["id"], "card_number": SUCCESS_CARD, "card_holder": "測試"},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    product1 = client.get("/api/products/1").json()
    product2 = client.get("/api/products/2").json()
    assert product1["stock"] == 24  # 25 - 1
    assert product2["stock"] == 27  # 30 - 3


def test_payment_invalid_card_format_returns_422(client: TestClient, auth_headers: dict):
    order = _create_order(client, auth_headers, product_id=1, quantity=1)
    resp = client.post(
        "/api/payments/mock",
        json={"order_id": order["id"], "card_number": "not-a-card", "card_holder": "測試"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_payment_cannot_pay_other_users_order(client: TestClient, register_and_login):
    headers_a = register_and_login(email="pay-a@example.com")
    headers_b = register_and_login(email="pay-b@example.com")

    order = _create_order(client, headers_a, product_id=1, quantity=1)

    resp = client.post(
        "/api/payments/mock",
        json={"order_id": order["id"], "card_number": SUCCESS_CARD, "card_holder": "測試"},
        headers=headers_b,
    )
    assert resp.status_code == 404
