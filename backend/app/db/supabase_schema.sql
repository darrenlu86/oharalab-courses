-- MeowShop 喵喵商店｜Supabase (PostgreSQL) schema
--
-- 使用方式：複製整份貼到 Supabase 專案的 SQL Editor 執行一次即可
-- （scripts/init_db.py 在 DB_BACKEND=supabase 時只會「提醒」你來這裡執行，
--  不會用程式自動跑 DDL——原因見 init_db.py 內的說明註解）。
--
-- 欄位名稱刻意跟 sqlite_schema.sql 完全一致，只有型別/自增語法依 PostgreSQL 慣例調整：
-- - 自增主鍵改用 GENERATED ALWAYS AS IDENTITY（PostgreSQL 建議寫法，取代舊式 SERIAL）
-- - 布林值有原生 BOOLEAN 型別，不用像 SQLite 那樣借用 INTEGER 0/1
-- - 時間戳記用 TIMESTAMPTZ（含時區資訊）+ now()，比 SQLite 的純文字時間更精確、也更標準

CREATE TABLE IF NOT EXISTS users (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS products (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    price INTEGER NOT NULL,               -- 金額一律用整數存新台幣「元」，兩邊資料庫的規則要一致
    stock INTEGER NOT NULL DEFAULT 0,
    category TEXT NOT NULL,
    image_url TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cart_items (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    product_id BIGINT NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, product_id)
);
CREATE INDEX IF NOT EXISTS idx_cart_items_user_id ON cart_items(user_id);

CREATE TABLE IF NOT EXISTS orders (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    total_amount INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'paid', 'failed', 'cancelled')),
    recipient_name TEXT NOT NULL,
    recipient_address TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);

CREATE TABLE IF NOT EXISTS order_items (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(id),
    product_id BIGINT NOT NULL REFERENCES products(id),
    -- product_name / unit_price 是下單當下的快照，理由跟 sqlite_schema.sql 一致。
    product_name TEXT NOT NULL,
    unit_price INTEGER NOT NULL,
    quantity INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);

CREATE TABLE IF NOT EXISTS payments (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(id),
    amount INTEGER NOT NULL,
    method TEXT NOT NULL DEFAULT 'mock_card',
    status TEXT NOT NULL CHECK (status IN ('success', 'failed')),
    transaction_id TEXT NOT NULL UNIQUE,
    card_last4 TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_payments_order_id ON payments(order_id);

-- 注意（教學簡化聲明，呼應 docs/PRD.md）：這裡沒有設定 Row Level Security（RLS）政策。
-- 本專案的 Supabase 存取一律透過後端 FastAPI 用 service role key 呼叫，
-- 存取權限控管都在後端程式碼裡（例如 get_current_user、訂單一定帶 user_id 過濾），
-- 前端瀏覽器不會直接拿 Supabase key 存取資料庫，所以先不啟用 RLS；
-- 如果之後改成前端直接用 anon key 呼叫 Supabase，就一定要另外設計 RLS 政策。
