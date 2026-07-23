"""
資料庫存取層——連線管理 + 每個資料表的查詢/寫入函式。

跟 meowshop 的差異，也是 stage4 就定下的教學重點：本課程 master spec 規定六個
階段全部只用 SQLite，不需要 Repository Pattern 那層「可以替換但永遠不會真的
替換」的抽象介面，這裡直接把 SQL 寫在函式裡。

連線策略沿用 stage4，本階段沒有變動：不是「每個函式各自開關連線」，而是
「每個 HTTP request 共用一條連線」——`app/deps.py` 的 `get_db()` 在 request
一開始建立連線，透過 `Depends(get_db)` 傳給這個 request 會呼叫到的所有路由與
db 函式共用，request 結束才關閉。這樣設計是因為 `routers/payments.py` 付款
成功時要「逐項扣庫存 → 更新訂單狀態 → 寫入付款紀錄」整批一起 commit，任何一步
失敗就要 `conn.rollback()` 撤銷整批——這個能力要靠多個函式共用同一條連線、
同一個交易才成立，完整理由見 stage4-fullstack/backend/app/db/database.py
模組開頭的說明，這裡不重複展開。

跟 stage4 的差異（逐項對照 docs/DATABASE.md「變更說明」）：
1. `create_user` 多一個 `role` 參數（預設 'customer'），給 `scripts/init_db.py`
   建立管理員種子帳號用；一般會員註冊路由（`routers/auth.py`）永遠不傳這個參數，
   確保「自己在註冊頁填表單」不可能生出管理員帳號。
2. `list_products` / `get_product_by_id` 多了 `include_inactive` 參數——前台永遠
   用預設值（只看得到上架商品），後台管理頁需要看到已下架商品才能把它重新上架，
   所以另外開一個口子讓後台可以選擇「連下架的也列出來」。
3. 新增 `create_product` / `update_product`：後台商品 CRUD 用，`update_product`
   只更新有傳進來的欄位（None 代表「這欄不改」），刻意不做真正的 DELETE
   （理由跟 is_active 欄位的教學點一致，見 schema.sql 開頭註解）。
4. `decrease_stock` 沿用 stage4 的做法，但呼叫時機從「建單當下」改成「付款成功
   當下」（見 routers/payments.py），這是本階段最重要的行為變更，理由寫在
   docs/DATABASE.md「訂單狀態與扣庫存時機」一節。
5. `create_order` 不再需要呼叫端先扣庫存——新版只單純寫入 orders + order_items，
   status 固定是 'pending'，扣不扣庫存完全交給付款流程處理。
6. 新增 `update_order_status`、`list_all_orders`（後台，含篩選）、
   `get_order_by_id_any_user`（後台查任何人的訂單，不像客戶端版本會用 user_id
   過濾）。
7. 新增 `create_payment`、`list_payments_by_order`——payments 表的存取。
8. 新增 `list_users`、`count_users_by_role`、`admin_summary`——給
   /api/admin/summary 用的聚合查詢。
"""

import sqlite3
from pathlib import Path

from app.config import get_settings


class DuplicateEmailError(Exception):
    """建立使用者時 email 已存在。用專屬例外類別，讓 routers 精準攔截成 409。"""


