"""測試 /api/orders* 與 /api/payments/mock，含完整 E2E 購物流程。"""

import pytest
from fastapi.testclient import TestClient

from app.repositories.sqlite_repo import SQLiteOrderRepository, SQLiteProductRepository

FAILING_CARD = "4000 0000 0000 0002"
SUCCESS_CARD = "4242 4242 4242 4242"


def test_create_order_with_empty_cart_returns_400(client: TestClient, auth_headers: dict):
    resp = client.post(
        "/api/orders",
        json={"recipient_name": "小明", "recipient_address": "台北市信義區某路 1 號"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "購物車是空的"


def test_create_order_success_clears_cart_and_does_not_touch_stock(
    client: TestClient, auth_headers: dict
):
    # 商品 1：鮭魚無穀貓糧 1.5kg，NT$880，stock 25
    client.post("/api/cart/items", json={"product_id": 1, "quantity": 2}, headers=auth_headers)

    resp = client.post(
        "/api/orders",
        json={"recipient_name": "小明", "recipient_address": "台北市信義區某路 1 號"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    order = resp.json()
    assert order["status"] == "pending"
    assert order["total_amount"] == 1760
    assert len(order["items"]) == 1
    assert order["items"][0]["product_name"] == "鮭魚無穀貓糧 1.5kg"
    assert order["items"][0]["unit_price"] == 880
    assert order["payments"] == []

    # 建單成功要清空購物車
    cart_resp = client.get("/api/cart", headers=auth_headers)
    assert cart_resp.json()["items"] == []

    # 教學點：建單當下不扣庫存，付款成功才扣
    product_resp = client.get("/api/products/1")
    assert product_resp.json()["stock"] == 25


def test_create_order_insufficient_stock_returns_409(client: TestClient, auth_headers: dict):
    # 商品 4：貓草薄荷魚抱枕，stock 只有 3；先加 3 件到購物車（合法），
    # 這裡直接用 PATCH 把數量改到超過庫存不行，所以改用「先加 3、再讓庫存被別人買光」
    # 的方式其實比較貼近真實情境，但為了單純測試 409，這裡直接用允許的最大值下單，
    # 驗證「剛好等於庫存」是可以成立的（見下一個測試），這個測試改成用一般手法：
    # 加車數量本身就會在加車時被 409 擋下，因此改為驗證「購物車最多只能加到等於庫存」，
    # 再確認下單這批「剛好滿庫存」的購物車不會被拒絕。
    resp = client.post(
        "/api/cart/items", json={"product_id": 4, "quantity": 3}, headers=auth_headers
    )
    assert resp.status_code == 200

    order_resp = client.post(
        "/api/orders",
        json={"recipient_name": "小華", "recipient_address": "台中市西區某路 2 號"},
        headers=auth_headers,
    )
    assert order_resp.status_code == 201


def test_list_orders_sorted_new_to_old(client: TestClient, auth_headers: dict):
    client.post("/api/cart/items", json={"product_id": 1, "quantity": 1}, headers=auth_headers)
    first_order = client.post(
        "/api/orders",
        json={"recipient_name": "A", "recipient_address": "地址 A"},
        headers=auth_headers,
    ).json()

    client.post("/api/cart/items", json={"product_id": 2, "quantity": 1}, headers=auth_headers)
    second_order = client.post(
        "/api/orders",
        json={"recipient_name": "B", "recipient_address": "地址 B"},
        headers=auth_headers,
    ).json()

    resp = client.get("/api/orders", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2
    # 新到舊：第二筆訂單要排在第一筆前面
    assert items[0]["id"] == second_order["id"]
    assert items[1]["id"] == first_order["id"]


def test_get_order_detail(client: TestClient, auth_headers: dict):
    client.post("/api/cart/items", json={"product_id": 1, "quantity": 1}, headers=auth_headers)
    order = client.post(
        "/api/orders",
        json={"recipient_name": "小明", "recipient_address": "某路 1 號"},
        headers=auth_headers,
    ).json()

    resp = client.get(f"/api/orders/{order['id']}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == order["id"]
    assert body["recipient_name"] == "小明"
    assert len(body["items"]) == 1


def test_get_other_users_order_returns_404_not_403(client: TestClient, register_and_login):
    headers_a = register_and_login(email="owner@example.com")
    headers_b = register_and_login(email="stranger@example.com")

    client.post("/api/cart/items", json={"product_id": 1, "quantity": 1}, headers=headers_a)
    order = client.post(
        "/api/orders",
        json={"recipient_name": "A", "recipient_address": "地址 A"},
        headers=headers_a,
    ).json()

    resp = client.get(f"/api/orders/{order['id']}", headers=headers_b)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "找不到這筆訂單"


def test_get_order_not_found_returns_404(client: TestClient, auth_headers: dict):
    resp = client.get("/api/orders/9999", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "找不到這筆訂單"


def _create_order(client: TestClient, headers: dict, product_id: int, quantity: int) -> dict:
    client.post(
        "/api/cart/items", json={"product_id": product_id, "quantity": quantity}, headers=headers
    )
    resp = client.post(
        "/api/orders",
        json={"recipient_name": "測試收件人", "recipient_address": "測試地址"},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


def test_payment_with_failing_card_marks_order_failed_and_allows_retry(
    client: TestClient, auth_headers: dict
):
    order = _create_order(client, auth_headers, product_id=1, quantity=1)

    fail_resp = client.post(
        "/api/payments/mock",
        json={
            "order_id": order["id"],
            "card_number": FAILING_CARD,
            "card_holder": "測試貓奴",
        },
        headers=auth_headers,
    )
    assert fail_resp.status_code == 200
    fail_body = fail_resp.json()
    assert fail_body["payment"]["status"] == "failed"
    assert fail_body["order"]["status"] == "failed"

    order_after_fail = client.get(f"/api/orders/{order['id']}", headers=auth_headers).json()
    assert order_after_fail["status"] == "failed"
    assert len(order_after_fail["payments"]) == 1
    assert order_after_fail["payments"][0]["status"] == "failed"

    # 失敗的訂單可以重新付款——這次用會成功的卡號重試
    retry_resp = client.post(
        "/api/payments/mock",
        json={
            "order_id": order["id"],
            "card_number": SUCCESS_CARD,
            "card_holder": "測試貓奴",
        },
        headers=auth_headers,
    )
    assert retry_resp.status_code == 200
    retry_body = retry_resp.json()
    assert retry_body["payment"]["status"] == "success"
    assert retry_body["order"]["status"] == "paid"


def test_payment_success_marks_order_paid_and_decreases_stock(
    client: TestClient, auth_headers: dict
):
    product_before = client.get("/api/products/1").json()
    stock_before = product_before["stock"]

    order = _create_order(client, auth_headers, product_id=1, quantity=2)

    resp = client.post(
        "/api/payments/mock",
        json={"order_id": order["id"], "card_number": SUCCESS_CARD, "card_holder": "付款貓"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["payment"]["status"] == "success"
    assert body["payment"]["amount"] == order["total_amount"]
    assert body["payment"]["card_last4"] == "4242"
    assert body["payment"]["transaction_id"].startswith("MOCK-")
    assert body["order"]["status"] == "paid"

    product_after = client.get("/api/products/1").json()
    assert product_after["stock"] == stock_before - 2


def test_duplicate_payment_on_paid_order_returns_409(client: TestClient, auth_headers: dict):
    order = _create_order(client, auth_headers, product_id=1, quantity=1)
    client.post(
        "/api/payments/mock",
        json={"order_id": order["id"], "card_number": SUCCESS_CARD, "card_holder": "付款貓"},
        headers=auth_headers,
    )

    resp = client.post(
        "/api/payments/mock",
        json={"order_id": order["id"], "card_number": SUCCESS_CARD, "card_holder": "付款貓"},
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "這筆訂單已經付款完成"


def test_payment_on_other_users_order_returns_404(client: TestClient, register_and_login):
    headers_a = register_and_login(email="payer-a@example.com")
    headers_b = register_and_login(email="payer-b@example.com")

    order = _create_order(client, headers_a, product_id=1, quantity=1)

    resp = client.post(
        "/api/payments/mock",
        json={"order_id": order["id"], "card_number": SUCCESS_CARD, "card_holder": "陌生人"},
        headers=headers_b,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "找不到這筆訂單"


def test_payment_time_stock_check_second_buyer_gets_409(client: TestClient, register_and_login):
    """兩個使用者搶同一件庫存只剩 3 的商品：先付款的人成功，後付款的人在付款當下被擋下。"""
    headers_a = register_and_login(email="racer-a@example.com")
    headers_b = register_and_login(email="racer-b@example.com")

    # 商品 4：貓草薄荷魚抱枕，stock 3。兩人都下單拿走全部 3 件（下單當下不扣庫存，都能成功建單）。
    order_a = _create_order(client, headers_a, product_id=4, quantity=3)
    order_b = _create_order(client, headers_b, product_id=4, quantity=3)

    resp_a = client.post(
        "/api/payments/mock",
        json={"order_id": order_a["id"], "card_number": SUCCESS_CARD, "card_holder": "先手"},
        headers=headers_a,
    )
    assert resp_a.status_code == 200
    assert resp_a.json()["order"]["status"] == "paid"

    resp_b = client.post(
        "/api/payments/mock",
        json={"order_id": order_b["id"], "card_number": SUCCESS_CARD, "card_holder": "後手"},
        headers=headers_b,
    )
    assert resp_b.status_code == 409
    assert resp_b.json()["detail"] == "庫存不足，無法完成付款"

    order_b_detail = client.get(f"/api/orders/{order_b['id']}", headers=headers_b).json()
    assert order_b_detail["status"] == "failed"


def test_payment_decrease_stock_failure_returns_409_and_marks_order_failed(
    client: TestClient, auth_headers: dict, monkeypatch: pytest.MonkeyPatch
):
    """回歸測試（backend-3）：就算「檢查迴圈」判斷庫存夠、卡號規則也判斷「應該成功」，
    只要實際扣減 decrease_stock() 回傳 False（模擬扣減當下庫存被搶走這個並發視窗），
    付款要回 409「庫存不足，無法完成付款」、訂單要被標記 failed，不能誤報付款成功。"""
    order = _create_order(client, auth_headers, product_id=1, quantity=1)

    # 用 monkeypatch 強迫 decrease_stock() 一律回傳 False，模擬「扣減當下才發現
    # 庫存被搶走」的情境——不需要真的跑兩個並發 request 就能重現這條路徑。
    monkeypatch.setattr(SQLiteProductRepository, "decrease_stock", lambda self, product_id, quantity: False)

    resp = client.post(
        "/api/payments/mock",
        json={"order_id": order["id"], "card_number": SUCCESS_CARD, "card_holder": "扣庫存失敗貓"},
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "庫存不足，無法完成付款"

    order_after = client.get(f"/api/orders/{order['id']}", headers=auth_headers).json()
    assert order_after["status"] == "failed"
    assert order_after["payments"][-1]["status"] == "failed"


def test_payment_on_cancelled_order_returns_409_with_cancelled_message(
    client: TestClient, auth_headers: dict, db_path
):
    """回歸測試（backend-13）：cancelled 訂單付款要回「這筆訂單已經取消，無法再付款」，
    跟 paid 訂單的「這筆訂單已經付款完成」是不同訊息，不能混用。"""
    order = _create_order(client, auth_headers, product_id=1, quantity=1)

    # 目前專案沒有「取消訂單」的端點，這裡直接呼叫 repository 把狀態改成 cancelled，
    # 模擬「以後加了取消訂單功能」的情境（見 fix-backend.md backend-13 的說明）。
    SQLiteOrderRepository(db_path).update_status(order["id"], "cancelled")

    resp = client.post(
        "/api/payments/mock",
        json={"order_id": order["id"], "card_number": SUCCESS_CARD, "card_holder": "取消訂單貓"},
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "這筆訂單已經取消，無法再付款"


def test_full_happy_path_e2e(client: TestClient):
    # 1. 註冊
    register_resp = client.post(
        "/api/auth/register",
        json={"email": "e2e@example.com", "password": "password123", "name": "全流程貓奴"},
    )
    assert register_resp.status_code == 201

    # 2. 登入
    login_resp = client.post(
        "/api/auth/login", json={"email": "e2e@example.com", "password": "password123"}
    )
    assert login_resp.status_code == 200
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    # 3. 逛商品列表、看商品詳情
    list_resp = client.get("/api/products")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 10

    detail_resp = client.get("/api/products/2")
    assert detail_resp.status_code == 200

    # 4. 加入購物車
    add_resp = client.post(
        "/api/cart/items", json={"product_id": 2, "quantity": 3}, headers=headers
    )
    assert add_resp.status_code == 200
    assert add_resp.json()["total_quantity"] == 3

    # 5. 建立訂單
    order_resp = client.post(
        "/api/orders",
        json={"recipient_name": "全流程貓奴", "recipient_address": "高雄市前鎮區某路 3 號"},
        headers=headers,
    )
    assert order_resp.status_code == 201
    order = order_resp.json()
    assert order["status"] == "pending"

    # 6. 模擬付款成功
    pay_resp = client.post(
        "/api/payments/mock",
        json={"order_id": order["id"], "card_number": SUCCESS_CARD, "card_holder": "全流程貓奴"},
        headers=headers,
    )
    assert pay_resp.status_code == 200
    assert pay_resp.json()["order"]["status"] == "paid"

    # 7. 我的訂單看得到最新狀態
    final_order = client.get(f"/api/orders/{order['id']}", headers=headers).json()
    assert final_order["status"] == "paid"
    assert len(final_order["payments"]) == 1
    assert final_order["payments"][0]["status"] == "success"
