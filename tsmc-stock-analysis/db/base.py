"""
db/base.py — 資料存取層的抽象介面（StockRepository）。

做什麼：
    定義所有資料庫操作必須實作的方法清單（ABC = Abstract Base Class）。
    `db/sqlite_repo.py` 與 `db/supabase_repo.py` 都繼承這個類別，各自實作
    同一組方法，但底層存取的資料庫不同。

為什麼這樣設計（repository pattern）：
    爬蟲層（crawlers/）與 Dashboard 層（dashboard/）永遠只呼叫這裡定義的方法，
    完全不知道、也不需要知道背後是 SQLite 還是 Supabase。這樣的好處：
    1. 抽換資料庫（例如教學專案想改示範 Supabase）只要換一個 repository 實作，
       呼叫端一行都不用改。
    2. 寫測試時可以用 SQLite 的暫存檔快速驗證邏輯，不必依賴雲端服務。
    3. 介面即合約——本檔案的方法簽名是整個專案所有 agent 的共同依據，
       任何一方偏離都會讓其他人的程式碼壞掉，所以簽名禁止隨意更動。

注意（初學者常見誤解）：
    ABC 本身不能被實例化（`StockRepository()` 會直接噴錯），
    一定要透過 `db.factory.get_repository()` 拿到「真正的」實作物件。
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class StockRepository(ABC):
    """所有資料庫實作共同遵守的抽象介面。"""

    # ---------------------------------------------------------------
    # stocks：股票基本資料
    # ---------------------------------------------------------------
    @abstractmethod
    def upsert_stock(
        self,
        symbol: str,
        name: str,
        market: str | None = None,
        industry: str | None = None,
    ) -> None:
        """新增或更新一檔股票的基本資料（以 symbol 為主鍵，已存在則更新）。"""
        raise NotImplementedError

    @abstractmethod
    def get_stocks(self) -> list[dict]:
        """回傳所有股票的基本資料清單。"""
        raise NotImplementedError

    # ---------------------------------------------------------------
    # daily_prices：每日股價
    # ---------------------------------------------------------------
    @abstractmethod
    def upsert_daily_prices(self, rows: list[dict]) -> int:
        """批次新增或更新每日股價。

        rows 每筆字典需包含以下 key：
            stock_symbol, trade_date(YYYY-MM-DD), open, high, low, close,
            volume, turnover, transactions, change

        以 (stock_symbol, trade_date) 為唯一鍵去重 upsert：同一天同一檔股票
        的資料若重複匯入，後面的會覆蓋前面的，不會產生重複列。

        回傳：實際寫入（新增或更新）的筆數。
        """
        raise NotImplementedError

    @abstractmethod
    def get_daily_prices(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """回傳指定股票的每日股價，結果一律依 trade_date 遞增排序（舊到新）。

        start/end 可用來限制日期區間（含端點）。

        limit 的語意（與 get_news() 的「最新 N 筆」一致，注意不要搞混）：
            取的是「最新的 N 筆」，不是「最舊的 N 筆」——先在 start/end
            篩選過的範圍內找出最新 N 筆，再把這 N 筆依 trade_date 遞增排序
            後回傳。這樣呼叫端（例如畫折線圖）永遠拿到「舊到新排好的最近
            N 天資料」，不需要自己再排序一次；如果 limit 語意是「最舊 N
            筆」，呼叫端要嘛看到的是很久以前的資料、要嘛得自己在外面反轉
            排序再切片，兩種都容易寫錯，這是初學者常踩的坑。
        """
        raise NotImplementedError

    @abstractmethod
    def get_latest_price_date(self, symbol: str) -> str | None:
        """回傳指定股票目前已存最新的交易日期（checkpoint 用途）。

        爬蟲每次執行前會先呼叫這個方法，知道「上次抓到哪一天」，
        就不用每次都從頭重抓，這是「增量爬取」的核心機制。
        沒有任何資料時回傳 None。
        """
        raise NotImplementedError

    # ---------------------------------------------------------------
    # news：新聞
    # ---------------------------------------------------------------
    @abstractmethod
    def upsert_news(self, rows: list[dict]) -> int:
        """批次新增新聞（以 url 為唯一鍵去重，已存在的 url 不會重複新增）。

        rows 每筆字典需包含以下 key：
            stock_symbol, title, url, source, published_at(ISO8601), summary

        回傳：實際新增的筆數（已存在的 url 不計入）。
        """
        raise NotImplementedError

    @abstractmethod
    def get_news(self, symbol: str, limit: int = 50) -> list[dict]:
        """依 published_at 遞減排序（最新在前）回傳指定股票的新聞。"""
        raise NotImplementedError

    # ---------------------------------------------------------------
    # supply_chain：上下游供應鏈
    # ---------------------------------------------------------------
    @abstractmethod
    def upsert_supply_chain(self, rows: list[dict]) -> int:
        """批次新增或更新供應鏈公司資料。

        rows 每筆字典需包含以下 key：
            anchor_symbol, company_name, company_symbol(可 None),
            relation(upstream/midstream/downstream), segment, source_url

        以 (anchor_symbol, company_name, segment) 為唯一鍵去重 upsert。

        注意：segment 為 None 時，實作必須正規化成空字串 '' 再寫入
        （對應 schema 的 NOT NULL DEFAULT ''）。這是因為 SQLite／PostgreSQL
        的 UNIQUE 約束都不比對 NULL（NULL 與任何值都不相等，包含 NULL
        自己），segment 若真的存 NULL，UNIQUE (anchor_symbol, company_name,
        segment) 就會對「沒有 segment」的列完全失去去重效果，重複爬取會
        讓這張表無限膨脹。

        回傳：實際寫入（新增或更新）的筆數。
        """
        raise NotImplementedError

    @abstractmethod
    def get_supply_chain(self, anchor_symbol: str) -> list[dict]:
        """回傳指定股票的所有上下游供應鏈公司資料。"""
        raise NotImplementedError

    # ---------------------------------------------------------------
    # meta：統計摘要
    # ---------------------------------------------------------------
    @abstractmethod
    def get_crawl_summary(self) -> dict:
        """回傳各資料表的統計摘要，供 Dashboard 首頁顯示。

        回傳格式固定為：
            {"stocks": n, "daily_prices": n, "news": n, "supply_chain": n,
             "latest_trade_date": str|None, "latest_news_at": str|None}
        """
        raise NotImplementedError
