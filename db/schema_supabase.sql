-- db/schema_supabase.sql
-- 台積電股票分析教學專案 — Supabase（PostgreSQL）版資料表定義。
-- 可直接貼到 Supabase 專案的 SQL Editor 執行。本專案預設不實際串接 Supabase，
-- 這份檔案是「教學文件化選項」：讓學員知道同一份資料模型換成正式的雲端
-- PostgreSQL 資料庫時，哪些型別與寫法要跟著調整。
--
-- 與 schema_sqlite.sql 的差異（教學重點，對照 docs/PRD.md）：
--   1. 自增主鍵：SQLite 用 AUTOINCREMENT；PostgreSQL 用 GENERATED ALWAYS AS IDENTITY。
--   2. 日期／時間型別：SQLite 用 TEXT 存 ISO8601 字串；PostgreSQL 有原生
--      DATE 與 TIMESTAMPTZ，可以做日期運算與時區處理，不必自己解析字串。
--   3. 金額精度：SQLite 用 REAL（浮點數，有精度誤差風險）；PostgreSQL 用
--      NUMERIC(10,2)（定點數，適合金額計算，不會有浮點誤差）。
--   4. Upsert 語法：兩邊都支援 `INSERT ... ON CONFLICT ... DO UPDATE`，
--      寫法幾乎相同，這也是選擇 SQLite 做本地開發的原因之一——語法可直接遷移。

CREATE TABLE IF NOT EXISTS stocks (
    symbol      TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    market      TEXT,
    industry    TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS daily_prices (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    stock_symbol  TEXT NOT NULL REFERENCES stocks(symbol),
    trade_date    DATE NOT NULL,
    open          NUMERIC(10, 2),
    high          NUMERIC(10, 2),
    low           NUMERIC(10, 2),
    close         NUMERIC(10, 2),
    volume        BIGINT,
    turnover      BIGINT,
    transactions  INTEGER,
    change        NUMERIC(10, 2),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (stock_symbol, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_prices_trade_date
    ON daily_prices (trade_date);

CREATE TABLE IF NOT EXISTS news (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    stock_symbol  TEXT REFERENCES stocks(symbol),
    title         TEXT NOT NULL,
    url           TEXT NOT NULL UNIQUE,
    source        TEXT,
    published_at  TIMESTAMPTZ,
    summary       TEXT,
    crawled_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_news_symbol_published
    ON news (stock_symbol, published_at DESC);

-- 注意（教學重點：UNIQUE 與 NULL 的陷阱，與 schema_sqlite.sql 同步）：
--   PostgreSQL 的 UNIQUE 約束跟 SQLite 一樣，把 NULL 視為互不相等，
--   segment 允許 NULL 會讓 UNIQUE (anchor_symbol, company_name, segment)
--   對「沒有 segment」的列完全失去去重效果。改成 NOT NULL DEFAULT ''，
--   統一用空字串表示「無 segment 資訊」，讓 UNIQUE 約束能正常運作。
CREATE TABLE IF NOT EXISTS supply_chain_companies (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    anchor_symbol   TEXT NOT NULL REFERENCES stocks(symbol),
    company_name    TEXT NOT NULL,
    company_symbol  TEXT,
    relation        TEXT NOT NULL, -- upstream / midstream / downstream
    segment         TEXT NOT NULL DEFAULT '', -- 如「IP 設計/設備/材料/封測」；無資料時存空字串，不存 NULL
    source_url      TEXT,
    crawled_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (anchor_symbol, company_name, segment)
);
