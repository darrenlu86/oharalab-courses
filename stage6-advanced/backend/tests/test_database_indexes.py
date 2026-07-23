"""
索引存在性檢查——用 SQLite 的 `PRAGMA index_list` 直接查資料庫的中繼資料，
確認 schema.sql 描述的索引真的被建立出來了，不是「SQL 檔案裡有寫，但其實
從沒被跑過」這種帳面上有、實際上沒有的情況。
"""

import sqlite3


def _index_columns(conn: sqlite3.Connection, table: str) -> list[tuple]:
    """回傳 (index_name, [column names]) 的清單，方便逐一比對。"""
    indexes = conn.execute(f"PRAGMA index_list({table})").fetchall()
    result = []
    for index in indexes:
        index_name = index["name"]
        columns = conn.execute(f"PRAGMA index_info({index_name})").fetchall()
        column_names = [col["name"] for col in columns]
        result.append((index_name, column_names))
    return result


def test_orders_user_id_index_exists(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        indexes = _index_columns(conn, "orders")
    finally:
        conn.close()
    assert any(columns == ["user_id"] for _, columns in indexes)


def test_orders_status_index_exists(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        indexes = _index_columns(conn, "orders")
    finally:
        conn.close()
    assert any(columns == ["status"] for _, columns in indexes)


def test_order_items_order_id_index_exists(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        indexes = _index_columns(conn, "order_items")
    finally:
        conn.close()
    assert any(columns == ["order_id"] for _, columns in indexes)


def test_payments_order_id_index_exists(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        indexes = _index_columns(conn, "payments")
    finally:
        conn.close()
    assert any(columns == ["order_id"] for _, columns in indexes)


def test_products_category_is_active_composite_index_exists(db_path):
    """stage6 新增的複合索引——順序必須是 (category, is_active)，見
    schema.sql 的說明（欄位順序要跟最常見的查詢條件順序一致才有效）。"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        indexes = _index_columns(conn, "products")
    finally:
        conn.close()
    assert any(columns == ["category", "is_active"] for _, columns in indexes)
