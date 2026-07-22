-- db/schema_sqlite.sql
-- 台積電股票分析教學專案 — SQLite 版資料表定義。
-- 由 scripts/init_db.py 執行本檔建表；教學重點見 docs/PRD.md「資料庫設計」章節。

-- stocks：股票基本資料表。symbol 是主鍵，因為股票代號本身就是天然唯一識別碼，
-- 不需要另外設自增 id。
CREATE TABLE IF NOT EXISTS stocks (
    symbol      TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    market      TEXT,
    industry    TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- daily_prices：每日股價。
-- 注意：SQLite 沒有原生 DATE 型別，統一用 TEXT 存 ISO8601 格式（YYYY-MM-DD），
-- 排序與字串比較天生就正確，這是 SQLite 教學上常見的簡化取捨。
CREATE TABLE IF NOT EXISTS daily_prices (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_symbol  TEXT NOT NULL REFERENCES stocks(symbol),
    trade_date    TEXT NOT NULL,
    open          REAL,
    high          REAL,
    low           REAL,
    close         REAL,
    volume        INTEGER,
    turnover      INTEGER,
    transactions  INTEGER,
    change        REAL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (stock_symbol, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_prices_trade_date
    ON daily_prices (trade_date);

-- news：新聞。url 是唯一鍵，因為同一篇新聞不該因為重複爬取而重複入庫。
CREATE TABLE IF NOT EXISTS news (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_symbol  TEXT REFERENCES stocks(symbol),
    title         TEXT NOT NULL,
    url           TEXT NOT NULL UNIQUE,
    source        TEXT,
    published_at  TEXT,
    summary       TEXT,
    crawled_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_news_symbol_published
    ON news (stock_symbol, published_at DESC);

-- supply_chain_companies：上下游供應鏈公司。
-- company_symbol 允許 NULL，因為上下游公司不一定是上市櫃公司（沒有股票代號）。
--
-- 注意（教學重點：UNIQUE 與 NULL 的陷阱）：
--   segment 刻意設成 NOT NULL DEFAULT ''，不允許 NULL。原因是 SQLite 與
--   PostgreSQL 的 UNIQUE 約束都把 NULL 視為「與任何值都不相等」（包含
--   NULL 自己），所以 UNIQUE (anchor_symbol, company_name, segment) 若
--   segment 允許 NULL，同一組 (anchor_symbol, company_name, NULL) 重複插入
--   會被當成不同列，完全不會去重——重複爬取就會讓這張表無限膨脹。
--   改成 NOT NULL DEFAULT ''，把「沒有 segment 資訊」統一表示成空字串，
--   讓 UNIQUE 約束能正常比對、正常去重。呼叫端（repository 層）在寫入前
--   要負責把 None 正規化成 ''，schema 本身的 DEFAULT '' 只保底沒傳值的情況。
CREATE TABLE IF NOT EXISTS supply_chain_companies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    anchor_symbol   TEXT NOT NULL REFERENCES stocks(symbol),
    company_name    TEXT NOT NULL,
    company_symbol  TEXT,
    relation        TEXT NOT NULL, -- upstream / midstream / downstream
    segment         TEXT NOT NULL DEFAULT '', -- 如「IP 設計/設備/材料/封測」；無資料時存空字串，不存 NULL
    source_url      TEXT,
    crawled_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (anchor_symbol, company_name, segment)
);
