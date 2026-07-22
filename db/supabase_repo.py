"""
db/supabase_repo.py — StockRepository 的 Supabase（雲端 PostgreSQL）實作。

做什麼：
    用官方 supabase-py 套件實作 db/base.py 定義的所有介面方法，讓本專案
    未來要換成雲端資料庫時，只要改 .env 的 DB_BACKEND=supabase，
    不用改任何爬蟲或 Dashboard 的程式碼。

為什麼這樣設計：
    - 本專案的教學重點放在「本地端全流程跑通」，所以 Supabase 這條路線
      刻意只做到「程式碼完整可讀、邏輯正確」，不在本專案內實際連線測試。
      要啟用時，先照 db/schema_supabase.sql 在 Supabase SQL Editor 建表，
      再填好 .env 的 SUPABASE_URL / SUPABASE_KEY 即可。
    - supabase-py 的 table().upsert() 底層就是 PostgreSQL 的
      `INSERT ... ON CONFLICT ...`，語意與 sqlite_repo.py 幾乎一致，
      這正是選 SQLite 做本地開發副本的原因——upsert 心智模型可以直接遷移。

注意（初學者常見誤解）：
    - SUPABASE_KEY 建議在後端腳本使用 service_role key（可繞過 Row Level
      Security，適合爬蟲這種可信任的伺服器端流程）；如果是要給瀏覽器前端
      直接呼叫，才使用 anon key 並搭配 RLS 規則限制存取範圍。
      本專案的 Dashboard 一律走 FastAPI 後端代理，不會把任一種 key 曝露給瀏覽器。
    - `.execute()` 的回傳物件是 `APIResponse`，實際資料在 `.data`（list[dict]）。
    - upsert 搭配 `ignore_duplicates=True` 時，衝突的既有列會被「跳過」而不是
      更新，回傳的 `.data` 只包含真正新增的列——這是 news 表用 url 去重、
      且規格要求「回傳實際新增筆數」的關鍵技巧。
"""

from __future__ import annotations

from db.base import StockRepository

try:
    from supabase import Client, create_client
except ImportError:  # pragma: no cover - 套件已在 requirements.txt，理論上不會發生
    Client = None  # type: ignore[assignment,misc]
    create_client = None  # type: ignore[assignment]


