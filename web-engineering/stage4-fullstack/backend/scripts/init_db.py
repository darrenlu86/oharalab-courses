"""
資料庫初始化腳本——用法：`python scripts/init_db.py`（要在 backend/ 目錄下執行）。

負責什麼：建立 SQLite 資料表（app/db/schema.sql）+ 匯入 12 筆種子商品資料
（app/db/seed_products.json，與 master 型錄逐筆一致，含 id）。

防呆設計（跟 meowshop 同一套原則，理由不重複展開）：這支腳本很可能被重複執行——
如果每次都無條件砍掉重建，一旦資料庫裡已經有你自己測出來的帳號、訂單，會在沒有
任何警告的情況下整個消失，這是不可逆的操作。所以預設行為是「資料庫檔案已存在
就跳過、印出提示」，只有明確加上 `--reset` 旗標才會真的刪除重建。
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# 讓這支腳本不管從哪裡執行，都能正確 import 到 app 這個套件。
_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

from app.config import get_settings  # noqa: E402  (需要先調整 sys.path 才能 import)
from app.db.database import init_schema  # noqa: E402

SEED_PATH = _BACKEND_DIR / "app" / "db" / "seed_products.json"


def _load_seed_products() -> list[dict]:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="BrewGo 資料庫初始化腳本")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="刪除現有 SQLite 資料庫並重建。注意：這是不可逆的操作，會清空所有既有資料。",
    )
    args = parser.parse_args()

    settings = get_settings()
    db_path = settings.sqlite_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db_exists = db_path.exists()

    if db_exists and not args.reset:
        print(f"資料庫已經存在：{db_path}")
        print("為了避免不小心刪掉既有資料，這次不會重複建立。")
        print("如果你確定要清空重建，請加上 --reset 參數再跑一次：")
        print("  python scripts/init_db.py --reset")
        return

    if db_exists and args.reset:
        print(f"[--reset] 刪除現有資料庫：{db_path}")
        db_path.unlink()

    print(f"建立資料表於：{db_path}")
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        init_schema(conn)

        cursor = conn.execute("SELECT COUNT(*) FROM products")
        existing_count = cursor.fetchone()[0]
        if existing_count > 0:
            print(f"products 資料表已有 {existing_count} 筆資料，跳過種子資料匯入。")
        else:
            seed_products = _load_seed_products()
            for product in seed_products:
                conn.execute(
                    """
                    INSERT INTO products (id, name, description, price, stock, category, image_url)
                    VALUES (:id, :name, :description, :price, :stock, :category, :image_url)
                    """,
                    product,
                )
            conn.commit()
            print(f"已匯入 {len(seed_products)} 筆種子商品資料。")
    finally:
        conn.close()

    print("SQLite 資料庫初始化完成！")


if __name__ == "__main__":
    main()
