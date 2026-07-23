# DEVELOPMENT.md — 開發者／AI 技術文件

本文件給要修改、擴充這個專案的人（包含未來接手的 AI agent）看，說明架構、
資料流、每一層的介面合約，以及「新增一支爬蟲」「新增一種資料庫後端」這類
常見擴充工作的具體步驟。使用者導向的安裝與操作說明請看
[README.md](README.md)。

本文件所有內容以**實際程式碼為準**：如果你發現這裡寫的跟程式碼對不上，
以程式碼為準，並回頭更新這份文件（不要憑這份文件去猜程式碼「應該」長怎樣）。

作者：呂紹民（Darren Lu）。對本專案有任何問題，或有專案導入、教學、諮詢需求，
歡迎聯絡：kevin868686@gmail.com（其他聯絡方式見 [README.md](README.md)）。

---

## 目錄

1. [專案結構與各資料夾用途](#專案結構與各資料夾用途)
2. [資料流](#資料流)
3. [repository 介面說明](#repository-介面說明)
4. [如何新增一種資料庫後端](#如何新增一種資料庫後端)
5. [如何新增一支爬蟲＋一張表](#如何新增一支爬蟲一張表)
6. [測試怎麼跑](#測試怎麼跑)
7. [程式慣例](#程式慣例)

---

## 專案結構與各資料夾用途

```
config.py           全域設定：讀 .env，提供 DB_BACKEND / SQLITE_PATH /
                     SUPABASE_URL / SUPABASE_KEY 給其他模組 import 使用。
db/                  資料存取層。所有跟「資料庫」有關的程式碼都在這裡，
                     其他層（crawlers/、dashboard/）不會直接寫 SQL 或呼叫
                     sqlite3 / supabase-py，只透過這一層定義的介面存取。
scripts/             一次性或排程用的執行腳本（建表/seed、跑全部爬蟲）。
crawlers/            三支爬蟲＋共用工具。每支爬蟲都是可以獨立執行的腳本，
                     彼此不互相 import，只共用 crawlers/common.py。
dashboard/           唯讀的 FastAPI 應用程式＋原生 HTML/CSS/JS 前端。
                     只呼叫 db/ 的 get_* 方法，程式碼裡完全沒有任何
                     upsert_* 呼叫（見下方〈資料流〉的唯讀邊界說明）。
tests/               pytest 測試，檔案與 crawlers/、db/、dashboard/ 一一對應。
logs/                爬蟲與排程執行的 log 檔（crawler.log），已 gitignore。
data/                SQLite 資料庫檔（tsmc.db），已 gitignore。
```

**注意（`.env` 與 shell 環境變數的優先權）**：`config.py` 用 `load_dotenv(override=False)` 載入
`.env`，`override=False` 代表如果 shell 環境已經有同名變數，shell 的值會贏過 `.env` 檔案裡寫的值，
`.env` 只補上 shell 沒設定的那些。CI／測試環境常會用這個特性：直接在執行環境設定 `DB_BACKEND` 等
環境變數蓋過 `.env`，不需要為每個環境各自維護一份不同的 `.env` 檔案。

`db/` 底下各檔案的角色（細節見下一節「repository 介面說明」）：

| 檔案 | 角色 |
|---|---|
| `db/base.py` | `StockRepository` 抽象基底類別（ABC）：定義所有資料庫操作的方法簽名，是整個專案的合約。 |
| `db/factory.py` | `get_repository()`：讀 `config.DB_BACKEND`，回傳對應的實作物件。是呼叫端唯一應該 import 的入口。 |
| `db/sqlite_repo.py` | `SqliteRepository`：用標準庫 `sqlite3` 實作，唯一實際驗證過的後端。 |
| `db/supabase_repo.py` | `SupabaseRepository`：用 `supabase-py` 實作，程式完整可讀，未實際連線測試。 |
| `db/schema_sqlite.sql` / `db/schema_supabase.sql` | 兩種資料庫的建表 SQL，資料模型（欄位、型別、UNIQUE 鍵）刻意保持同構，只有型別語法因資料庫而異。 |

`crawlers/` 底下每支爬蟲的共同結構（新增第四支爬蟲時應該照這個模式寫）：

1. 檔案最上方一段「清理／解析純函式」——輸入是原始資料（字串、HTML），輸出是
   乾淨的值或 dict，完全不碰網路或資料庫，方便用固定 fixture 單獨測試。
2. 中間是「抓取（I/O）」函式——實際發 HTTP 請求或開瀏覽器，呼叫
   `crawlers/common.py` 的 `check_robots_allowed()` / `polite_get()`。
3. 最下面是「主流程」函式（如 `crawl()` / `crawl_news()` / `run()`）——
   串起抓取與清理，呼叫 `db.factory.get_repository()` 寫入資料庫。
4. `main()` + `if __name__ == "__main__":`——用 `argparse` 提供 CLI 參數，
   讓爬蟲可以直接 `venv/bin/python crawlers/xxx_crawler.py --xxx` 執行。

---

## 資料流

### 寫入方向（爬蟲）

```
crawlers/xxx_crawler.py main()
  → parse_args()                          （argparse 解析 CLI 參數）
  → crawl() / crawl_news() / run()         （主流程函式）
      → 抓取函式（polite_get() 或 Playwright）→ 拿到原始資料
      → 清理／解析純函式                    → 轉成 upsert_* 要的 dict 格式
      → db.factory.get_repository()        → 拿到 StockRepository 實例
      → repo.upsert_xxx(rows)              → 寫入 SQLite（或 Supabase）
```

三支爬蟲彼此獨立，`scripts/run_all_crawlers.py` 只是依序 import 並呼叫這三支
的主流程函式（`crawl` / `crawl_news` / `run`），每支包在自己的
`try/except` 裡，任一支失敗不影響其他支，最後印總結——這是排程系統唯一
需要知道的單一入口，細節見該檔案的 docstring。

### 讀取方向（Dashboard）

```
瀏覽器 GET http://localhost:8300/
  → StaticFiles 回傳 dashboard/static/index.html
  → index.html 載入 main.js
  → main.js DOMContentLoaded 時平行呼叫四支 API：
      /api/summary → dashboard/app.py api_summary()
      /api/prices  → dashboard/app.py api_prices()
      /api/news    → dashboard/app.py api_news()
      /api/supply-chain → dashboard/app.py api_supply_chain()
  → 每支端點透過 FastAPI 的 Depends(get_repo) 拿到 StockRepository 實例
  → 呼叫 repo.get_xxx(...)（唯讀，只查詢，不寫入）
  → 回傳 JSON → main.js 組成 stat tiles / Chart.js 圖表 / 新聞列表 / 供應鏈卡片
```

**唯讀邊界**（重要架構原則，修改 `dashboard/app.py` 時務必遵守）：
整支 `dashboard/app.py` 不應該出現任何 `upsert_*` 呼叫。這個邊界不是靠
程式碼強制檢查，而是團隊慣例——寫新端點時如果發現需要寫入資料庫，代表
這個功能邏輯上屬於「爬蟲」而不是「Dashboard」，應該放到 `crawlers/` 或
`scripts/`，不要加進 `dashboard/app.py`。

### 資料庫可抽換的關鍵

`crawlers/` 與 `dashboard/` 的程式碼裡，唯一會出現的 db 相關 import 是：

```python
from db.factory import get_repository
```

不會出現 `from db.sqlite_repo import SqliteRepository` 這種直接 import 具體
實作的寫法（`db/factory.py` 內部才會這樣做）。這確保了「呼叫端只依賴
`db/base.py` 定義的抽象介面」，換資料庫後端時呼叫端一行都不用改。

---

## repository 介面說明

`db/base.py` 的 `StockRepository` 是所有資料庫操作的合約，`SqliteRepository`
與 `SupabaseRepository` 都必須完整實作以下方法（方法簽名禁止偏離，因為
`crawlers/` 與 `dashboard/` 都是照這份合約寫呼叫端程式碼）：

| 方法 | 用途 | 去重／排序規則 |
|---|---|---|
| `upsert_stock(symbol, name, market=None, industry=None) -> None` | 新增或更新一檔股票基本資料 | 以 `symbol` 為主鍵 upsert |
| `get_stocks() -> list[dict]` | 取全部股票 | 依 `symbol` 排序 |
| `upsert_daily_prices(rows) -> int` | 批次寫入每日股價，回傳寫入筆數 | 以 `(stock_symbol, trade_date)` 唯一鍵 upsert |
| `get_daily_prices(symbol, start=None, end=None, limit=None) -> list[dict]` | 取某股票股價 | 依 `trade_date` 遞增排序 |
| `get_latest_price_date(symbol) -> str \| None` | checkpoint 用：目前最新交易日 | 無資料回傳 `None` |
| `upsert_news(rows) -> int` | 批次寫入新聞，回傳**實際新增**筆數 | 以 `url` 唯一鍵去重，已存在的 url 不重複寫入、不更新 |
| `get_news(symbol, limit=50) -> list[dict]` | 取某股票新聞 | 依 `published_at` 遞減排序（最新在前） |
| `upsert_supply_chain(rows) -> int` | 批次寫入供應鏈公司，回傳寫入筆數 | 以 `(anchor_symbol, company_name, segment)` 唯一鍵 upsert |
| `get_supply_chain(anchor_symbol) -> list[dict]` | 取某股票的供應鏈公司 | — |
| `get_crawl_summary() -> dict` | 各表筆數統計＋最新日期，供 Dashboard 首頁用 | 固定回傳格式，見下方 |

`get_crawl_summary()` 回傳格式固定為：

```python
{"stocks": n, "daily_prices": n, "news": n, "supply_chain": n,
 "latest_trade_date": str | None, "latest_news_at": str | None}
```

**為什麼 `upsert_news` 跟其他兩個 `upsert_*` 語意不一樣**：`upsert_daily_prices`
與 `upsert_supply_chain` 遇到重複鍵是「用新值覆蓋舊值」（因為股價、供應鏈
名單本來就可能被重新抓取後更新），但 `upsert_news` 遇到重複的 `url` 是
「整列跳過、不覆蓋」（因為同一篇新聞的標題、內容不會變，沒有覆蓋的必要，
且用「跳過」才能準確統計「這次真正新增了幾筆」，用來判斷排程是否有抓到
新內容）。實作時（`db/sqlite_repo.py` 用 `ON CONFLICT (url) DO NOTHING`；
`db/supabase_repo.py` 用 `ignore_duplicates=True`）都要維持這個語意差異。

---

## 如何新增一種資料庫後端

假設你想新增第三種後端（例如 MySQL），步驟如下：

1. **新增 `db/schema_mysql.sql`**：把 `db/schema_sqlite.sql` 的四張表結構
   轉成目標資料庫的語法，欄位名稱、UNIQUE 鍵必須跟現有兩份 schema 保持
   同構（同樣的欄位、同樣的去重鍵），只改型別語法與自增主鍵寫法。
2. **新增 `db/mysql_repo.py`**：建立一個繼承 `db.base.StockRepository` 的
   類別（例如 `MysqlRepository`），完整實作上一節列出的全部方法，去重／
   排序規則必須跟合約一致（尤其 `upsert_news` 的「跳過不覆蓋」語意）。
   可以直接參考 `db/sqlite_repo.py`（同步、標準庫）或
   `db/supabase_repo.py`（第三方 client 套件）的寫法風格。
3. **修改 `db/factory.py` 的 `get_repository()`**：新增一個
   `if backend == "mysql":` 分支，在裡面才 `import db.mysql_repo`（比照
   `supabase` 分支「只在真的選用時才 import」的作法，避免沒裝對應套件的
   環境在 `import db.factory` 這一步就出錯）。
4. **更新 `config.py` 與 `.env.example`**：如果新後端需要額外設定（例如
   `MYSQL_HOST`／`MYSQL_PORT`），依樣加進 `config.py` 的 `os.getenv(...)`
   讀取邏輯，並在 `.env.example` 補上對應欄位與註解。
5. **（建議）新增測試**：可以仿照 `tests/conftest.py` 的 `repo` fixture 寫
   一個新的 fixture，讓 `tests/test_repository.py` 的既有測試案例可以
   對這個新後端重跑一次（或另開一個測試檔），確保新實作符合同一份合約。
6. **更新 README.md**：在〈如何切換到 Supabase〉旁邊或之後補一節新的
   後端切換說明（誠實標示是否實際連線測試過）。

呼叫端（`crawlers/`、`dashboard/`、`scripts/`）完全不需要改動，這就是
repository pattern 的目的。

---

## 如何新增一支爬蟲＋一張表

以下是端到端步驟，假設你要新增一支爬蟲抓「法人買賣超」資料，存進新的
`institutional_trades` 表：

### 1. Schema：`db/schema_sqlite.sql` 與 `db/schema_supabase.sql`

兩份檔案都要加上新表定義，欄位、UNIQUE 去重鍵必須同構。例如：

```sql
CREATE TABLE IF NOT EXISTS institutional_trades (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,  -- Supabase 版改用 GENERATED ALWAYS AS IDENTITY
    stock_symbol  TEXT NOT NULL REFERENCES stocks(symbol),
    trade_date    TEXT NOT NULL,                       -- Supabase 版改用 DATE
    ...
    UNIQUE (stock_symbol, trade_date)
);
```

先想清楚「這張表的自然去重鍵是什麼」（通常是「哪一天、哪一檔股票」這種
組合），因為下一步的 `upsert_*` 方法會需要用到。

### 2. 介面：`db/base.py`

在 `StockRepository` 加上一組抽象方法（讀＋寫各一個），docstring 要寫清楚
`rows` 需要哪些 key、去重規則、回傳值意義，比照現有方法的寫法：

```python
@abstractmethod
def upsert_institutional_trades(self, rows: list[dict]) -> int:
    """..."""
    raise NotImplementedError

@abstractmethod
def get_institutional_trades(self, symbol: str, limit: int | None = None) -> list[dict]:
    """..."""
    raise NotImplementedError
```

**注意**：只要在 `StockRepository` 加了新的 `@abstractmethod`，
`SqliteRepository` 與 `SupabaseRepository` 只要有任一個沒實作，之後
`get_repository()` 建立實例時就會直接因為「還是抽象類別」而報錯——這是
Python ABC 機制的保護，故意的，逼你兩邊都要補齊。

### 3. 兩個 repository 實作

在 `db/sqlite_repo.py` 與 `db/supabase_repo.py` 都要補上第 2 步新增的方法，
SQLite 版用 `INSERT ... ON CONFLICT (...) DO UPDATE`，Supabase 版用
`self.client.table(...).upsert(..., on_conflict=...)`，兩邊語意要一致。

### 4. 爬蟲：`crawlers/xxx_crawler.py`

新增一支獨立檔案，結構比照上方〈專案結構與各資料夾用途〉列出的四段式
（清理純函式 → 抓取 I/O 函式 → 主流程函式 → `main()` CLI 入口）。務必：

- 用 `crawlers/common.py` 的 `check_robots_allowed()`、`polite_get()`、
  `setup_logging()`，不要自己重寫節流／重試邏輯。
- 清理／解析邏輯寫成純函式（輸入 → 輸出，不做 I/O），方便單獨測試。
- 單筆資料解析失敗只記 log 跳過，不可以讓整支爬蟲中斷，也不可以填假值
  湊資料（禁止捏造資料，是本專案的品質底線）。
- 檔案開頭比照現有三支爬蟲補上模組 docstring：做什麼／為什麼這樣設計
  （取捨教學點）／流程／注意事項。

### 5. 排程入口：`scripts/run_all_crawlers.py`（視情況）

如果新爬蟲也要納入例行排程，在這支腳本裡仿照既有三段（股價／新聞／
供應鏈）的寫法，加一段 `try/except` 呼叫新爬蟲的主流程函式，並加進最後
的 `results` 總結清單。

### 6. 測試：`tests/test_xxx_crawler.py`

比照 `tests/test_stock_crawler.py` 或 `tests/test_supply_chain_crawler.py`
的寫法：

- 清理／解析純函式直接單元測試（不需要 fixture，給定輸入斷言輸出）。
- 需要固定 HTML／JSON 樣本的解析邏輯，把樣本存進 `tests/fixtures/`，讀檔
  後餵給解析函式，不要在測試裡真的發網路請求。
- 如果要測 `upsert_*`／`get_*` 的資料庫行為，用 `tests/conftest.py` 提供
  的 `repo` fixture（乾淨的暫存 SQLite）。

### 7. Dashboard（視情況）

如果新資料要在 Dashboard 顯示，在 `dashboard/app.py` 加一個新的唯讀端點
（只呼叫 `repo.get_xxx(...)`，不可以呼叫任何 `upsert_*`），並在
`dashboard/static/` 的 HTML/CSS/JS 加對應的顯示區塊；新增端點記得也在
`tests/test_api.py` 補一個對應的測試案例（用 `TestClient` + tmp db，寫法
比照既有測試）。

---

## 測試怎麼跑

```bash
venv/bin/python -m pytest -q
```

目前共 107 個測試，涵蓋範圍與檔案對應：

| 測試檔 | 涵蓋範圍 |
|---|---|
| `tests/test_repository.py` | `SqliteRepository` 全部方法：CRUD、upsert 去重、`get_crawl_summary()` |
| `tests/test_stock_crawler.py` | 股價清理純函式（民國年轉換、千分位、`--`、漲跌符號）＋固定 JSON fixture 測解析 |
| `tests/test_news_crawler.py` | 新聞清理／時間解析純函式＋固定 HTML fixture 測列表頁與文章頁解析 |
| `tests/test_supply_chain_crawler.py` | 固定 HTML fixture 測供應鏈頁面解析 |
| `tests/test_api.py` | FastAPI `TestClient` 打四支 API 端點，搭配暫存資料庫 |

`tests/conftest.py` 提供的 `repo` fixture 會在 pytest 的暫存目錄
（`tmp_path`）建一份全新 SQLite 檔案並執行 `db/schema_sqlite.sql`，每個
測試互不汙染，也不會動到 `data/tsmc.db` 這份真實資料。

**注意**：測試全部針對「清理／解析純函式」與「本機 SQLite」，不會真的發
網路請求（HTML／JSON 樣本都固定存在 `tests/fixtures/`），也**不測試
`SupabaseRepository`**（沒有雲端連線可用）——這是本專案「全本地端」定位在
測試層的具體反映，修改 `db/supabase_repo.py` 後請自行以程式邏輯 review
確認正確性，無法靠自動測試驗證。

跑單一測試檔或單一測試函式：

```bash
venv/bin/python -m pytest tests/test_stock_crawler.py -q
venv/bin/python -m pytest tests/test_stock_crawler.py::test_convert_roc_date -q
```

---

## 程式慣例

- **logging，不用 `print`**：所有執行期訊息（包含爬蟲進度、跳過的資料、
  錯誤）一律用 `crawlers/common.py` 的 `setup_logging(name)` 拿到的
  logger，同時輸出到終端機與 `logs/crawler.log`。`scripts/init_db.py` 是
  例外（用 `print`），因為它是一次性的手動執行腳本，不是長跑的爬蟲流程。
  新增程式碼時，凡是會被排程自動執行的邏輯，一律用 logging。
- **清理／解析函式必須是純函式**：輸入資料（字串、dict、HTML）進去，輸出
  乾淨的值或 dict 出來，函式內部不能有任何網路請求、資料庫存取、或讀寫
  檔案系統。這是本專案能夠大量單元測試（107 個測試多數不連網路、不連
  資料庫）的根本原因；新增爬蟲或修改清理邏輯時，先確認你寫的函式符合
  這個約束，才有辦法用固定 fixture 測試。
- **upsert 必須冪等（idempotent）**：同一份輸入不管執行一次還是十次，
  資料庫最終狀態都要一樣（不能每次都疊加出重複列）。三支爬蟲的
  checkpoint／backfill 邏輯都依賴這個特性才敢「重疊重抓」（例如股價爬蟲
  checkpoint 落在月中時會整月重抓）——如果新增的 `upsert_*` 沒有仔細選對
  UNIQUE 去重鍵，這個安全網就會失效。
- **例外處理：單筆失敗不中斷整批**：網路錯誤、解析失敗都只記一筆
  `WARNING`／`ERROR` log 並跳過該筆（或該次請求），不能讓一支爬蟲因為
  某一筆資料異常就整個 crash。`scripts/run_all_crawlers.py` 把同樣的原則
  再往上套用一層：單支爬蟲失敗不能讓其他爬蟲不執行。
- **禁止捏造資料**：解析不到某個必要欄位，就整筆跳過並記 log，絕對不要用
  `0`、空字串、或「上一筆的值」去湊一筆看起來完整、實際上是假的資料。
  這是整個專案最優先的品質底線，寫程式時遇到「這裡到底該填什麼預設值」
  的猶豫，答案幾乎都是「跳過並記 log，不要填」。
- **教學註解風格**：每個模組（檔案最上方）與每個重要函式的 docstring，
  盡量包含「做什麼」＋「為什麼這樣設計」兩段；如果這個設計背後有取捨
  （例如選 Playwright 而不是 requests、選 requests 而不是 Playwright），
  要把取捨的理由寫進去，而不是只描述程式在做什麼。初學者容易誤解或
  容易踩坑的地方，額外用「注意」標出來。新增程式碼時請維持這個風格，
  這份專案的存在目的本來就是給人讀懂，不只是給人跑。
- **不留 TODO/FIXME 交差、不留 `print` 除錯殘留**：發現真的做不完的事，
  記錄在文件（README/DEVELOPMENT）或直接跟需求方說明，不要用程式碼裡的
  註解當代辦清單；除錯用的 `print()` 在確認邏輯正確後要清乾淨或改成
  適當等級的 logging。
