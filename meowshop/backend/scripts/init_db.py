"""
資料庫初始化腳本——用法：`python scripts/init_db.py`（要在 backend/ 目錄下執行）。

負責什麼：
- `DB_BACKEND=sqlite`（預設）：建立 SQLite 資料表 + 匯入 10 筆種子商品資料。
- `DB_BACKEND=supabase`：印出操作指引（請到 Supabase SQL Editor 手動執行
  `supabase_schema.sql`），資料表確認建好之後，改由這支腳本透過 supabase-py
  幫你匯入種子商品資料。

關鍵設計「為什麼」——防呆機制：
這支腳本很可能被學員重複執行好幾次（照著教學文件的步驟走，一不小心多按一次
Enter 是很常見的事）。如果每次執行都無條件砍掉重建資料庫，一旦資料庫裡已經有
使用者自己測試出來的帳號、訂單等真實資料，會在完全沒有預警的情況下被整個刪除
——這是不可逆的操作。所以這裡的預設行為是「資料庫已經存在就跳過、印出提示」，
只有學員自己明確加上 `--reset` 旗標，才會真的刪除重建。這是「破壞性操作要先
讓人確認」這個原則，具體落實到腳本層級的寫法。

為什麼 `DB_BACKEND=supabase` 時不自動幫你跑建表 SQL：建表（DDL）是會影響
「正式」雲端資料庫結構的操作，風險比在本機建一個 SQLite 檔案高得多；
讓使用者自己到 Supabase 後台的 SQL Editor 貼上、親眼看過再執行，比腳本自動
幫你跑更安全，也更符合「結構性變更要讓人看過」的原則。seed 資料匯入則相對
低風險（只是新增幾筆商品），所以這部分可以由腳本透過 supabase-py 自動處理。
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

SQLITE_SCHEMA_PATH = _BACKEND_DIR / "app" / "db" / "sqlite_schema.sql"
SEED_PATH = _BACKEND_DIR / "app" / "db" / "seed_products.json"


def _load_seed_products() -> list[dict]:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def init_sqlite(reset: bool) -> None:
    settings = get_settings()
    db_path = settings.sqlite_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db_exists = db_path.exists()

    if db_exists and not reset:
        # 注意：這裡「先檢查、再決定要不要動手」，是本腳本最重要的防呆設計，
        # 詳細理由見檔案頂端的 docstring。
        print(f"資料庫已經存在：{db_path}")
        print("為了避免不小心刪掉既有資料，這次不會重複建立。")
        print("如果你確定要清空重建，請加上 --reset 參數再跑一次：")
        print("  python scripts/init_db.py --reset")
        return

    if db_exists and reset:
        print(f"[--reset] 刪除現有資料庫：{db_path}")
        db_path.unlink()

    print(f"建立資料表於：{db_path}")
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        schema_sql = SQLITE_SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(schema_sql)
        conn.commit()

        cursor = conn.execute("SELECT COUNT(*) FROM products")
        existing_count = cursor.fetchone()[0]
        if existing_count > 0:
            # 就算資料庫檔案是新建的，這裡還是多一層保險：萬一 schema 是套用在
            # 已經有資料的檔案上（例如手動指定了別的 SQLITE_PATH），也不會重複塞種子資料。
            print(f"products 資料表已有 {existing_count} 筆資料，跳過種子資料匯入。")
        else:
            seed_products = _load_seed_products()
            for product in seed_products:
                conn.execute(
                    """
                    INSERT INTO products
                        (name, description, price, stock, category, image_url, is_active)
                    VALUES
                        (:name, :description, :price, :stock, :category, :image_url, :is_active)
                    """,
                    product,
                )
            conn.commit()
            print(f"已匯入 {len(seed_products)} 筆種子商品資料。")
    finally:
        conn.close()

    print("SQLite 資料庫初始化完成！")


def init_supabase() -> None:
    settings = get_settings()
    print("=" * 60)
    print("DB_BACKEND=supabase：本腳本不會自動對 Supabase 執行建表 SQL。")
    print()
    print("請依照以下步驟操作：")
    print("  1. 打開你的 Supabase 專案 → SQL Editor")
    print("  2. 貼上並執行 backend/app/db/supabase_schema.sql 的完整內容")
    print("  3. 確認 backend/.env 已經設定好 SUPABASE_URL / SUPABASE_KEY")
    print("  4. 重新執行這支腳本（python scripts/init_db.py），")
    print("     這次會改成幫你把種子商品資料匯入 Supabase")
    print("=" * 60)

    if not settings.supabase_url or not settings.supabase_key:
        print("尚未偵測到 SUPABASE_URL / SUPABASE_KEY，請先設定好再重新執行本腳本。")
        return

    # 延後 import：只有真的要連 Supabase 時才載入 supabase-py。
    from supabase import create_client

    client = create_client(settings.supabase_url, settings.supabase_key)

    existing = client.table("products").select("id").limit(1).execute()
    if existing.data:
        print("products 資料表已經有資料，跳過種子資料匯入（避免重複塞入相同商品）。")
        return

    seed_products = _load_seed_products()
    for product in seed_products:
        client.table("products").insert(product).execute()
    print(f"已匯入 {len(seed_products)} 筆種子商品資料到 Supabase。")


def main() -> None:
    parser = argparse.ArgumentParser(description="MeowShop 資料庫初始化腳本")
    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "刪除現有 SQLite 資料庫並重建（僅適用 DB_BACKEND=sqlite）。"
            "注意：這是不可逆的操作，會清空所有既有資料，請先確認再使用。"
        ),
    )
    args = parser.parse_args()

    settings = get_settings()
    print(f"DB_BACKEND = {settings.db_backend}")

    if settings.db_backend == "supabase":
        init_supabase()
    else:
        init_sqlite(reset=args.reset)


if __name__ == "__main__":
    main()
