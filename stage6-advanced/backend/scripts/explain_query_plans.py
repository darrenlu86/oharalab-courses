"""
索引效果實測腳本——`python scripts/explain_query_plans.py`（在 backend/ 目錄下執行，
需要先跑過 `python scripts/init_db.py`，讓資料庫裡有種子商品可以查）。

這支腳本印出來的內容**直接被複製貼進 docs/DATABASE.md**（標明是這支腳本的實際
輸出，不是手打的），做法：對同一份資料庫，先在一份「拿掉 stage6 新索引」的暫存
複本上跑 `EXPLAIN QUERY PLAN`，再對正式（有索引）的資料庫跑一次，兩相對照。
其餘三個索引（orders.user_id / order_items.order_id / payments.order_id）在
stage5 就已經存在（不是這階段新加的），這裡也一併跑一次 `EXPLAIN QUERY PLAN`
確認它們真的有被使用到（SEARCH ... USING INDEX，而不是 SCAN 全表）。
"""

import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

from app.config import get_settings  # noqa: E402


def _print_plan(conn: sqlite3.Connection, label: str, sql: str, params: tuple = ()) -> None:
    print(f"-- {label}")
    print(f"   SQL: {sql}")
    rows = conn.execute(f"EXPLAIN QUERY PLAN {sql}", params).fetchall()
    for row in rows:
        # EXPLAIN QUERY PLAN 回傳欄位：id, parent, notused, detail——教學重點只看
        # 最後一欄 detail（SCAN 還是 SEARCH、有沒有用到 USING INDEX）。
        print(f"   {row[3]}")
    print()


def main() -> None:
    settings = get_settings()
    real_db_path = settings.sqlite_path
    if not real_db_path.exists():
        print(f"找不到資料庫：{real_db_path}，請先執行 python scripts/init_db.py")
        sys.exit(1)

    print("=" * 70)
    print("第一部分：products(category, is_active) 複合索引——加索引前 vs 後")
    print("=" * 70)
    print()

    with tempfile.TemporaryDirectory() as tmp_dir:
        no_index_path = Path(tmp_dir) / "no_index.db"
        shutil.copy(real_db_path, no_index_path)
        no_index_conn = sqlite3.connect(str(no_index_path))
        no_index_conn.execute("DROP INDEX IF EXISTS idx_products_category_active")

        _print_plan(
            no_index_conn,
            "加索引「前」：SELECT * FROM products WHERE category = ? AND is_active = 1",
            "SELECT * FROM products WHERE category = ? AND is_active = 1",
            ("beans",),
        )
        no_index_conn.close()

    real_conn = sqlite3.connect(str(real_db_path))
    real_conn.row_factory = sqlite3.Row
    _print_plan(
        real_conn,
        "加索引「後」：SELECT * FROM products WHERE category = ? AND is_active = 1",
        "SELECT * FROM products WHERE category = ? AND is_active = 1",
        ("beans",),
    )

    print("=" * 70)
    print("第二部分：stage5 已經建過的三個索引——確認實際上真的有被用到")
    print("=" * 70)
    print()

    _print_plan(
        real_conn,
        "orders.user_id：SELECT * FROM orders WHERE user_id = ?",
        "SELECT * FROM orders WHERE user_id = ?",
        (2,),
    )
    _print_plan(
        real_conn,
        "order_items.order_id：SELECT * FROM order_items WHERE order_id = ?",
        "SELECT * FROM order_items WHERE order_id = ?",
        (1,),
    )
    _print_plan(
        real_conn,
        "payments.order_id：SELECT * FROM payments WHERE order_id = ?",
        "SELECT * FROM payments WHERE order_id = ?",
        (1,),
    )

    real_conn.close()


if __name__ == "__main__":
    main()