def get_connection() -> sqlite3.Connection:
    """建立一條符合本專案規範的 SQLite 連線：row_factory 用 Row、外鍵檢查打開。"""
    settings = get_settings()
    conn = sqlite3.connect(str(settings.sqlite_path))
    # row_factory = sqlite3.Row 讓查詢結果可以用欄位名稱取值（row["email"]）。
    conn.row_factory = sqlite3.Row
    # SQLite 預設不會檢查外鍵約束，每個連線都要手動打開，否則 REFERENCES 形同虛設。
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _row(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def init_schema(conn: sqlite3.Connection) -> None:
    """執行 schema.sql 建立資料表（executescript 允許一次跑多句 SQL）。"""
    schema_path = Path(__file__).resolve().parent / "schema.sql"
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.commit()


# ---------- users ----------


def create_user(
    conn: sqlite3.Connection, email: str, password_hash: str, name: str, role: str = "customer"
) -> dict:
    try:
        cursor = conn.execute(
            "INSERT INTO users (email, password_hash, name, role) VALUES (?, ?, ?, ?)",
            (email, password_hash, name, role),
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        # users.email 有 UNIQUE 約束，違反時轉換成語意明確的自訂例外。
        raise DuplicateEmailError(email) from exc
    return get_user_by_id(conn, cursor.lastrowid)


def get_user_by_email(conn: sqlite3.Connection, email: str) -> dict | None:
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return _row(row)


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row(row)


def list_users(conn: sqlite3.Connection) -> list[dict]:
    """後台會員清單——刻意在 SQL 層就不 SELECT password_hash，不是回傳後才篩掉。

    這是縱深防禦（defense in depth）的示範：就算未來 schemas.py 的 response_model
    不小心漏加欄位過濾，資料庫查詢結果本身也從來沒有把密碼雜湊值拉進 Python
    process 的記憶體裡，攻擊面比「查全部欄位、靠 Pydantic 濾掉」更小。
    """
    rows = conn.execute(
        "SELECT id, email, name, role, created_at FROM users ORDER BY id"
    ).fetchall()
    return [dict(row) for row in rows]


def count_users_by_role(conn: sqlite3.Connection, role: str) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM users WHERE role = ?", (role,)).fetchone()
    return row["n"]


# ---------- products ----------


def list_products(
    conn: sqlite3.Connection,
    category: str | None = None,
    search: str | None = None,
    include_inactive: bool = False,
) -> list[dict]:
    sql = "SELECT * FROM products WHERE 1 = 1"
    params: list = []
    if not include_inactive:
        sql += " AND is_active = 1"
    if category:
        sql += " AND category = ?"
        params.append(category)
    if search:
        # LIKE 模糊比對；SQLite 的 LIKE 對 ASCII 字母預設不分大小寫，中文本來就沒有大小寫問題。
        sql += " AND name LIKE ?"
        params.append(f"%{search}%")
    sql += " ORDER BY id"
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get_product_by_id(
    conn: sqlite3.Connection, product_id: int, include_inactive: bool = False
) -> dict | None:
    if include_inactive:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM products WHERE id = ? AND is_active = 1", (product_id,)
        ).fetchone()
    return _row(row)


def create_product(
    conn: sqlite3.Connection,
    name: str,
    description: str,
    price: int,
    stock: int,
    category: str,
    image_url: str,
) -> dict:
    cursor = conn.execute(
        """
        INSERT INTO products (name, description, price, stock, category, image_url, is_active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
        """,
        (name, description, price, stock, category, image_url),
    )
    conn.commit()
    return get_product_by_id(conn, cursor.lastrowid, include_inactive=True)


def update_product(conn: sqlite3.Connection, product_id: int, fields: dict) -> dict | None:
    """局部更新——`fields` 只包含真的要改的欄位（呼叫端已經濾掉 None）。

    刻意不接受任意欄位名稱：白名單寫死在這裡，避免呼叫端不小心傳進
    `id` / `created_at` 這種不該被外部改動的欄位（教學點：白名單優於黑名單）。
    """
    allowed = {"name", "description", "price", "stock", "category", "image_url", "is_active"}
    updates = {key: value for key, value in fields.items() if key in allowed}
    if not updates:
        return get_product_by_id(conn, product_id, include_inactive=True)

    set_clause = ", ".join(f"{key} = ?" for key in updates)
    params = list(updates.values()) + [product_id]
    conn.execute(f"UPDATE products SET {set_clause} WHERE id = ?", params)
    conn.commit()
    return get_product_by_id(conn, product_id, include_inactive=True)


def decrease_stock(conn: sqlite3.Connection, product_id: int, quantity: int) -> bool:
    """條件式 UPDATE：只有庫存 >= quantity 才會真的扣，回傳是否扣成功。

    為什麼要把「檢查」跟「扣減」合成同一句 SQL，而不是先 SELECT 讀庫存、判斷夠不夠、
    再 UPDATE：如果拆成兩步，兩個並發的請求可能同時讀到「庫存還夠」，然後都各自扣一次，
    導致庫存變成負數（經典的 race condition／超賣問題）。這句 SQL 由資料庫保證整體是
    原子操作，`cursor.rowcount` 告訴我們有沒有真的更新到那一列（1=成功、0=庫存不夠）。
    """
    cursor = conn.execute(
        "UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?",
        (quantity, product_id, quantity),
    )
    return cursor.rowcount > 0


def list_low_stock_products(conn: sqlite3.Connection, threshold: int = 5) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM products WHERE is_active = 1 AND stock < ? ORDER BY stock, id",
        (threshold,),
    ).fetchall()
    return [dict(row) for row in rows]


