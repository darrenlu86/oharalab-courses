-- BrewGo 沖沖咖啡｜stage4 SQLite schema
--
-- 這個檔案本身不會自動被執行，是給 scripts/init_db.py 讀取後 executescript() 的。
-- 完整 ER 圖與逐表「為什麼這樣設計」寫在 docs/DATABASE.md，這裡的註解只放
-- 「看 schema 本身就該懂」的事（型別、約束），不重複那份文件的完整脈絡。

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,          -- bcrypt 雜湊，絕不存明文密碼
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,               -- 刻意不用 AUTOINCREMENT：id 固定對應 master 型錄的 1-12 號
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    price INTEGER NOT NULL,               -- 金額用整數存新台幣「元」，不用浮點數存錢
    stock INTEGER NOT NULL DEFAULT 0,
    category TEXT NOT NULL,               -- beans / drip / gear / cups / gift
    image_url TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cart_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, product_id)          -- 同一使用者、同一商品只有一列，靠這個做「累加」
);
CREATE INDEX IF NOT EXISTS idx_cart_items_user_id ON cart_items(user_id);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    total_amount INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending')),    -- 本階段只有一種狀態，見 DATABASE.md 的取捨說明
    recipient_name TEXT NOT NULL,
    recipient_address TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    -- product_name / unit_price 是下單當下的「快照」，跟 products 表的即時資料分開存：
    -- 商品之後改名、改價，都不應該讓已經成立的歷史訂單金額跟著變動。
    product_name TEXT NOT NULL,
    unit_price INTEGER NOT NULL,
    quantity INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
