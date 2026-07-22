"""
tests/test_repository.py — 驗證 SqliteRepository 完整實作 StockRepository 介面。

涵蓋範圍（對照 db/base.py 的每個方法）：
    - stocks：upsert 去重（同 symbol 更新而非新增）＋ get_stocks
    - daily_prices：upsert 去重（同 stock_symbol+trade_date）＋ 遞增排序＋ checkpoint
    - news：upsert 以 url 去重＋ 遞減排序
    - supply_chain：upsert 以 (anchor_symbol, company_name, segment) 去重
    - get_crawl_summary：各表筆數與最新日期彙總

為什麼這樣設計：
    每個測試只驗證一件事（單一職責），測試名稱直接說明「驗證什麼行為」，
    這樣測試失敗時一看名稱就知道是哪個介面契約被打破，方便之後三支爬蟲
    的 agent 接手時，能用這份測試快速確認自己沒有誤用 repository 介面。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------
# stocks
# ---------------------------------------------------------------
def test_upsert_stock_then_get_stocks(repo):
    repo.upsert_stock(symbol="2330", name="台積電", market="上市", industry="半導體")
    stocks = repo.get_stocks()
    assert len(stocks) == 1
    assert stocks[0]["symbol"] == "2330"
    assert stocks[0]["name"] == "台積電"
    assert stocks[0]["market"] == "上市"
    assert stocks[0]["industry"] == "半導體"


def test_upsert_stock_same_symbol_updates_not_duplicates(repo):
    repo.upsert_stock(symbol="2330", name="台積電", market="上市", industry="半導體")
    # 第二次呼叫同一個 symbol，name 故意打錯字再修正，驗證是「更新」而非新增一列。
    repo.upsert_stock(symbol="2330", name="台積電股份有限公司", market="上市", industry="半導體")

    stocks = repo.get_stocks()
    assert len(stocks) == 1
    assert stocks[0]["name"] == "台積電股份有限公司"


# ---------------------------------------------------------------
# daily_prices
# ---------------------------------------------------------------
def _price_row(trade_date: str, close: float = 1000.0, symbol: str = "2330") -> dict:
    return {
        "stock_symbol": symbol,
        "trade_date": trade_date,
        "open": close - 5,
        "high": close + 10,
        "low": close - 10,
        "close": close,
        "volume": 30000000,
        "turnover": 30000000000,
        "transactions": 50000,
        "change": 5.0,
    }


def test_upsert_daily_prices_dedup_by_symbol_and_date(repo):
    repo.upsert_stock(symbol="2330", name="台積電")

    written_1 = repo.upsert_daily_prices([_price_row("2026-07-01", close=1000.0)])
    assert written_1 == 1

    # 同一天再匯入一次，收盤價不同：應該是「更新」，不是新增一列。
    written_2 = repo.upsert_daily_prices([_price_row("2026-07-01", close=1050.0)])
    assert written_2 == 1

    rows = repo.get_daily_prices("2330")
    assert len(rows) == 1
    assert rows[0]["close"] == 1050.0


def test_get_daily_prices_sorted_ascending_by_trade_date(repo):
    repo.upsert_stock(symbol="2330", name="台積電")
    repo.upsert_daily_prices(
        [
            _price_row("2026-07-03"),
            _price_row("2026-07-01"),
            _price_row("2026-07-02"),
        ]
    )

    rows = repo.get_daily_prices("2330")
    dates = [r["trade_date"] for r in rows]
    assert dates == ["2026-07-01", "2026-07-02", "2026-07-03"]


def test_get_daily_prices_start_end_and_limit(repo):
    repo.upsert_stock(symbol="2330", name="台積電")
    for day in ["01", "02", "03", "04", "05"]:
        repo.upsert_daily_prices([_price_row(f"2026-07-{day}")])

    ranged = repo.get_daily_prices("2330", start="2026-07-02", end="2026-07-04")
    assert [r["trade_date"] for r in ranged] == [
        "2026-07-02",
        "2026-07-03",
        "2026-07-04",
    ]

    # limit 的語意是「最新 N 筆」，取完之後仍依 trade_date 遞增排序回傳
    # （對照 db/base.py 的 get_daily_prices docstring，與 get_news() 的
    # 「最新 N 筆」語意一致，不是「最舊 N 筆」）。
    limited = repo.get_daily_prices("2330", limit=2)
    assert [r["trade_date"] for r in limited] == ["2026-07-04", "2026-07-05"]


def test_get_daily_prices_limit_is_latest_n_within_start_end_range(repo):
    repo.upsert_stock(symbol="2330", name="台積電")
    for day in ["01", "02", "03", "04", "05"]:
        repo.upsert_daily_prices([_price_row(f"2026-07-{day}")])

    # start/end 先把範圍限縮到 07-01 ~ 07-03，limit=2 取的應該是這個範圍內
    # 「最新」的 2 筆（07-02、07-03），不是全表最新的 2 筆。
    rows = repo.get_daily_prices("2330", start="2026-07-01", end="2026-07-03", limit=2)
    assert [r["trade_date"] for r in rows] == ["2026-07-02", "2026-07-03"]


def test_get_latest_price_date(repo):
    repo.upsert_stock(symbol="2330", name="台積電")
    assert repo.get_latest_price_date("2330") is None

    repo.upsert_daily_prices(
        [_price_row("2026-07-01"), _price_row("2026-07-05"), _price_row("2026-07-03")]
    )
    assert repo.get_latest_price_date("2330") == "2026-07-05"


# ---------------------------------------------------------------
# news
# ---------------------------------------------------------------
def _news_row(url: str, published_at: str, title: str = "台積電新聞") -> dict:
    return {
        "stock_symbol": "2330",
        "title": title,
        "url": url,
        "source": "鉅亨網",
        "published_at": published_at,
        "summary": "摘要內容",
    }


def test_upsert_news_dedup_by_url(repo):
    repo.upsert_stock(symbol="2330", name="台積電")

    written_1 = repo.upsert_news(
        [_news_row("https://news.example.com/a", "2026-07-01T09:00:00")]
    )
    assert written_1 == 1

    # 同一個 url 再匯入一次：不該計入新增筆數，也不該產生第二列。
    written_2 = repo.upsert_news(
        [_news_row("https://news.example.com/a", "2026-07-01T09:00:00")]
    )
    assert written_2 == 0

    rows = repo.get_news("2330")
    assert len(rows) == 1


def test_get_news_sorted_descending_by_published_at(repo):
    repo.upsert_stock(symbol="2330", name="台積電")
    repo.upsert_news(
        [
            _news_row("https://news.example.com/1", "2026-07-01T09:00:00"),
            _news_row("https://news.example.com/2", "2026-07-03T09:00:00"),
            _news_row("https://news.example.com/3", "2026-07-02T09:00:00"),
        ]
    )

    rows = repo.get_news("2330")
    published = [r["published_at"] for r in rows]
    assert published == [
        "2026-07-03T09:00:00",
        "2026-07-02T09:00:00",
        "2026-07-01T09:00:00",
    ]


def test_get_news_respects_limit(repo):
    repo.upsert_stock(symbol="2330", name="台積電")
    repo.upsert_news(
        [
            _news_row(f"https://news.example.com/{i}", f"2026-07-0{i}T09:00:00")
            for i in range(1, 6)
        ]
    )
    rows = repo.get_news("2330", limit=2)
    assert len(rows) == 2


# ---------------------------------------------------------------
# supply_chain
# ---------------------------------------------------------------
def _supply_chain_row(company_name: str, segment: str = "設備") -> dict:
    return {
        "anchor_symbol": "2330",
        "company_name": company_name,
        "company_symbol": None,
        "relation": "upstream",
        "segment": segment,
        "source_url": "https://ic.tpex.org.tw/introduce.php?ic=D000",
    }


def test_upsert_supply_chain_dedup_by_anchor_name_segment(repo):
    repo.upsert_stock(symbol="2330", name="台積電")

    written_1 = repo.upsert_supply_chain([_supply_chain_row("應用材料")])
    assert written_1 == 1

    written_2 = repo.upsert_supply_chain([_supply_chain_row("應用材料")])
    assert written_2 == 1  # 同鍵值再次 upsert 視為更新，仍算「寫入」

    rows = repo.get_supply_chain("2330")
    assert len(rows) == 1


def test_upsert_supply_chain_none_segment_dedups_not_duplicates(repo):
    """segment=None 的列重複 upsert 不該膨脹（回歸測試，對應 schema 的
    UNIQUE (anchor_symbol, company_name, segment)：SQLite/PostgreSQL 的
    UNIQUE 都不比對 NULL，若 segment 真的存 NULL 會導致每次 upsert 都被
    當成新列插入。repository 必須把 None 正規化成空字串 '' 才能讓 UNIQUE
    生效。"""
    repo.upsert_stock(symbol="2330", name="台積電")

    row = _supply_chain_row("應用材料")
    row["segment"] = None

    written_1 = repo.upsert_supply_chain([row])
    assert written_1 == 1

    written_2 = repo.upsert_supply_chain([row])
    assert written_2 == 1  # 同鍵值再次 upsert 視為更新，仍算「寫入」

    written_3 = repo.upsert_supply_chain([row])
    assert written_3 == 1

    rows = repo.get_supply_chain("2330")
    assert len(rows) == 1  # 沒有膨脹成 3 列
    assert rows[0]["segment"] == ""


def test_get_supply_chain_returns_all_companies(repo):
    repo.upsert_stock(symbol="2330", name="台積電")
    repo.upsert_supply_chain(
        [
            _supply_chain_row("應用材料", segment="設備"),
            _supply_chain_row("信紘科", segment="材料"),
        ]
    )
    rows = repo.get_supply_chain("2330")
    names = {r["company_name"] for r in rows}
    assert names == {"應用材料", "信紘科"}


# ---------------------------------------------------------------
# meta：get_crawl_summary
# ---------------------------------------------------------------
def test_get_crawl_summary_empty(repo):
    summary = repo.get_crawl_summary()
    assert summary == {
        "stocks": 0,
        "daily_prices": 0,
        "news": 0,
        "supply_chain": 0,
        "latest_trade_date": None,
        "latest_news_at": None,
    }


def test_get_crawl_summary_with_data(repo):
    repo.upsert_stock(symbol="2330", name="台積電")
    repo.upsert_daily_prices([_price_row("2026-07-01"), _price_row("2026-07-02")])
    repo.upsert_news(
        [
            _news_row("https://news.example.com/1", "2026-07-01T09:00:00"),
            _news_row("https://news.example.com/2", "2026-07-02T09:00:00"),
        ]
    )
    repo.upsert_supply_chain([_supply_chain_row("應用材料")])

    summary = repo.get_crawl_summary()
    assert summary["stocks"] == 1
    assert summary["daily_prices"] == 2
    assert summary["news"] == 2
    assert summary["supply_chain"] == 1
    assert summary["latest_trade_date"] == "2026-07-02"
    assert summary["latest_news_at"] == "2026-07-02T09:00:00"


# ---------------------------------------------------------------
# config.SQLITE_PATH：相對路徑要 resolve 到專案根目錄，不受 cwd 影響
# ---------------------------------------------------------------
def test_sqlite_path_resolves_to_project_root_regardless_of_cwd(tmp_path):
    """從專案根目錄以外的 cwd 匯入 config 模組，SQLITE_PATH 仍要落在
    專案根目錄底下，不能因為換了執行目錄就在別處生出第二份 db 檔
    （回歸測試：config.py 過去用 os.getenv() 直接存相對路徑字串，
    「相對於誰」取決於程式執行當下的 cwd，而不是專案根目錄）。
    """
    project_root = Path(__file__).resolve().parent.parent
    other_cwd = tmp_path  # 一個跟本專案完全無關的目錄，模擬「換目錄執行」

    env = dict(os.environ)
    env.pop("SQLITE_PATH", None)  # 避免使用者環境變數干擾這次驗證
    env["PYTHONPATH"] = str(project_root)

    result = subprocess.run(
        [sys.executable, "-c", "import config; print(config.SQLITE_PATH)"],
        cwd=other_cwd,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    resolved = Path(result.stdout.strip())
    assert resolved.is_absolute()
    # 預設值 "data/tsmc.db" resolve 後應該是 <專案根目錄>/data/tsmc.db，
    # 不是 <other_cwd>/data/tsmc.db。
    assert resolved == project_root / "data" / "tsmc.db"
