"""測試 /api/cart*：購物車增改刪查，全部端點都需要登入。"""

from fastapi.testclient import TestClient


def test_get_cart_without_login_returns_401(client: TestClient):
    resp = client.get("/api/cart")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "請先登入"


def test_get_empty_cart(client: TestClient, auth_headers: dict):
    resp = client.get("/api/cart", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"items": [], "total_amount": 0, "total_quantity": 0}


def test_add_item_to_cart(client: TestClient, auth_headers: dict):
    # 商品 1：鮭魚無穀貓糧 1.5kg，NT$880，stock 25
    resp = client.post(
        "/api/cart/items", json={"product_id": 1, "quantity": 2}, headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["product_id"] == 1
    assert item["quantity"] == 2
    assert item["price"] == 880
    assert item["subtotal"] == 1760
    assert body["total_amount"] == 1760
    assert body["total_quantity"] == 2


def test_add_same_item_twice_accumulates_quantity(client: TestClient, auth_headers: dict):
    client.post("/api/cart/items", json={"product_id": 1, "quantity": 2}, headers=auth_headers)
    resp = client.post(
        "/api/cart/items", json={"product_id": 1, "quantity": 3}, headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["quantity"] == 5


def test_add_item_product_not_found_returns_404(client: TestClient, auth_headers: dict):
    resp = client.post(
        "/api/cart/items", json={"product_id": 9999, "quantity": 1}, headers=auth_headers
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "找不到這個商品"


def test_add_item_exceeding_stock_returns_409(client: TestClient, auth_headers: dict):
    # 商品 4：貓草薄荷魚抱枕，stock 只有 3
    resp = client.post(
        "/api/cart/items", json={"product_id": 4, "quantity": 4}, headers=auth_headers
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "庫存不足，目前只剩 3 件"


def test_update_item_quantity(client: TestClient, auth_headers: dict):
    client.post("/api/cart/items", json={"product_id": 1, "quantity": 2}, headers=auth_headers)
    resp = client.patch(
        "/api/cart/items/1", json={"quantity": 10}, headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"][0]["quantity"] == 10
    assert body["items"][0]["subtotal"] == 8800


def test_update_item_quantity_exceeding_stock_returns_409(client: TestClient, auth_headers: dict):
    client.post("/api/cart/items", json={"product_id": 4, "quantity": 1}, headers=auth_headers)
    resp = client.patch(
        "/api/cart/items/4", json={"quantity": 100}, headers=auth_headers
    )
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
