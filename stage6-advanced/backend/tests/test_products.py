"""測試 /api/products*：商品清單（分類篩選＋關鍵字搜尋）與商品詳情，不需要登入。"""

from fastapi.testclient import TestClient


def test_list_products_returns_all_12(client: TestClient):
    resp = client.get("/api/products")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 12
    assert len(body["items"]) == 12


def test_list_products_filter_by_category(client: TestClient):
    resp = client.get("/api/products", params={"category": "beans"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 4
    assert all(item["category"] == "beans" for item in body["items"])


def test_list_products_search_by_keyword(client: TestClient):
    # 「耶加雪菲」同時出現在商品 1（淺焙單品豆）與商品 5（掛耳包）名稱裡，
    # 用更完整的關鍵字才能精準命中單一商品。
    resp = client.get("/api/products", params={"search": "耶加雪菲 淺焙"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == 1


def test_list_products_search_matches_multiple_products(client: TestClient):
    resp = client.get("/api/products", params={"search": "耶加雪菲"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert {item["id"] for item in body["items"]} == {1, 5}


def test_list_products_category_and_search_combined(client: TestClient):
    resp = client.get("/api/products", params={"category": "gear", "search": "壺"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == 7


def test_get_product_by_id(client: TestClient):
    resp = client.get("/api/products/1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == 1
    assert body["price"] == 520
    assert body["stock"] == 25


def test_get_product_low_stock_sample(client: TestClient):
    # id=6 是型錄裡刻意設低庫存的商品，示範「僅剩 N 件」的資料來源
    resp = client.get("/api/products/6")
    assert resp.status_code == 200
    assert resp.json()["stock"] == 3


def test_get_product_out_of_stock_sample(client: TestClient):
    # id=11 是型錄裡刻意設庫存 0 的商品，示範「補貨中」
    resp = client.get("/api/products/11")
    assert resp.status_code == 200
    assert resp.json()["stock"] == 0


def test_get_product_not_found_returns_404(client: TestClient):
    resp = client.get("/api/products/9999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "找不到這個商品"


def test_get_product_with_oversized_id_returns_422_not_500(client: TestClient):
    # 20 位數遠超過 SQLite INTEGER 欄位的 64-bit 範圍——修復前這種輸入會在
    # `sqlite3` 綁定參數時丟出未接住的 `OverflowError`，變成一支 500；
    # 修復後 FastAPI 在還沒碰到資料庫之前，就靠 `Path(..., le=SQLITE_INT64_MAX)`
    # 把它擋成 422（見 app/routers/products.py、app/schemas.py `SQLITE_INT64_MAX`）。
    resp = client.get("/api/products/99999999999999999999")
    assert resp.status_code == 422
    assert resp.status_code != 500
