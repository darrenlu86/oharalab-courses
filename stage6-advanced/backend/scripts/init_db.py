"""
資料庫初始化腳本——用法：`python scripts/init_db.py`（要在 backend/ 目錄下執行）。

負責什麼：建立 SQLite 資料表（app/db/schema.sql，stage6 新增了
`idx_products_category_active` 複合索引，見 schema.sql 開頭說明）+ 匯入
12 筆種子商品資料（app/db/seed_products.json，與 master 型錄逐筆一致，含 id）
+ 建立兩個測試帳號（管理員／顧客）+ 7 筆示範訂單（狀態涵蓋整個訂單狀態機，
stage5 新增，stage6 沿用不變）。

防呆設計（跟 meowshop / stage4 同一套原則，理由不重複展開）：這支腳本很可能被
重複執行——如果每次都無條件砍掉重建，一旦資料庫裡已經有你自己測出來的帳號、
訂單，會在沒有任何警告的情況下整個消失，這是不可逆的操作。所以預設行為是
「資料庫檔案已存在就跳過、印出提示」，只有明確加上 `--reset` 旗標才會真的刪除重建。

**誠實聲明——示範訂單為什麼不會影響商品庫存**：master spec 的商品型錄（見
docs/DATABASE.md 附錄）規定各商品的庫存數字是固定值，不得增刪改；如果種子資料
照著「已付款訂單真的扣過庫存」的邏輯回推每個商品庫存，庫存數字就會偏離 master
型錄公告的值，之後學員對照 README 附錄會對不起來。所以這裡的示範訂單是刻意的
「歷史示意資料」：訂單、payments 紀錄都是真的寫進資料庫、狀態也是真的分佈在
各種合法狀態，但**不會**連動去扣減 products.stock——這是教學簡化，正式產品不會
有這種「訂單存在但庫存沒被扣過」的不一致，這裡這樣做純粹是為了讓學員每次重建
資料庫，商品庫存都精準對照得上 master 型錄附錄。
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
from app.security import hash_password  # noqa: E402

SEED_PATH = _BACKEND_DIR / "app" / "db" / "seed_products.json"

ADMIN_EMAIL = "admin@brewgo.test"
ADMIN_PASSWORD = "Admin12345"
CUSTOMER_EMAIL = "customer@brewgo.test"
CUSTOMER_PASSWORD = "Customer12345"

# 7 筆示範訂單：日期固定在 2026-07-14 ~ 2026-07-20（明確標示為示範資料，不是真的
# 營運紀錄），狀態涵蓋 pending / paid / failed / shipped / completed / cancelled
# 整個訂單狀態機，讓後台 Dashboard 一開始就有東西可以看。
# items 用 (product_id, quantity) 表示，unit_price / product_name 會在寫入時
# 從當下的 products 表查出來，確保金額跟型錄一致。
DEMO_ORDERS = [
    {
        "created_at": "2026-07-14 10:00:00",
        "status": "completed",
        "recipient_name": "測試顧客",
        "recipient_address": "台北市大安區羅斯福路一段 1 號",
        "items": [(1, 2), (5, 1)],
        "payments": [("success", "4242")],
    },
    {
        "created_at": "2026-07-15 11:30:00",
        "status": "completed",
        "recipient_name": "測試顧客",
        "recipient_address": "台北市大安區羅斯福路一段 1 號",
        "items": [(4, 1)],
        "payments": [("success", "4242")],
    },
    {
        "created_at": "2026-07-16 09:15:00",
        "status": "shipped",
        "recipient_name": "測試顧客",
        "recipient_address": "台北市大安區羅斯福路一段 1 號",
        "items": [(7, 1), (8, 1)],
        "payments": [("success", "4242")],
    },
    {
        # 這筆示範「付款失敗過一次、重試才成功」——payments 表會有兩筆紀錄，
        # 對照後台 Dashboard「待出貨」數字會把這筆算進去（status=paid）。
        "created_at": "2026-07-17 14:00:00",
        "status": "paid",
        "recipient_name": "測試顧客",
        "recipient_address": "台北市大安區羅斯福路一段 1 號",
        "items": [(12, 1)],
        "payments": [("failed", "0002"), ("success", "4242")],
    },
    {
        "created_at": "2026-07-18 16:45:00",
        "status": "pending",
        "recipient_name": "測試顧客",
        "recipient_address": "台北市大安區羅斯福路一段 1 號",
        "items": [(2, 1), (6, 1)],
        "payments": [],
    },
    {
        # 顧客下單後改變心意，訂單還是 pending 狀態時自行取消。
        "created_at": "2026-07-19 08:20:00",
        "status": "cancelled",
        "recipient_name": "測試顧客",
        "recipient_address": "台北市大安區羅斯福路一段 1 號",
        "items": [(10, 2)],
        "payments": [],
    },
    {
        "created_at": "2026-07-20 12:00:00",
        "status": "failed",
        "recipient_name": "測試顧客",
        "recipient_address": "台北市大安區羅斯福路一段 1 號",
        "items": [(3, 1)],
        "payments": [("failed", "0002")],
    },
]


def _load_seed_products() -> list[dict]:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def _seed_accounts_and_orders(conn: sqlite3.Connection) -> None:
    admin_id = conn.execute(
        "INSERT INTO users (email, password_hash, name, role) VALUES (?, ?, ?, 'admin')",
        (ADMIN_EMAIL, hash_password(ADMIN_PASSWORD), "店長 Admin"),
    ).lastrowid
    customer_id = conn.execute(
        "INSERT INTO users (email, password_hash, name, role) VALUES (?, ?, ?, 'customer')",
        (CUSTOMER_EMAIL, hash_password(CUSTOMER_PASSWORD), "測試顧客"),
    ).lastrowid
    print(f"已建立管理員帳號：{ADMIN_EMAIL}（id={admin_id}）")
    print(f"已建立顧客測試帳號：{CUSTOMER_EMAIL}（id={customer_id}）")

    for order in DEMO_ORDERS:
        total_amount = 0
        item_rows = []
        for product_id, quantity in order["items"]:
            product = conn.execute(
                "SELECT name, price FROM products WHERE id = ?", (product_id,)
            ).fetchone()
            unit_price = product["price"]
            total_amount += unit_price * quantity
            item_rows.append((product_id, product["name"], unit_price, quantity))

        order_id = conn.execute(
            """
            INSERT INTO orders
                (user_id, total_amount, status, recipient_name, recipient_address, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                customer_id,
                total_amount,
                order["status"],
                order["recipient_name"],
                order["recipient_address"],
                order["created_at"],
                order["created_at"],
            ),
        ).lastrowid

        for product_id, product_name, unit_price, quantity in item_rows:
            conn.execute(
                """
                INSERT INTO order_items (order_id, product_id, product_name, unit_price, quantity)
                VALUES (?, ?, ?, ?, ?)
                """,
                (order_id, product_id, product_name, unit_price, quantity),
            )

        for payment_status, card_last4 in order["payments"]:
            conn.execute(
                """
                INSERT INTO payments (order_id, amount, card_last4, status, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (order_id, total_amount, card_last4, payment_status, order["created_at"]),
            )

    print(f"已匯入 {len(DEMO_ORDERS)} 筆示範訂單（含對應 payments 紀錄）。")


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
        conn.row_factory = sqlite3.Row
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

        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if user_count > 0:
            print(f"users 資料表已有 {user_count} 筆資料，跳過測試帳號與示範訂單匯入。")
        else:
            _seed_accounts_and_orders(conn)
            conn.commit()
    finally:
        conn.close()

    print("SQLite 資料庫初始化完成！")


if __name__ == "__main__":
    main()
