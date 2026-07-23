"""
資料庫存取層——連線管理 + 每個資料表的查詢/寫入函式。

跟上一份教材（meowshop）的差異，也是本階段的教學重點：
meowshop 用了完整的 Repository Pattern（`app/repositories/base.py` 定義抽象介面，
`sqlite_repo.py` / `supabase_repo.py` 兩種實作，`factory.py` 依環境變數切換）——
那一層抽象的價值在於「同一套介面、可以換底層資料庫」。本課程 master spec 規定
六個階段全部只用 SQLite（不需要切換到 Supabase），既然永遠只有一種實作，
硬加一層「可以替換但永遠不會真的替換」的抽象介面，只會讓初學者多一層要理解的
間接層、卻拿不到對應的好處。所以這裡刻意簡化成「一個模組、一組函式」，
直接把 SQL 寫在函式裡——這是本階段「夠用就好、不過度設計」的具體示範。

**如果你的專案未來真的需要換資料庫**（例如公司要求正式環境用 PostgreSQL），
meowshop 的 Repository Pattern 寫法就是你該參考的方向：把這裡的函式簽名照抄
成抽象介面，對照 meowshop-tutorial/backend/app/repositories/ 的做法即可。

連線策略：不是「每個函式各自開關連線」（這裡刻意不跟 meowshop 一樣），而是
「每個 HTTP request 共用一條連線」——`app/deps.py` 的 `get_db()` 是一個 FastAPI
generator dependency，在 request 一開始呼叫 `get_connection()` 建立一條連線、
`yield` 給這個 request 會用到的路由函式，路由函式再把同一條連線透過參數傳給
這個模組裡的各個函式；不管 request 處理成功還是中途拋例外，`finally` 區塊都會
在 request 結束時關閉這條連線。

會這樣設計，是因為部分操作需要「一連串資料庫寫入要嘛全部一起成功、要嘛全部
一起復原」：`app/routers/orders.py` 建單時要「逐項檢查並扣庫存 → 寫入訂單 →
清空購物車」，只要中途任何一項扣庫存失敗，就要整批復原，不能留下「扣了一半
庫存、但訂單沒真的建立」的中間狀態。做法是這些操作全部在同一條連線上執行、
最後才一次 `conn.commit()`；失敗時呼叫 `conn.rollback()`，撤銷這條連線上「還沒
commit」的所有變更。這個「整批復原」的能力，前提就是這些函式共用同一條連線、
同一個交易（transaction）——如果每個函式各自開一條連線，`rollback()` 只能撤銷
自己那條連線上的變更，沒辦法讓「扣庫存」跟「建立訂單」這兩個分屬不同函式的
操作綁在同一個交易裡一起復原。

SQLite 連線物件預設不是執行緒安全的，但這裡「每個 request 各自一條連線、
不同 request 之間互不共用」本身就已經避免了多個 request 同時搶用同一條連線的
問題，不需要再靠「每個函式各自開關連線」換取安全性——那樣做反而會讓上面說的
整批 rollback 沒辦法運作。
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


def create_user(conn: sqlite3.Connection, email: str, password_hash: str, name: str) -> dict:
    try:
        cursor = conn.execute(
            "INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)",
            (email, password_hash, name),
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


# ---------- products ----------


def list_products(
    conn: sqlite3.Connection, category: str | None = None, search: str | None = None
) -> list[dict]:
    sql = "SELECT * FROM products WHERE 1 = 1"
    params: list = []
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


def get_product_by_id(conn: sqlite3.Connection, product_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    return _row(row)


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


# ---------- cart_items ----------


def get_cart_items(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            p.id AS product_id,
            p.name AS name,
            p.price AS price,
            p.image_url AS image_url,
            p.stock AS stock,
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
    """建立訂單本體 + order_items 品項快照，回傳新訂單的 id。

    呼叫端（routers/orders.py）負責在同一條連線上，先用 decrease_stock() 逐項扣庫存，
    全部扣成功才呼叫這個函式、最後一次 commit；任何一項扣庫存失敗，呼叫端要
    rollback 整條連線，不能留下「扣了一半庫存、但訂單沒真的建立」的中間狀態。
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
    return order_id


def list_orders_by_user(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC, id DESC",
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


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
    order = dict(order_row)
    item_rows = conn.execute(
        "SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,)
    ).fetchall()
    order["items"] = [dict(row) for row in item_rows]
    return order
