"""
db/sqlite_repo.py — StockRepository 的 SQLite 實作。

做什麼：
    用 Python 標準庫的 sqlite3 模組，實作 db/base.py 定義的所有介面方法。
    這是本專案的預設、且唯一實際驗證過的資料庫後端。

為什麼這樣設計：
    - 只用標準庫 sqlite3，不引入額外的 ORM（如 SQLAlchemy）：教學專案的重點是
      讓學員直接看懂 SQL 語句在做什麼，ORM 反而會多一層抽象，增加初學者的認知負擔。
    - 每個方法內部自己開關連線，不維護長駐連線：SQLite 是檔案型資料庫，
      短連線的開銷很小，這樣寫法最簡單也最不容易踩到「忘記 commit」的坑。

注意（為什麼要用 `with closing(self._connect()) as conn, conn:` 而不是單純
`with self._connect() as conn:`）：
    `sqlite3.Connection` 的 context manager 只負責交易（成功時 commit、
    發生例外時 rollback），不會呼叫 `conn.close()`——這是初學者很容易誤會
    的地方，以為 `with sqlite3.connect(...) as conn:` 結束後連線就關掉了，
    其實沒有，連線物件只是靠之後被垃圾回收（GC）才真正釋放。短時間內
    大量呼叫（例如批次 upsert 一次跑很多次）會讓「已經用完但還沒被 GC
    回收」的連線同時存在，浪費檔案描述符（file descriptor）。顯式呼叫
    close() 才能確保資源立刻釋放，不必依賴 GC 的時機，這是操作任何資料庫
    連線（不只 SQLite）都該養成的好習慣。寫法上用 `contextlib.closing()`
    包一層負責關閉，再讓同一個 conn 物件自己的 context manager 負責交易，
    兩者疊加：離開 with 區塊時「先 commit/rollback，再 close」。
    - Row 轉 dict：sqlite3 預設回傳 tuple，本檔案統一設定 conn.row_factory =
      sqlite3.Row 並在回傳前轉成 dict，讓呼叫端（爬蟲、Dashboard）可以用欄位名稱
      存取，不必記欄位在 tuple 裡的順序。

注意（初學者常見誤解）：
    - `INSERT ... ON CONFLICT ... DO UPDATE` 就是 SQLite 的 upsert 寫法；
      DO UPDATE 子句必須明確列出要更新哪些欄位，不會自動更新全部欄位。
    - sqlite3 預設對同一個連線是序列化執行（一個時間只有一個寫入），
      教學專案的爬蟲是單執行緒依序寫入，不會遇到並發衝突。
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from db.base import StockRepository


def _row_to_dict(row: sqlite3.Row) -> dict:
    """把 sqlite3.Row 轉成一般 dict，方便呼叫端使用與序列化成 JSON。"""
    return dict(row)


class SqliteRepository(StockRepository):
    """StockRepository 的 SQLite 實作。"""

    def __init__(self, db_path: str) -> None:
        """
        參數：
            db_path: SQLite 資料庫檔案路徑（相對或絕對皆可）。

        注意：本建構子不會自動建表，建表由 scripts/init_db.py 負責
        （執行 db/schema_sqlite.sql）。如果檔案或資料表不存在，
        後續操作會直接噴 sqlite3 的錯誤，這是刻意設計——資料庫初始化
        與資料存取是兩個獨立步驟，教學上分開講解比較清楚。
        """
        self.db_path = db_path
        # 確保資料庫檔案所在目錄存在，避免第一次執行時因目錄不存在而失敗。
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        """建立一個新連線，並設定 row_factory 讓查詢結果可轉成 dict。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # 開啟外鍵約束檢查：SQLite 預設不會強制 FOREIGN KEY，需要每個連線手動開啟。
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # ---------------------------------------------------------------
    # stocks
    # ---------------------------------------------------------------
    def upsert_stock(
        self,
        symbol: str,
        name: str,
        market: str | None = None,
        industry: str | None = None,
    ) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO stocks (symbol, name, market, industry)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (symbol) DO UPDATE SET
                    name = excluded.name,
                    market = excluded.market,
                    industry = excluded.industry
                """,
                (symbol, name, market, industry),
            )

    def get_stocks(self) -> list[dict]:
        with closing(self._connect()) as conn, conn:
            rows = conn.execute("SELECT * FROM stocks ORDER BY symbol").fetchall()
            return [_row_to_dict(r) for r in rows]

    # ---------------------------------------------------------------
    # daily_prices
    # ---------------------------------------------------------------
    def upsert_daily_prices(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        with closing(self._connect()) as conn, conn:
            cursor = conn.cursor()
            count = 0
            for row in rows:
                cursor.execute(
                    """
                    INSERT INTO daily_prices (
                        stock_symbol, trade_date, open, high, low, close,
                        volume, turnover, transactions, change
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (stock_symbol, trade_date) DO UPDATE SET
                        open = excluded.open,
                        high = excluded.high,
                        low = excluded.low,
                        close = excluded.close,
                        volume = excluded.volume,
                        turnover = excluded.turnover,
                        transactions = excluded.transactions,
                        change = excluded.change
                    """,
                    (
                        row["stock_symbol"],
                        row["trade_date"],
                        row.get("open"),
                        row.get("high"),
                        row.get("low"),
                        row.get("close"),
                        row.get("volume"),
                        row.get("turnover"),
                        row.get("transactions"),
                        row.get("change"),
                    ),
                )
                count += cursor.rowcount if cursor.rowcount else 0
            return count

    def get_daily_prices(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        query = "SELECT * FROM daily_prices WHERE stock_symbol = ?"
        params: list = [symbol]
        if start is not None:
            query += " AND trade_date >= ?"
            params.append(start)
        if end is not None:
            query += " AND trade_date <= ?"
            params.append(end)
        # 注意：這裡故意先用 DESC 排序＋LIMIT 撈資料，撈完才在 Python 端反轉
        # 回遞增排序（見下方 result.reverse()）。如果直接用 ASC 排序再 LIMIT，
        # 撈到的會是「最舊」的 N 筆，跟 get_news() 的「最新 N 筆」語意不一致，
        # 也不是呼叫端（例如畫折線圖）想要的「最近 N 天」——這是本方法過去
        # 的臭蟲，詳見 db/base.py 的 docstring 說明。
        query += " ORDER BY trade_date DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with closing(self._connect()) as conn, conn:
            rows = conn.execute(query, params).fetchall()
            result = [_row_to_dict(r) for r in rows]
        result.reverse()  # 撈出來是新到舊，反轉回舊到新，符合介面約定的遞增排序
        return result

    def get_latest_price_date(self, symbol: str) -> str | None:
        with closing(self._connect()) as conn, conn:
            row = conn.execute(
                "SELECT MAX(trade_date) AS latest FROM daily_prices WHERE stock_symbol = ?",
                (symbol,),
            ).fetchone()
            return row["latest"] if row else None

    # ---------------------------------------------------------------
    # news
    # ---------------------------------------------------------------
    def upsert_news(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        with closing(self._connect()) as conn, conn:
            cursor = conn.cursor()
            new_count = 0
            for row in rows:
                cursor.execute(
                    """
                    INSERT INTO news (
                        stock_symbol, title, url, source, published_at, summary
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT (url) DO NOTHING
                    """,
                    (
                        row["stock_symbol"],
                        row["title"],
                        row["url"],
                        row.get("source"),
                        row.get("published_at"),
                        row.get("summary"),
                    ),
                )
                # rowcount 在 DO NOTHING 沒有實際插入時會是 0，
                # 這樣就能精準統計「實際新增」的筆數（去重的關鍵）。
                new_count += cursor.rowcount if cursor.rowcount else 0
            return new_count

    def get_news(self, symbol: str, limit: int = 50) -> list[dict]:
        with closing(self._connect()) as conn, conn:
            rows = conn.execute(
                """
                SELECT * FROM news
                WHERE stock_symbol = ?
                ORDER BY published_at DESC
                LIMIT ?
                """,
                (symbol, limit),
            ).fetchall()
            return [_row_to_dict(r) for r in rows]

    # ---------------------------------------------------------------
    # supply_chain
    # ---------------------------------------------------------------
    def upsert_supply_chain(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        with closing(self._connect()) as conn, conn:
            cursor = conn.cursor()
            count = 0
            for row in rows:
                # 注意：segment 為 None 時正規化成空字串 ''，對應 schema 的
                # NOT NULL DEFAULT ''。原因見 db/schema_sqlite.sql 的註解——
                # UNIQUE 約束不比對 NULL，segment 若真的存 NULL 會讓去重失效。
                segment = row.get("segment") or ""
                cursor.execute(
                    """
                    INSERT INTO supply_chain_companies (
                        anchor_symbol, company_name, company_symbol,
                        relation, segment, source_url
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT (anchor_symbol, company_name, segment) DO UPDATE SET
                        company_symbol = excluded.company_symbol,
                        relation = excluded.relation,
                        source_url = excluded.source_url
                    """,
                    (
                        row["anchor_symbol"],
                        row["company_name"],
                        row.get("company_symbol"),
                        row["relation"],
                        segment,
                        row.get("source_url"),
                    ),
                )
                count += cursor.rowcount if cursor.rowcount else 0
            return count

    def get_supply_chain(self, anchor_symbol: str) -> list[dict]:
        with closing(self._connect()) as conn, conn:
            rows = conn.execute(
                """
                SELECT * FROM supply_chain_companies
                WHERE anchor_symbol = ?
                ORDER BY relation, company_name
                """,
                (anchor_symbol,),
            ).fetchall()
            return [_row_to_dict(r) for r in rows]

    # ---------------------------------------------------------------
    # meta
    # ---------------------------------------------------------------
    def get_crawl_summary(self) -> dict:
        with closing(self._connect()) as conn, conn:
            stocks = conn.execute("SELECT COUNT(*) AS c FROM stocks").fetchone()["c"]
            daily_prices = conn.execute(
                "SELECT COUNT(*) AS c FROM daily_prices"
            ).fetchone()["c"]
            news = conn.execute("SELECT COUNT(*) AS c FROM news").fetchone()["c"]
            supply_chain = conn.execute(
                "SELECT COUNT(*) AS c FROM supply_chain_companies"
            ).fetchone()["c"]
            latest_trade_date = conn.execute(
                "SELECT MAX(trade_date) AS latest FROM daily_prices"
            ).fetchone()["latest"]
            latest_news_at = conn.execute(
                "SELECT MAX(published_at) AS latest FROM news"
            ).fetchone()["latest"]
            return {
                "stocks": stocks,
                "daily_prices": daily_prices,
                "news": news,
                "supply_chain": supply_chain,
                "latest_trade_date": latest_trade_date,
                "latest_news_at": latest_news_at,
            }
