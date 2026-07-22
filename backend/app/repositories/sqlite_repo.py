"""
SQLite 版的 Repository 實作——本教案「本機開發、零額外設定」的預設資料庫。

在架構中的位置：實作 `base.py` 定義的四個抽象介面，供 `factory.py` 在
`DB_BACKEND=sqlite`（預設值）時組裝出來。

關鍵設計「為什麼」：

- 為什麼用標準庫 `sqlite3` 而不是 ORM（例如 SQLAlchemy）：教學專案希望學員
  能直接看懂每一句 SQL 在做什麼，不希望 ORM 的抽象語法擋在中間；`sqlite3`
  是 Python 內建模組，零額外依賴，最適合「一個指令就能跑起來」的教學情境。
- 為什麼每個方法都自己開關連線（`sqlite3.connect()` ... 最後 `close()`），
  而不是整個 app 共用一條連線：SQLite 的連線物件預設不是執行緒安全的，
  FastAPI 用 uvicorn 跑的時候，不同 request 可能在不同 thread 處理；
  每個方法用完就關閉連線，簡單、不易出現「連線被兩個 thread 同時搶用」的問題。
  這是教學上「用簡單方式換取正確性」的取捨，正式高流量系統會改用連線池。
- 為什麼每次連線都要下 `PRAGMA foreign_keys = ON`（**注意**，初學者最容易漏掉這行）：
  SQLite 預設「不會」強制檢查外鍵約束，就算 schema 裡寫了 `REFERENCES`，
  如果沒有每個連線都下這行 PRAGMA，刪除使用者時就算還有訂單指向他，
  SQLite 也不會擋下來，資料完整性形同虛設。這是 SQLite 和其他資料庫
  （像 PostgreSQL 預設就會檢查）很不一樣的地方。
"""

import sqlite3
from pathlib import Path

from app.repositories.base import (
    CartRepository,
    DuplicateEmailError,
    OrderRepository,
    ProductRepository,
    UserRepository,
)


def _connect(db_path: Path) -> sqlite3.Connection:
    """建立一條符合本專案規範的 SQLite 連線：row_factory 用 Row、外鍵檢查打開。"""
    conn = sqlite3.connect(str(db_path))
    # row_factory = sqlite3.Row 讓查詢結果可以像 dict 一樣用欄位名稱取值
    # （例如 row["email"]），而不用死記欄位在 SELECT 裡的第幾個位置。
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


class SQLiteUserRepository(UserRepository):
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def create(self, email: str, password_hash: str, name: str) -> dict:
        conn = _connect(self.db_path)
        try:
            cursor = conn.execute(
                "INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)",
                (email, password_hash, name),
            )
            conn.commit()
            return self._get_by_id(conn, cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            # users.email 有 UNIQUE 約束，違反時 sqlite3 會丟 IntegrityError；
            # 我們把它轉換成語意明確的自訂例外，讓 router 只要 catch 一種型別就好。
            raise DuplicateEmailError(email) from exc
        finally:
            conn.close()

    def get_by_email(self, email: str) -> dict | None:
        conn = _connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            return _row_to_dict(row)
        finally:
            conn.close()

    def get_by_id(self, user_id: int) -> dict | None:
        conn = _connect(self.db_path)
        try:
            return self._get_by_id(conn, user_id)
        finally:
            conn.close()

    @staticmethod
    def _get_by_id(conn: sqlite3.Connection, user_id: int) -> dict | None:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _row_to_dict(row)


class SQLiteProductRepository(ProductRepository):
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def list(self, category: str | None = None, search: str | None = None) -> list[dict]:
        conn = _connect(self.db_path)
        try:
            sql = "SELECT * FROM products WHERE is_active = 1"
            params: list = []
            if category:
                sql += " AND category = ?"
                params.append(category)
            if search:
                # 用 LIKE 做「模糊比對」；前後包 % 代表比對商品名稱裡任何位置出現這段文字。
                # SQLite 的 LIKE 對 ASCII 字母預設就是不分大小寫，中文名稱本來就沒有大小寫問題。
                sql += " AND name LIKE ?"
                params.append(f"%{search}%")
            sql += " ORDER BY id"
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_by_id(self, product_id: int) -> dict | None:
        conn = _connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM products WHERE id = ? AND is_active = 1", (product_id,)
            ).fetchone()
            return _row_to_dict(row)
        finally:
            conn.close()

    def decrease_stock(self, product_id: int, quantity: int) -> bool:
        conn = _connect(self.db_path)
        try:
            # 條件式 UPDATE：只有「庫存 >= quantity」這個條件成立時才會真的更新到那一列，
            # cursor.rowcount 會告訴我們「這句 SQL 實際改動了幾列」——1 代表扣成功，
            # 0 代表庫存不夠（沒有任何列符合條件，SQL 完全沒有生效）。
            cursor = conn.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?",
                (quantity, product_id, quantity),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


