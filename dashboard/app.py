"""
dashboard/app.py — 唯讀 Dashboard 的 FastAPI 應用程式。

做什麼：
    提供四支唯讀 API（/api/summary、/api/prices、/api/news、/api/supply-chain），
    並在根目錄 `/` 服務 dashboard/static/ 底下的靜態前端頁面（index.html/style.css/main.js）。

為什麼這樣設計（唯讀邊界）：
    整份檔案裡完全沒有呼叫 repository 的任何 upsert_* 方法，只呼叫 get_*。
    這不是巧合，是刻意的架構分工（見規格書 §1）：
        [爬蟲層] 負責寫入資料庫；[Dashboard 層] 只負責讀出來顯示。
    兩層完全不共用程式流程，只透過資料庫（經 db/ 的 repository 介面）間接溝通。
    這樣的好處是：就算 Dashboard 的程式碼有 bug，也不可能不小心把資料庫寫壞——
    因為它手上根本沒有「寫」的能力。

為什麼用 FastAPI 的 Depends() 注入 repository，而不是在每個函式裡直接呼叫
`get_repository()`：
    測試（tests/test_api.py）需要讓 API 讀到一個「乾淨、獨立」的暫存資料庫，
    而不是專案真正的 data/tsmc.db（否則測試結果會受到爬蟲進度影響，
    也可能不小心汙染正式資料）。用 Depends() 注入，測試就能透過
    `app.dependency_overrides[get_repo] = ...` 換掉底層的資料庫，
    完全不用改 app.py 裡任何一行邏輯——這正是 repository pattern 帶來的彈性。

注意（初學者常見誤解）：
    `get_repo()` 每次被呼叫都會重新走一次 `db.factory.get_repository()`，
    不是全域共用同一個連線。SQLite 是短連線設計（見 db/sqlite_repo.py 的說明），
    這裡沿用同樣的原則，不額外維護長駐連線。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Query
from fastapi.staticfiles import StaticFiles

from db.base import StockRepository
from db.factory import get_repository

# 台積電是本教學專案唯一收錄的股票，所有查詢參數的預設值都指向它，
# 方便學員直接開瀏覽器打 API 也能看到資料，不必先查代號。
DEFAULT_SYMBOL = "2330"

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="台積電股票分析 Dashboard",
    description="唯讀 API：僅呼叫 db repository 的 get_* 方法，不做任何寫入。",
)


def get_repo() -> StockRepository:
    """FastAPI 依賴注入用：回傳一個 StockRepository 實例。

    做什麼＋為什麼：
        預設走 `db.factory.get_repository()`（依 config.DB_BACKEND 決定實際
        接哪個資料庫）。測試時會用 `app.dependency_overrides` 把這個函式換成
        另一個回傳「測試用暫存資料庫」的函式，詳見 tests/test_api.py。
    """
    return get_repository()


# ---------------------------------------------------------------------------
# API 端點（全部唯讀：只呼叫 repo 的 get_* 方法）
# ---------------------------------------------------------------------------
@app.get("/api/summary")
def api_summary(repo: StockRepository = Depends(get_repo)) -> dict:
    """回傳各資料表的統計摘要，供首頁 stat tiles 與「最後更新時間」使用。

    直接回傳 repo.get_crawl_summary() 的結果，不額外加工——
    格式已在 db/base.py 定義死（stocks/daily_prices/news/supply_chain 筆數
    ＋ latest_trade_date/latest_news_at），前端照這個固定格式取值即可。
    """
    return repo.get_crawl_summary()


@app.get("/api/prices")
def api_prices(
    symbol: str = Query(DEFAULT_SYMBOL, description="股票代號，如 2330"),
    days: int = Query(90, ge=1, le=3650, description="回傳最近幾天的資料"),
    repo: StockRepository = Depends(get_repo),
) -> dict:
    """回傳指定股票「最近 N 天」的每日股價（供折線圖／長條圖使用）。

    做什麼：
        repo.get_daily_prices(symbol) 依規格（db/base.py）固定回傳「依 trade_date
        遞增排序」的整段歷史，本身不支援「只拿最近 N 天」的查詢方式——它的
        limit 參數搭配遞增排序，取到的會是「最舊」的 N 筆，不是最新的 N 筆。

    為什麼用 Python slice `rows[-days:]` 而不是傳 limit 或用日期區間過濾：
        1. 避免重新推導「今天日期 - N 天」再轉字串比對 trade_date 的邏輯，
           不需要處理交易日與日曆天數不一致的問題（股市週末、國定假日不開盤）。
        2. repository 回傳的資料本來就已經是遞增排序好的，直接對這個
           list 做「取最後 N 筆」是最直覺、最不容易寫錯的做法。
        3. 教學專案資料量小（一檔股票、頂多幾年資料），先整段抓出來再切片，
           效能上完全沒有問題；大型專案才需要在資料庫層做分頁最佳化。
    """
    rows = repo.get_daily_prices(symbol)
    if days and len(rows) > days:
        rows = rows[-days:]
    return {"symbol": symbol, "days": days, "prices": rows}


@app.get("/api/news")
def api_news(
    symbol: str = Query(DEFAULT_SYMBOL, description="股票代號，如 2330"),
    limit: int = Query(30, ge=1, le=200, description="回傳最多幾則新聞"),
    repo: StockRepository = Depends(get_repo),
) -> dict:
    """回傳指定股票最新的新聞列表（published_at 遞減，最新在前）。"""
    rows = repo.get_news(symbol, limit=limit)
    return {"symbol": symbol, "news": rows}


@app.get("/api/supply-chain")
def api_supply_chain(
    symbol: str = Query(DEFAULT_SYMBOL, description="股票代號，如 2330"),
    repo: StockRepository = Depends(get_repo),
) -> dict:
    """回傳指定股票的上下游供應鏈公司，依 upstream/midstream/downstream 分組。

    為什麼在這裡分組（而不是回傳原始平坦 list 讓前端自己分）：
        前端要畫「上/中/下游三欄 grid」，在 API 層就依 relation 分好三組，
        前端拿到就能直接對應三欄渲染，不用重複寫一次分組邏輯——
        後端只需要寫一次，前端邏輯自然變簡單。
    """
    rows = repo.get_supply_chain(symbol)
    grouped: dict[str, list[dict]] = {
        "upstream": [],
        "midstream": [],
        "downstream": [],
    }
    for row in rows:
        relation = row.get("relation")
        # 注意：只收 relation 剛好是三種預期值之一的資料；如果資料庫裡
        # 出現非預期的 relation 字串（理論上不該發生，因為 schema 已限制
        # 只有三種寫法會被爬蟲寫入），這裡選擇安靜跳過而不是噴錯——
        # Dashboard 是唯讀展示層，不該因為一筆髒資料整頁掛掉。
        if relation in grouped:
            grouped[relation].append(row)
    return {"symbol": symbol, **grouped}


# ---------------------------------------------------------------------------
# 靜態前端頁面：`/` 與其他非 /api 路徑一律交給 dashboard/static/ 底下的檔案。
#
# 注意：這一段必須寫在所有 @app.get(...) 路由「之後」。FastAPI（背後是
# Starlette）比對路由時依「註冊順序」由上而下找第一個相符的規則，
# StaticFiles 掛載在 "/" 會比對到任何路徑；如果寫在 /api/* 路由「之前」，
# 所有 /api/* 請求都會先被這個掛載點攔截，變成找靜態檔案找不到而回 404。
# ---------------------------------------------------------------------------
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
