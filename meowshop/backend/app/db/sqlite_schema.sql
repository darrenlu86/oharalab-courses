-- MeowShop 喵喵商店｜SQLite schema
--
-- 注意：這個檔案本身不會自動被執行，是給 scripts/init_db.py 讀取後逐句 executescript() 的。
-- 欄位名稱必須跟 supabase_schema.sql 完全一致（只有型別/自增語法不同），
-- 這樣 Repository 兩種實作回傳的 dict 才會有一樣的 key，routers 層才能共用同一套程式碼。

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,          -- bcrypt 雜湊，絕不存明文密碼
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    price INTEGER NOT NULL,               -- 教學點：金額用整數存新台幣「元」，不要用浮點數存錢
    stock INTEGER NOT NULL DEFAULT 0,
    category TEXT NOT NULL,               -- food / snack / toy / litter / supplies
    image_url TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1, -- SQLite 沒有原生 BOOLEAN，用 0/1 的 INTEGER 代替
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cart_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, product_id)          -- 同一個使用者、同一件商品只會有一列，靠這個做「累加」
);
CREATE INDEX IF NOT EXISTS idx_cart_items_user_id ON cart_items(user_id);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    total_amount INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'paid', 'failed', 'cancelled')),
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
    -- product_name / unit_price 是下單當下的「快照」，刻意跟 products 表的即時資料分開存：
    -- 商品之後改名、改價，都不應該讓已經成立的歷史訂單金額跟著變動。
    product_name TEXT NOT NULL,
    unit_price INTEGER NOT NULL,
    quantity INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    amount INTEGER NOT NULL,
    method TEXT NOT NULL DEFAULT 'mock_card',
    status TEXT NOT NULL CHECK (status IN ('success', 'failed')),
    transaction_id TEXT NOT NULL UNIQUE,  -- 格式 MOCK-<uuid4>，模擬金流的交易編號
    card_last4 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_payments_order_id ON payments(order_id);