class SQLiteCartRepository(CartRepository):
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def get_items(self, user_id: int) -> list[dict]:
        conn = _connect(self.db_path)
        try:
            # 教學點——為什麼要加 `AND p.is_active = 1`：如果不過濾，商品下架後
            # 仍然會出現在購物車裡（看起來是一件庫存正常、可以購買的商品），
            # 但真正建單時 orders.py 用的是有過濾 is_active 的 get_by_id()，
            # 會查不到商品、報出「庫存不足」，其實真正原因是「商品已下架」，
            # 訊息文不對題容易誤導人。這裡加上過濾之後，下架商品會直接從
            # 購物車「消失」——這是教學簡化，真實電商系統通常會保留這筆
            # cart_items、額外標示「已下架，請移除」讓使用者自己處理，
            # 而不是默默讓它消失。
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
                WHERE ci.user_id = ? AND p.is_active = 1
                ORDER BY ci.id
                """,
                (user_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def upsert_item(self, user_id: int, product_id: int, quantity_delta: int) -> None:
        conn = _connect(self.db_path)
        try:
            # ON CONFLICT ... DO UPDATE 是 SQLite 的 UPSERT 語法：
            # 如果 (user_id, product_id) 這組 UNIQUE 組合已經存在，就把數量「累加」，
            # 不存在就當作一般 INSERT——一句 SQL 同時處理兩種情況，不用先 SELECT 判斷。
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
        finally:
            conn.close()

    def set_quantity(self, user_id: int, product_id: int, quantity: int) -> bool:
        conn = _connect(self.db_path)
        try:
            cursor = conn.execute(
                "UPDATE cart_items SET quantity = ? WHERE user_id = ? AND product_id = ?",
                (quantity, user_id, product_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def remove_item(self, user_id: int, product_id: int) -> bool:
        conn = _connect(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM cart_items WHERE user_id = ? AND product_id = ?",
                (user_id, product_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def clear(self, user_id: int) -> None:
        conn = _connect(self.db_path)
        try:
            conn.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
            conn.commit()
        finally:
            conn.close()


class SQLiteOrderRepository(OrderRepository):
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def create(
        self,
        user_id: int,
        total_amount: int,
        recipient_name: str,
        recipient_address: str,
        items: list[dict],
    ) -> dict:
        conn = _connect(self.db_path)
        try:
            # 訂單本身與它的品項快照要「一起成功或一起失敗」，所以共用同一條連線、
            # 最後才一次 commit；只要中間有任何一句失敗，因為還沒 commit，
            # 這個連線關閉時等於自動捨棄了所有還沒 commit 的變更。
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
                    (
                        order_id,
                        item["product_id"],
                        item["product_name"],
                        item["unit_price"],
                        item["quantity"],
                    ),
                )
            conn.commit()
            return self._get_full_order(conn, order_id, user_id)
        finally:
            conn.close()

    def list_by_user(self, user_id: int) -> list[dict]:
        conn = _connect(self.db_path)
        try:
            rows = conn.execute(
                """
                SELECT * FROM orders
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (user_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_by_id(self, order_id: int, user_id: int) -> dict | None:
        conn = _connect(self.db_path)
        try:
            return self._get_full_order(conn, order_id, user_id)
        finally:
            conn.close()

    def update_status(self, order_id: int, status: str) -> None:
        conn = _connect(self.db_path)
        try:
            conn.execute(
                "UPDATE orders SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (status, order_id),
            )
            conn.commit()
        finally:
            conn.close()

    def add_payment(
        self,
        order_id: int,
        amount: int,
        status: str,
        transaction_id: str,
        card_last4: str,
    ) -> dict:
        conn = _connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                INSERT INTO payments (order_id, amount, method, status, transaction_id, card_last4)
                VALUES (?, ?, 'mock_card', ?, ?, ?)
                """,
                (order_id, amount, status, transaction_id, card_last4),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM payments WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return dict(row)
        finally:
            conn.close()

    @staticmethod
    def _get_full_order(conn: sqlite3.Connection, order_id: int, user_id: int) -> dict | None:
        """組出「訂單本體 + items + payments」的完整 dict。

        注意：這裡用 `user_id` 一起當查詢條件，而不是先查訂單、再另外判斷擁有者，
        是為了呼應 SPEC 的安全設計：別人的訂單要回 404（查無此訂單），
        而不是 403（訂單存在但你沒權限）——避免讓攻擊者從「404 vs 403」
        就能推測出「這個訂單 id 存不存在」，屬於資源存在性不外洩的基本安全習慣。
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
        payment_rows = conn.execute(
            "SELECT * FROM payments WHERE order_id = ? ORDER BY id", (order_id,)
        ).fetchall()
        order["payments"] = [dict(row) for row in payment_rows]
        return order
