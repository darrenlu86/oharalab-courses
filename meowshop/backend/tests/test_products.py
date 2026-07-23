"""測試 /api/products*：商品清單（分類/搜尋）與商品詳情。"""

from fastapi.testclient import TestClient


def test_list_products_returns_all_seed_data(client: TestClient):
    resp = client.get("/api/products")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 10
    assert len(body["items"]) == 10
    first = body["items"][0]
    # 確認金額是整數、is_active 是布林值——教學點：金額不用浮點數
    assert isinstance(first["price"], int)
    assert isinstance(first["is_active"], bool)


def test_list_products_filter_by_category(client: TestClient):
    resp = client.get("/api/products", params={"category": "toy"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3  # 逗貓棒、貓草薄荷魚抱枕、智能滾動逗貓球
    assert all(item["category"] == "toy" for item in body["items"])


def test_list_products_search_by_name(client: TestClient):
    resp = client.get("/api/products", params={"search": "鮭魚"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert "鮭魚" in body["items"][0]["name"]


def test_list_products_search_no_match_returns_empty(client: TestClient):
    resp = client.get("/api/products", params={"search": "恐龍"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_get_product_detail(client: TestClient):
    resp = client.get("/api/products/1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == 1
    assert body["name"] == "鮭魚無穀貓糧 1.5kg"
    assert body["price"] == 880
    assert body["stock"] == 25


def test_get_product_out_of_stock_still_visible(client: TestClient):
    # 第 9 筆商品 stock=0（補貨中），但 is_active 還是 true，商品頁應該還是看得到。
    resp = client.get("/api/products/9")
    assert resp.status_code == 200
    body = resp.json()
    assert body["stock"] == 0
    assert body["is_active"] is True


def test_get_product_not_found_returns_404(client: TestClient):
    resp = client.get("/api/products/9999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "找不到這個商品"