# ---------- cart_items ----------


def get_cart_items(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    # 這裡刻意不加 `AND p.is_active = 1`：商品下架後，已經放進購物車的品項不會
    # 被自動清掉（購物車表本來就沒有這個機制），如果 JOIN 濾掉下架商品，使用者
    # 會看到「購物車少了一項」卻不知道發生了什麼事，一路到建單被 409 擋下
    # （見 app/routers/orders.py）才第一次看到「已下架」三個字，不知道該移除
    # 哪一項。改成把 `is_active` 也一起帶出來，讓呼叫端（app/routers/cart.py
    # `_build_cart_out()`）決定要怎麼標示，前端就能提早顯示徽章、停用該品項的
    # 數量調整、並在結帳前就說明原因（後端的 409 防線本身不受影響，仍然是最終
    # 那一道守門，這裡只是把訊息提前說清楚）。
    rows = conn.execute(
        """
        SELECT
            p.id AS product_id,
            p.name AS name,
            p.price AS price,
            p.image_url AS image_url,
            p.stock AS stock,
            p.is_active AS is_active,
            ci.quantity AS quantity
        FROM cart_items ci
        JOIN products p ON p.id = ci.product_id
        WHERE ci.user_id = ?
        ORDER BY ci.id
        """,
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def upsert_cart_item(conn: sqlite3.Connection, user_id: int, product_id: int, quantity_delta: int) -> None:
    # ON CONFLICT ... DO UPDATE 是 SQLite 的 UPSERT 語法：(user_id, product_id) 已存在就累加，
    # 不存在就當一般 INSERT，一句 SQL 同時處理兩種情況，不用先 SELECT 判斷。
    conn.execute(
        """
        INSERT INTO cart_items (user_id, product_id, quantity)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, product_id)
        DO UPDATE SET quantity = quantity + excluded.quantity
        """,
        (user_id, product_id, quantity_delta),
    )
    conn.commit()


def set_cart_item_quantity(conn: sqlite3.Connection, user_id: int, product_id: int, quantity: int) -> bool:
    cursor = conn.execute(
        "UPDATE cart_items SET quantity = ? WHERE user_id = ? AND product_id = ?",
        (quantity, user_id, product_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def remove_cart_item(conn: sqlite3.Connection, user_id: int, product_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM cart_items WHERE user_id = ? AND product_id = ?",
        (user_id, product_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def clear_cart(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
    conn.commit()


# ---------- orders ----------


def create_order(
    conn: sqlite3.Connection,
    user_id: int,
    total_amount: int,
    recipient_name: str,
    recipient_address: str,
    items: list[dict],
) -> int:
    """建立訂單本體 + order_items 品項快照，回傳新訂單的 id，status 固定是 'pending'。

    跟 stage4 的差異：這個函式不再負責扣庫存（呼叫端 routers/orders.py 也不會先扣），
    庫存要等到 routers/payments.py 付款成功那一刻才會真的減少——理由見
    docs/DATABASE.md「訂單狀態與扣庫存時機」一節。
    """
    cursor = conn.execute(
        """
        INSERT INTO orders (user_id, total_amount, status, recipient_name, recipient_address)
        VALUES (?, ?, 'pending', ?, ?)
        """,
        (user_id, total_amount, recipient_name, recipient_address),
    )
    order_id = cursor.lastrowid
    for item in items:
        conn.execute(
            """
            INSERT INTO order_items (order_id, product_id, product_name, unit_price, quantity)
            VALUES (?, ?, ?, ?, ?)
            """,
            (order_id, item["product_id"], item["product_name"], item["unit_price"], item["quantity"]),
        )
    conn.commit()
    return order_id


def list_orders_by_user(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC, id DESC",
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _attach_items(conn: sqlite3.Connection, order: dict) -> dict:
    item_rows = conn.execute(
        "SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order["id"],)
    ).fetchall()
    order["items"] = [dict(row) for row in item_rows]
    return order


def get_order_by_id(conn: sqlite3.Connection, order_id: int, user_id: int) -> dict | None:
    """依 id 查單一訂單，必須同時符合 user_id——不是自己的訂單一律當作不存在。

    教學安全點：這裡用 user_id 一起當查詢條件，讓「別人的訂單」跟「根本不存在的
    訂單」在查詢結果上完全一樣（都是 None），routers 層才能安心一律回 404，
    不會不小心洩漏「這個訂單 id 其實存在，只是不是你的」這種資源存在性資訊。
    """
    order_row = conn.execute(
        "SELECT * FROM orders WHERE id = ? AND user_id = ?", (order_id, user_id)
    ).fetchone()
    if order_row is None:
        return None
    return _attach_items(conn, dict(order_row))


def get_order_by_id_any_user(conn: sqlite3.Connection, order_id: int) -> dict | None:
    """後台查訂單專用——不限定 user_id（admin 本來就該能看到所有人的訂單）。"""
    order_row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order_row is None:
        return None
    return _attach_items(conn, dict(order_row))


def update_order_status(conn: sqlite3.Connection, order_id: int, new_status: str) -> None:
    conn.execute(
        "UPDATE orders SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (new_status, order_id),
    )
    conn.commit()


def list_all_orders(conn: sqlite3.Connection, status: str | None = None) -> list[dict]:
    """後台訂單列表——不分使用者，可選狀態篩選；每筆都附上品項明細（跟顧客端的
    訂單詳情一樣，後台列表也需要看到買了什麼，不是只看到金額與狀態）。"""
    sql = "SELECT * FROM orders WHERE 1 = 1"
    params: list = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC, id DESC"
    rows = conn.execute(sql, params).fetchall()
    return [_attach_items(conn, dict(row)) for row in rows]


# ---------- payments ----------


def create_payment(
    conn: sqlite3.Connection, order_id: int, amount: int, card_last4: str, status: str
) -> dict:
    cursor = conn.execute(
        "INSERT INTO payments (order_id, amount, card_last4, status) VALUES (?, ?, ?, ?)",
        (order_id, amount, card_last4, status),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM payments WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def list_payments_by_order(conn: sqlite3.Connection, order_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM payments WHERE order_id = ? ORDER BY id", (order_id,)
    ).fetchall()
    return [dict(row) for row in rows]


# ---------- admin summary ----------

# 「已完成付款流程」的訂單狀態集合：paid（已付未出貨）／shipped（已出貨未完成）／
# completed（已完成）都代表這筆錢真的進帳了，計算總營收要把這三種狀態的訂單金額
# 加總；pending（還沒付）、failed（付款失敗）、cancelled（已取消）都不算營收。
REVENUE_STATUSES = ("paid", "shipped", "completed")


def admin_summary(conn: sqlite3.Connection) -> dict:
    placeholders = ", ".join("?" for _ in REVENUE_STATUSES)

    revenue_row = conn.execute(
        f"SELECT COALESCE(SUM(total_amount), 0) AS revenue FROM orders WHERE status IN ({placeholders})",
        REVENUE_STATUSES,
    ).fetchone()
    total_orders_row = conn.execute("SELECT COUNT(*) AS n FROM orders").fetchone()
    pending_shipment_row = conn.execute(
        "SELECT COUNT(*) AS n FROM orders WHERE status = 'paid'"
    ).fetchone()

    return {
        "total_revenue": revenue_row["revenue"],
        "total_orders": total_orders_row["n"],
        "pending_shipment_orders": pending_shipment_row["n"],
        "low_stock_products": list_low_stock_products(conn),
        "member_count": count_users_by_role(conn, "customer"),
    }