class SupabaseRepository(StockRepository):
    """StockRepository 的 Supabase 實作（雲端選項，本專案不實際連線測試）。"""

    def __init__(self, url: str, key: str) -> None:
        """
        參數：
            url: Supabase 專案 URL（config.SUPABASE_URL）。
            key: Supabase API key（config.SUPABASE_KEY，建議 service_role）。
        """
        if create_client is None:
            raise ImportError(
                "supabase 套件未安裝，請先執行 pip install supabase"
            )
        if not url or not key:
            raise ValueError(
                "SUPABASE_URL 與 SUPABASE_KEY 必須都設定才能使用 Supabase 後端，"
                "請檢查 .env 內容"
            )
        self.client: Client = create_client(url, key)

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
        self.client.table("stocks").upsert(
            {"symbol": symbol, "name": name, "market": market, "industry": industry},
            on_conflict="symbol",
        ).execute()

    def get_stocks(self) -> list[dict]:
        response = self.client.table("stocks").select("*").order("symbol").execute()
        return response.data

    # ---------------------------------------------------------------
    # daily_prices
    # ---------------------------------------------------------------
    def upsert_daily_prices(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        payload = [
            {
                "stock_symbol": row["stock_symbol"],
                "trade_date": row["trade_date"],
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
                "volume": row.get("volume"),
                "turnover": row.get("turnover"),
                "transactions": row.get("transactions"),
                "change": row.get("change"),
            }
            for row in rows
        ]
        response = self.client.table("daily_prices").upsert(
            payload, on_conflict="stock_symbol,trade_date"
        ).execute()
        return len(response.data)

    def get_daily_prices(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        query = (
            self.client.table("daily_prices")
            .select("*")
            .eq("stock_symbol", symbol)
        )
        if start is not None:
            query = query.gte("trade_date", start)
        if end is not None:
            query = query.lte("trade_date", end)
        # 注意：跟 sqlite_repo.py 同步的做法——先用 desc=True（新到舊）排序
        # 搭配 limit 撈出「最新 N 筆」，撈完再於 Python 端反轉回遞增排序。
        # 若直接用 desc=False 排序再 limit，撈到的會是「最舊」的 N 筆，
        # 跟 get_news() 的「最新 N 筆」語意不一致，詳見 db/base.py docstring。
        query = query.order("trade_date", desc=True)
        if limit is not None:
            query = query.limit(limit)
        response = query.execute()
        rows = response.data
        rows.reverse()  # 撈出來是新到舊，反轉回舊到新，符合介面約定的遞增排序
        return rows

    def get_latest_price_date(self, symbol: str) -> str | None:
        response = (
            self.client.table("daily_prices")
            .select("trade_date")
            .eq("stock_symbol", symbol)
            .order("trade_date", desc=True)
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        return response.data[0]["trade_date"]

    # ---------------------------------------------------------------
    # news
    # ---------------------------------------------------------------
    def upsert_news(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        payload = [
            {
                "stock_symbol": row["stock_symbol"],
                "title": row["title"],
                "url": row["url"],
                "source": row.get("source"),
                "published_at": row.get("published_at"),
                "summary": row.get("summary"),
            }
            for row in rows
        ]
        # ignore_duplicates=True：url 已存在時整列跳過（不更新），
        # 回傳的 .data 因此只含「真正新增」的列，符合介面「回傳實際新增筆數」的規定。
        response = self.client.table("news").upsert(
            payload, on_conflict="url", ignore_duplicates=True
        ).execute()
        return len(response.data)

    def get_news(self, symbol: str, limit: int = 50) -> list[dict]:
        response = (
            self.client.table("news")
            .select("*")
            .eq("stock_symbol", symbol)
            .order("published_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data

    # ---------------------------------------------------------------
    # supply_chain
    # ---------------------------------------------------------------
    def upsert_supply_chain(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        payload = [
            {
                "anchor_symbol": row["anchor_symbol"],
                "company_name": row["company_name"],
                "company_symbol": row.get("company_symbol"),
                "relation": row["relation"],
                # segment 為 None 時正規化成空字串 ''，對應 schema 的
                # NOT NULL DEFAULT ''，理由與 sqlite_repo.py 相同：
                # UNIQUE 約束不比對 NULL，存 NULL 會讓去重失效。
                "segment": row.get("segment") or "",
                "source_url": row.get("source_url"),
            }
            for row in rows
        ]
        response = self.client.table("supply_chain_companies").upsert(
            payload, on_conflict="anchor_symbol,company_name,segment"
        ).execute()
        return len(response.data)

    def get_supply_chain(self, anchor_symbol: str) -> list[dict]:
        response = (
            self.client.table("supply_chain_companies")
            .select("*")
            .eq("anchor_symbol", anchor_symbol)
            .order("relation")
            .order("company_name")
            .execute()
        )
        return response.data

    # ---------------------------------------------------------------
    # meta
    # ---------------------------------------------------------------
    def get_crawl_summary(self) -> dict:
        def _count(table: str) -> int:
            # head=True：只要求 PostgREST 回傳筆數（透過 Content-Range 標頭），
            # 不把整張表的實際資料一起傳回來。這裡只需要數字，若不加 head=True，
            # select("*", count="exact") 預設仍會把每一列資料都下載一次，
            # 資料量變大時等於白白浪費頻寬與時間。
            response = (
                self.client.table(table)
                .select("*", count="exact", head=True)
                .execute()
            )
            return response.count or 0

        latest_price = (
            self.client.table("daily_prices")
            .select("trade_date")
            .order("trade_date", desc=True)
            .limit(1)
            .execute()
        )
        latest_news = (
            self.client.table("news")
            .select("published_at")
            .order("published_at", desc=True)
            .limit(1)
            .execute()
        )
        return {
            "stocks": _count("stocks"),
            "daily_prices": _count("daily_prices"),
            "news": _count("news"),
            "supply_chain": _count("supply_chain_companies"),
            "latest_trade_date": (
                latest_price.data[0]["trade_date"] if latest_price.data else None
            ),
            "latest_news_at": (
                latest_news.data[0]["published_at"] if latest_news.data else None
            ),
        }
