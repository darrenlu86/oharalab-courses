"""
用真的計數方式證明「N+1 修復」：實際去數 `list_all_orders_naive_n_plus_one()`
（stage5 舊寫法，保留在 app/db/database.py 純供對照）跟 `list_all_orders()`
（stage6 新寫法）各自對 SQLite 連線發出了幾次 `execute()`，不是憑印象宣稱
「應該有變快」。

計數方式一開始試過 monkeypatch `sqlite3.Connection.execute`，實測直接失敗——
`sqlite3.Connection` 是 C 實作的內建型別，Python 不允許幫它的方法重新賦值
（`TypeError: cannot set 'execute' attribute of immutable type`，這是實測
踩到的錯誤，不是憑空猜的）。改用 `sqlite3.Connection.set_trace_callback()`
這個官方就是為了這種用途設計的介面：每執行一句 SQL，SQLite 都會呼叫一次
你註冊的 callback，函式本身完全不需要知道；用它來數「這段程式碼實際對資料庫
發出了幾次查詢」，比監控 `execute()` 呼叫次數更準確、更貼近底層真實行為。
"""

import sqlite3

from fastapi.testclient import TestClient

from app.db.database import list_all_orders, list_all_orders_naive_n_plus_one


def _create_orders(client: TestClient, headers: dict, count: int) -> None:
    for _ in range(count):
        client.post("/api/cart/items", json={"product_id": 1, "quantity": 1}, headers=headers)
        client.post(
            "/api/orders",
            json={"recipient_name": "N+1 測試", "recipient_address": "台北市信義區某路 1 號"},
            headers=headers,
        )


def _count_queries(conn: sqlite3.Connection, fn, *args, **kwargs) -> int:
    counter = {"n": 0}
    conn.set_trace_callback(lambda sql: counter.__setitem__("n", counter["n"] + 1))
    try:
        fn(conn, *args, **kwargs)
    finally:
        conn.set_trace_callback(None)
    return counter["n"]


def test_naive_version_issues_one_query_per_order_plus_one(
    client: TestClient, auth_headers: dict, db_path
):
    """驗證 N+1 現象本身真的存在：N 筆訂單應該對應到 1 + N 次查詢。"""
    order_count = 5
    _create_orders(client, auth_headers, order_count)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        query_count = _count_queries(conn, list_all_orders_naive_n_plus_one)
    finally:
        conn.close()

    # 至少要有「查訂單本體那 1 次」加上「每筆訂單各自查一次品項」——
    # 用 >= 而不是 == 是因為資料庫裡可能還有種子資料以外、其他測試殘留的訂單
    # （每個測試各自有獨立的暫存資料庫，這裡其實不會有殘留，但用 >= 更保守）。
    assert query_count >= 1 + order_count


def test_optimized_version_issues_exactly_one_query_regardless_of_order_count(
    client: TestClient, auth_headers: dict, db_path
):
    """驗證優化後的版本，不管有幾筆訂單，永遠只發 1 次 SQL 查詢。"""
    order_count = 5
    _create_orders(client, auth_headers, order_count)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        query_count = _count_queries(conn, list_all_orders)
    finally:
        conn.close()

    assert query_count == 1


def test_naive_and_optimized_versions_return_the_same_data(
    client: TestClient, auth_headers: dict, db_path
):
    """優化不能改變行為——兩個函式對同一份資料，回傳的內容要一模一樣（除了
    Python dict 的 key 順序，用排序後比較，避免因為順序不同誤判成不相等）。"""
    _create_orders(client, auth_headers, 3)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        naive_result = list_all_orders_naive_n_plus_one(conn)
        optimized_result = list_all_orders(conn)
    finally:
        conn.close()

    def _item_shape(item: dict) -> tuple:
        # 舊寫法（`SELECT *`）的 items 每一列多帶了 order_items 表自己的
        # `id` / `order_id` 兩個欄位，新寫法只挑 AdminOrderOut 真正需要的
        # 四個欄位——這是兩個函式故意存在的介面差異（新寫法更貼近 schema），
        # 這裡只比較兩者共通、真正代表「訂單內容」的四個欄位。
        return (item["product_id"], item["product_name"], item["unit_price"], item["quantity"])

    assert len(naive_result) == len(optimized_result)
    naive_by_id = {order["id"]: order for order in naive_result}
    optimized_by_id = {order["id"]: order for order in optimized_result}
    assert set(naive_by_id) == set(optimized_by_id)
    for order_id in naive_by_id:
        naive_items = sorted(_item_shape(item) for item in naive_by_id[order_id]["items"])
        optimized_items = sorted(_item_shape(item) for item in optimized_by_id[order_id]["items"])
        assert naive_items == optimized_items
        assert naive_by_id[order_id]["total_amount"] == optimized_by_id[order_id]["total_amount"]
