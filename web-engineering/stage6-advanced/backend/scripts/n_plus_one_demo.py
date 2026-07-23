"""
N+1 查詢次數實測腳本——`python scripts/n_plus_one_demo.py`（在 backend/ 目錄下
執行，需要先跑過 `python scripts/init_db.py`）。這支腳本的輸出直接被複製貼進
docs/DATABASE.md，做法：在種子資料庫既有的 7 筆示範訂單之上，各自呼叫舊寫法
`list_all_orders_naive_n_plus_one()` 與新寫法 `list_all_orders()`，用
`sqlite3.Connection.set_trace_callback()`（詳細原理見
tests/test_n_plus_one_demo.py 的說明）實際數出兩者各自對資料庫發出了幾次查詢。
"""

import sqlite3
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

from app.config import get_settings  # noqa: E402
from app.db.database import list_all_orders, list_all_orders_naive_n_plus_one  # noqa: E402


def _count_queries(conn: sqlite3.Connection, fn) -> tuple[int, int]:
    counter = {"n": 0}
    conn.set_trace_callback(lambda sql: counter.__setitem__("n", counter["n"] + 1))
    try:
        result = fn(conn)
    finally:
        conn.set_trace_callback(None)
    return counter["n"], len(result)


def main() -> None:
    settings = get_settings()
    if not settings.sqlite_path.exists():
        print(f"找不到資料庫：{settings.sqlite_path}，請先執行 python scripts/init_db.py")
        sys.exit(1)

    conn = sqlite3.connect(str(settings.sqlite_path))
    conn.row_factory = sqlite3.Row

    naive_queries, naive_order_count = _count_queries(conn, list_all_orders_naive_n_plus_one)
    optimized_queries, optimized_order_count = _count_queries(conn, list_all_orders)

    conn.close()

    assert naive_order_count == optimized_order_count, "兩個函式回傳的訂單筆數應該相同"

    print(f"資料庫目前有 {naive_order_count} 筆訂單。\n")
    print(f"stage5 舊寫法 list_all_orders_naive_n_plus_one()：實際發出 {naive_queries} 次 SQL 查詢")
    print(f"  （預期：1 次查訂單本體 + {naive_order_count} 次逐單查品項 = {1 + naive_order_count} 次）")
    print(f"stage6 新寫法 list_all_orders()：實際發出 {optimized_queries} 次 SQL 查詢")
    print(f"  （預期：1 次，不管訂單筆數是多少）")
    print()
    print(f"查詢次數從 {naive_queries} 次降到 {optimized_queries} 次"
          f"（訂單筆數越多，舊寫法的查詢次數會跟著線性增加，新寫法永遠是 1 次）。")


if __name__ == "__main__":
    main()
