"""測試 /api/cart*：購物車增改刪查，全部端點都需要登入。"""

from fastapi.testclient import TestClient


def test_get_cart_without_login_returns_401(client: TestClient):
    resp = client.get("/api/cart")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "請先登入"


def test_get_empty_cart(client: TestClient, auth_headers: dict):
    resp = client.get("/api/cart", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total_amount": 0, "total_quantity": 0}


def test_add_item_to_cart(client: TestClient, auth_headers: dict):
    # 商品 1：耶加雪菲 淺焙單品豆 250g，NT$520，stock 25
    resp = client.post("/api/cart/items", json={"product_id": 1, "quantity": 2}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["product_id"] == 1
    assert item["quantity"] == 2
    assert item["price"] == 520
    assert item["subtotal"] == 1040
    assert body["total_amount"] == 1040
    assert body["total_quantity"] == 2


def test_add_item_without_login_returns_401(client: TestClient):
    resp = client.post("/api/cart/items", json={"product_id": 1, "quantity": 1})
    assert resp.status_code == 401


def test_add_same_item_twice_accumulates_quantity(client: TestClient, auth_headers: dict):
    client.post("/api/cart/items", json={"product_id": 1, "quantity": 2}, headers=auth_headers)
    resp = client.post("/api/cart/items", json={"product_id": 1, "quantity": 3}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["quantity"] == 5


def test_add_item_product_not_found_returns_404(client: TestClient, auth_headers: dict):
    resp = client.post("/api/cart/items", json={"product_id": 9999, "quantity": 1}, headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "找不到這個商品"


def test_add_item_exceeding_stock_returns_409(client: TestClient, auth_headers: dict):
    # 商品 6：深焙醇厚掛耳包 10 入，stock 只有 3
    resp = client.post("/api/cart/items", json={"product_id": 6, "quantity": 4}, headers=auth_headers)
    assert resp.status_code == 409
    assert resp.json()["detail"] == "庫存不足，目前只剩 3 件"


def test_add_item_accumulating_exceeds_stock_returns_409(client: TestClient, auth_headers: dict):
    client.post("/api/cart/items", json={"product_id": 6, "quantity": 2}, headers=auth_headers)
    resp = client.post("/api/cart/items", json={"product_id": 6, "quantity": 2}, headers=auth_headers)
    assert resp.status_code == 409
    assert resp.json()["detail"] == "庫存不足，目前只剩 3 件"


def test_update_item_quantity(client: TestClient, auth_headers: dict):
    client.post("/api/cart/items", json={"product_id": 1, "quantity": 2}, headers=auth_headers)
    resp = client.patch("/api/cart/items/1", json={"quantity": 10}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"][0]["quantity"] == 10
    assert body["items"][0]["subtotal"] == 5200


def test_update_item_quantity_exceeding_stock_returns_409(client: TestClient, auth_headers: dict):
    client.post("/api/cart/items", json={"product_id": 6, "quantity": 1}, headers=auth_headers)
    resp = client.patch("/api/cart/items/6", json={"quantity": 100}, headers=auth_headers)
    assert resp.status_code == 409
    assert resp.json()["detail"] == "庫存不足，目前只剩 3 件"


def test_update_item_not_in_cart_returns_404(client: TestClient, auth_headers: dict):
    resp = client.patch("/api/cart/items/1", json={"quantity": 1}, headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "購物車裡沒有這個商品"


def test_remove_item(client: TestClient, auth_headers: dict):
    client.post("/api/cart/items", json={"product_id": 1, "quantity": 1}, headers=auth_headers)
    client.post("/api/cart/items", json={"product_id": 2, "quantity": 1}, headers=auth_headers)

    resp = client.delete("/api/cart/items/1", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["product_id"] == 2


def test_remove_item_not_in_cart_returns_404(client: TestClient, auth_headers: dict):
    resp = client.delete("/api/cart/items/1", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "購物車裡沒有這個商品"


def test_cart_is_isolated_per_user(client: TestClient, register_and_login):
    headers_a = register_and_login(email="user-a@example.com")
    headers_b = register_and_login(email="user-b@example.com")

    client.post("/api/cart/items", json={"product_id": 1, "quantity": 1}, headers=headers_a)

    resp_b = client.get("/api/cart", headers=headers_b)
    assert resp_b.json()["items"] == []


def test_add_item_with_oversized_product_id_returns_422_not_500(client: TestClient, auth_headers: dict):
    # 20 位數遠超過 SQLite INTEGER 欄位的 64-bit 範圍——修復前這種輸入會在
    # `sqlite3` 綁定參數時丟出未接住的 `OverflowError`，變成一支 500；修復後
    # pydantic 在還沒碰到資料庫之前，就靠 `CartItemIn.product_id` 的
    # `Field(..., le=SQLITE_INT64_MAX)` 把它擋成 422（見 app/schemas.py）。
    resp = client.post(
        "/api/cart/items",
        json={"product_id": 99999999999999999999, "quantity": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert resp.status_code != 500


def test_update_item_with_oversized_product_id_in_path_returns_422_not_500(
    client: TestClient, auth_headers: dict
):
    # 這次是路徑參數（不是 body 欄位）超界——擋在 app/routers/cart.py 的
    # `Path(..., le=SQLITE_INT64_MAX)`，同樣的道理，回 422 而不是 500。
    resp = client.patch(
        "/api/cart/items/99999999999999999999", json={"quantity": 1}, headers=auth_headers
    )
    assert resp.status_code == 422
    assert resp.status_code != 500
