"""
tests/test_api.py — 驗證 dashboard/app.py 的四支唯讀 API 端點。

涵蓋範圍：每個端點各測「有資料」與「空資料庫」兩種情境。
    - /api/summary：各表筆數、latest_trade_date/latest_news_at 是否正確
    - /api/prices：是否照 trade_date 遞增排序、days 參數是否正確裁切「最近 N 筆」
    - /api/news：是否照 published_at 遞減排序、limit 參數是否生效
    - /api/supply-chain：是否正確依 upstream/midstream/downstream 分組

為什麼一定要測「空資料庫」情境：
    這是唯讀 Dashboard 最容易被忽略、卻最常真實發生的狀態——爬蟲還沒跑過，
    或使用者剛 `scripts/init_db.py` 完就直接開 Dashboard。這個情境下 API
    不該回 500 或噴例外，而是回傳「筆數為 0、清單為空」的合法 JSON，
    讓前端可以判斷並顯示「尚無資料，請先執行爬蟲」，而不是白畫面或報錯畫面。

為什麼不直接打 `data/tsmc.db`（專案真正的資料庫）：
    這個資料庫此刻可能正被並行執行的爬蟲寫入（見任務背景），內容隨時在變，
    拿來當測試依據會讓測試結果不穩定，也可能因為斷言「筆數等於多少」
    而在爬蟲跑到一半時測試失敗。測試改用 tests/conftest.py 的 `repo`
    fixture（每個測試都是全新的暫存 SQLite 檔），完全不受外部爬蟲進度影響。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.app import app, get_repo  # noqa: E402


@pytest.fixture
def client(repo):
    """回傳一個 TestClient，其背後的 repository 已被換成測試用暫存資料庫。

    做什麼＋為什麼：
        用 FastAPI 的 `app.dependency_overrides` 機制，把 dashboard/app.py
        裡的 `get_repo` 依賴換成「直接回傳 conftest.py 的 repo fixture」。
        這樣呼叫任何 API 端點時，FastAPI 背後實際用的就是這個乾淨的暫存
        SQLite，而不是 `db.factory.get_repository()` 預設指向的正式資料庫。

    注意（初學者常見誤解）：
        測試結束後一定要呼叫 `app.dependency_overrides.clear()`，否則這個
        override 會殘留在 `app` 這個全域物件上，汙染同一個 pytest 執行程序
        裡「後面」才跑的其他測試（例如讓它們也錯誤地連到已經被丟棄的暫存檔）。
    """
    app.dependency_overrides[get_repo] = lambda: repo
    yield TestClient(app)
    app.dependency_overrides.clear()


def _price_row(trade_date: str, close: float = 600.0, symbol: str = "2330") -> dict:
    return {
        "stock_symbol": symbol,
        "trade_date": trade_date,
        "open": close - 5,
        "high": close + 10,
        "low": close - 10,
        "close": close,
        "volume": 20000000,
        "turnover": 12000000000,
        "transactions": 40000,
        "change": 3.5,
    }


# ---------------------------------------------------------------------------
# /api/summary
# ---------------------------------------------------------------------------
def test_summary_empty_db_returns_zero_counts(client):
    response = client.get("/api/summary")
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "stocks": 0,
        "daily_prices": 0,
        "news": 0,
        "supply_chain": 0,
        "latest_trade_date": None,
        "latest_news_at": None,
    }


def test_summary_with_data_returns_correct_counts(client, repo):
    repo.upsert_stock(symbol="2330", name="台積電", market="上市", industry="半導體")
    repo.upsert_daily_prices([_price_row("2026-07-01"), _price_row("2026-07-02")])
    repo.upsert_news(
        [
            {
                "stock_symbol": "2330",
                "title": "台積電法說會重點",
                "url": "https://example.com/news/1",
                "source": "鉅亨網",
                "published_at": "2026-07-02T09:00:00+08:00",
                "summary": "摘要內容",
            }
        ]
    )
    repo.upsert_supply_chain(
        [
            {
                "anchor_symbol": "2330",
                "company_name": "日月光投控",
                "company_symbol": "3711",
                "relation": "downstream",
                "segment": "封測",
                "source_url": "https://ic.tpex.org.tw/introduce.php?ic=D000",
            }
        ]
    )

    body = client.get("/api/summary").json()
    assert body["stocks"] == 1
    assert body["daily_prices"] == 2
    assert body["news"] == 1
    assert body["supply_chain"] == 1
    assert body["latest_trade_date"] == "2026-07-02"
    assert body["latest_news_at"] == "2026-07-02T09:00:00+08:00"


# ---------------------------------------------------------------------------
# /api/prices
# ---------------------------------------------------------------------------
def test_prices_empty_db_returns_empty_list(client):
    response = client.get("/api/prices?symbol=2330&days=90")
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "2330"
    assert body["prices"] == []


def test_prices_with_data_sorted_ascending(client, repo):
    repo.upsert_stock(symbol="2330", name="台積電")
    repo.upsert_daily_prices(
        [
            _price_row("2026-07-03", close=610.0),
            _price_row("2026-07-01", close=600.0),
            _price_row("2026-07-02", close=605.0),
        ]
    )

    body = client.get("/api/prices?symbol=2330&days=90").json()
    dates = [row["trade_date"] for row in body["prices"]]
    assert dates == ["2026-07-01", "2026-07-02", "2026-07-03"]


def test_prices_days_param_keeps_only_most_recent_n(client, repo):
    repo.upsert_stock(symbol="2330", name="台積電")
    repo.upsert_daily_prices(
        [_price_row(d) for d in ["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-04"]]
    )

    body = client.get("/api/prices?symbol=2330&days=2").json()
    dates = [row["trade_date"] for row in body["prices"]]
    # days=2 應該取「最新」的兩筆，不是最舊的兩筆。
    assert dates == ["2026-07-03", "2026-07-04"]


# ---------------------------------------------------------------------------
# /api/news
# ---------------------------------------------------------------------------
def test_news_empty_db_returns_empty_list(client):
    response = client.get("/api/news?symbol=2330&limit=30")
    assert response.status_code == 200
    assert response.json()["news"] == []


def test_news_with_data_sorted_descending_and_limited(client, repo):
    repo.upsert_stock(symbol="2330", name="台積電")
    repo.upsert_news(
        [
            {
                "stock_symbol": "2330",
                "title": "新聞A",
                "url": "https://example.com/a",
                "source": "鉅亨網",
                "published_at": "2026-07-01T08:00:00+08:00",
                "summary": "摘要A",
            },
            {
                "stock_symbol": "2330",
                "title": "新聞B",
                "url": "https://example.com/b",
                "source": "鉅亨網",
                "published_at": "2026-07-03T08:00:00+08:00",
                "summary": "摘要B",
            },
        ]
    )

    body = client.get("/api/news?symbol=2330&limit=1").json()
    assert len(body["news"]) == 1
    assert body["news"][0]["title"] == "新聞B"  # 最新一則排最前面


# ---------------------------------------------------------------------------
# /api/supply-chain
# ---------------------------------------------------------------------------
def test_supply_chain_empty_db_returns_empty_groups(client):
    response = client.get("/api/supply-chain?symbol=2330")
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "symbol": "2330",
        "upstream": [],
        "midstream": [],
        "downstream": [],
    }


def test_supply_chain_with_data_grouped_by_relation(client, repo):
    repo.upsert_stock(symbol="2330", name="台積電")
    repo.upsert_supply_chain(
        [
            {
                "anchor_symbol": "2330",
                "company_name": "世界先進",
                "company_symbol": "5347",
                "relation": "upstream",
                "segment": "IP 設計",
                "source_url": "https://ic.tpex.org.tw/introduce.php?ic=D000",
            },
            {
                "anchor_symbol": "2330",
                "company_name": "日月光投控",
                "company_symbol": "3711",
                "relation": "downstream",
                "segment": "封測",
                "source_url": "https://ic.tpex.org.tw/introduce.php?ic=D000",
            },
        ]
    )

    body = client.get("/api/supply-chain?symbol=2330").json()
    assert len(body["upstream"]) == 1
    assert body["upstream"][0]["company_name"] == "世界先進"
    assert len(body["downstream"]) == 1
    assert body["downstream"][0]["company_name"] == "日月光投控"
    assert body["midstream"] == []


# ---------------------------------------------------------------------------
# `/` 靜態頁面
# ---------------------------------------------------------------------------
def test_root_serves_index_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
