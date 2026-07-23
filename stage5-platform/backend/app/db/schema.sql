-- BrewGo 沖沖咖啡｜stage5 SQLite schema
--
-- 這個檔案本身不會自動被執行，是給 scripts/init_db.py 讀取後 executescript() 的。
-- 完整 ER 圖與逐表「為什麼這樣設計」寫在 docs/DATABASE.md，這裡的註解只放
-- 「看 schema 本身就該懂」的事（型別、約束）。
--
-- 跟 stage4 的差異（逐條見 docs/DATABASE.md「變更說明」一節）：
-- 1. users 新增 role 欄位（customer / admin）——後台需要分辨誰能打 /api/admin/*。
-- 2. products 新增 is_active 欄位——下架商品用軟刪除（is_active=0），不是真的 DELETE，
--    保留歷史訂單仍能查到「當初買的是哪個商品」的完整資料（見 order_items 的
--    product_name / unit_price 快照設計，is_active 影響的只是「現在還能不能買」）。
-- 3. orders.status 的合法值從只有一種（'pending'）擴充成完整的訂單狀態機
--    （pending / paid / failed / shipped / completed / cancelled），因為本階段
--    有了真正的付款流程與後台出貨管理，狀態機詳見 docs/SYSTEM_DESIGN.md。
-- 4. 新增 payments 資料表——每一次付款嘗試（不管成功或失敗）都留一筆紀錄，
--    這樣「這筆訂單付款失敗過幾次、最後是哪張卡付成功的」才有稽核軌跡可查。

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,          -- bcrypt 雜湊，絕不存明文密碼
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'customer'
        CHECK (role IN ('customer', 'admin')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,               -- 刻意不用 AUTOINCREMENT：master 型錄 1-12 號 id 固定
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    price INTEGER NOT NULL,               -- 金額用整數存新台幣「元」，不用浮點數存錢
    stock INTEGER NOT NULL DEFAULT 0,
    category TEXT NOT NULL,               -- beans / drip / gear / cups / gift
    image_url TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1, -- 0=已下架（前台列表與詳情都看不到，但歷史訂單仍看得到快照）
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
        CHECK (status IN ('pending', 'paid', 'failed', 'shipped', 'completed', 'cancelled')),
    recipient_name TEXT NOT NULL,
    recipient_address TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    -- product_name / unit_price 是下單當下的「快照」，跟 products 表的即時資料分開存：
    -- 商品之後改名、改價、甚至下架，都不應該讓已經成立的歷史訂單內容跟著變動。
    product_name TEXT NOT NULL,
    unit_price INTEGER NOT NULL,
    quantity INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    amount INTEGER NOT NULL,
    card_last4 TEXT NOT NULL,             -- 只存卡號末 4 碼（教學示範也不存完整卡號，比照真實 PCI 規範精神）
    status TEXT NOT NULL CHECK (status IN ('success', 'failed')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_payments_order_id ON payments(order_id);
