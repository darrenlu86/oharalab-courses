# 台積電股票分析教學專案

一個從零開始的「資料庫設計與網路爬蟲」教學範例：三支爬蟲把台積電（2330）的
股價、新聞、上下游供應鏈資料抓下來存進資料庫，再由一個唯讀的 Dashboard
網頁把資料視覺化。整個流程可以完全在本機跑通，不需要申請任何雲端帳號。

## 關於作者

本專案為呂紹民的學員教學範例。如果對本文件或專案有任何問題，或有專案導入、
教學、諮詢需求，歡迎聯絡我。

| | |
|---|---|
| 作者 | 呂紹民（Darren Lu） |
| Email | kevin868686@gmail.com |
| LinkedIn | https://linkedin.com/in/shaominglu |
| Facebook | https://www.facebook.com/darrenlu86 |

資料僅供教學與研究用途，請見文末〈爬蟲倫理與免責聲明〉。

---

## 目錄

1. [這個專案在教什麼](#這個專案在教什麼)
2. [環境需求與安裝](#環境需求與安裝)
3. [SQLite 本地快速起步](#sqlite-本地快速起步)
4. [如何切換到 Supabase（選用，本專案未實際串接）](#如何切換到-supabase選用本專案未實際串接)
5. [定時自動執行爬蟲](#定時自動執行爬蟲)
6. [對外部署指引（進階，純文件）](#對外部署指引進階純文件)
7. [爬蟲倫理與免責聲明](#爬蟲倫理與免責聲明)
8. [專案結構](#專案結構)

---

## 這個專案在教什麼

整個系統分成兩段，中間只透過「資料庫」溝通，彼此完全不知道對方的存在：

```
[資料來源]              [爬蟲層]              [清理]           [資料存取層]
TWSE / 鉅亨網 / TPEx  →  crawlers/  →  同檔內的清理純函式  →  db/  →  SQLite（或 Supabase）
                                                                   ↑
                                                        dashboard/（唯讀，只從資料庫讀）
```

**為什麼這樣設計**：爬蟲負責「把髒資料變乾淨、寫進資料庫」，Dashboard 負責
「把資料庫的資料顯示出來」，兩件事的節奏完全不同——爬蟲可能一天只跑一次、
可能因為對方網站改版而失敗；Dashboard 則是使用者隨時打開網頁都要能正常顯示。
把兩者用資料庫隔開，其中一邊出問題（例如新聞網站當天改版）不會拖累另一邊
（Dashboard 照樣能顯示昨天抓到的資料）。這也是業界常見的 ETL／應用分離架構
的縮小教學版。

資料庫的存取全部走同一份介面（`db/base.py` 的 `StockRepository`），底下可以
是 SQLite 或 Supabase（PostgreSQL）兩種實作。這個「介面統一、實作可抽換」的
寫法叫 **repository pattern**，細節與如何新增第三種資料庫後端寫在
[DEVELOPMENT.md](DEVELOPMENT.md)。

---

## 環境需求與安裝

### 需要什麼

- Python 3.11 以上（本專案開發與測試環境為 Python 3.13.11）
- macOS / Linux／Windows 皆可（本文件指令以 macOS/Linux 為主，Windows 對應寫法整理在下方
  〈Windows 使用者對照〉小節；〈定時自動執行爬蟲〉一節另有工作排程器的獨立說明）

### 安裝步驟

在專案根目錄（`tsmc-stock-analysis/`）依序執行：

```bash
# 1. 建立虛擬環境（venv）
python3 -m venv venv
```

**為什麼要建 venv**：Python 套件是「整台電腦共用」的，如果不同專案各自需要
不同版本的同一個套件，直接裝在系統 Python 會互相打架。虛擬環境（virtual
environment）幫每個專案開一個獨立的套件空間，這個專案的 `requirements.txt`
裝的版本，不會影響你電腦上其他 Python 專案。

```bash
# 2. 安裝套件（用 venv 裡的 pip，不要用系統的 pip）
venv/bin/pip install -r requirements.txt
```

**注意（初學者常見錯誤）**：忘記啟用或指定 venv，直接打 `pip install` 會裝到
系統 Python 去，之後執行 `python xxx.py` 卻用系統 Python 執行，會出現「明明
裝過了卻說找不到套件」的疑惑。本文件所有指令都直接寫 `venv/bin/python`／
`venv/bin/pip`，就是為了避免這個混淆——不管你有沒有 `source venv/bin/activate`
啟用 venv，指令都一定會用到正確的那一份 Python。

```bash
# 3. 安裝 Playwright 用的瀏覽器驅動程式
venv/bin/playwright install chromium
```

**這一步在裝什麼**：`playwright` 這個 Python 套件本身只是「遙控瀏覽器」的
控制介面，並不包含瀏覽器本體。`playwright install chromium` 是額外去下載一份
Chromium（類似 Chrome 的開源瀏覽器）的無頭（headless，沒有視窗畫面）版本，
裝在 Playwright 自己的快取資料夾裡，跟你電腦上原本安裝的 Chrome 完全無關。
新聞爬蟲（`crawlers/news_crawler.py`）需要這個瀏覽器才能執行，沒裝這一步會
在跑新聞爬蟲時直接報錯。

```bash
# 4. 複製環境變數範本
cp .env.example .env
```

`.env.example` 已經內建 SQLite 的預設值，本機開發不需要改任何東西就能直接用；
`.env` 這個檔案已被 `.gitignore` 排除，不會被 commit 進版本控制。

**注意（`.env` 與 shell 環境變數的優先權）**：`config.py` 用 `load_dotenv(override=False)` 讀取
`.env`——`override=False` 代表如果同一個變數在執行當下的 shell 環境裡已經有值（例如你自己下過
`export DB_BACKEND=sqlite`），shell 的值會優先於 `.env` 檔案裡寫的值，`.env` 只補上 shell 沒設定的
那些。這個特性在測試／CI 環境很有用：可以直接在執行環境設定環境變數蓋過 `.env` 的預設值，不需要
為每個環境各自維護一份不同的 `.env` 檔案。

### Windows 使用者對照

以下是上面安裝步驟與後續指令，在 Windows（PowerShell／cmd）下的對應寫法：

| 情境 | macOS / Linux（本文件預設寫法） | Windows |
|---|---|---|
| 建立 venv | `python3 -m venv venv` | `python -m venv venv`（Windows 一般只有 `python`，沒有 `python3` 這個別名） |
| 執行 venv 裡的程式 | `venv/bin/python`／`venv/bin/pip` | `venv\Scripts\python.exe`／`venv\Scripts\pip.exe`（路徑分隔字元改用反斜線） |
| 啟用 venv（選用，本文件指令不需要這步） | `source venv/bin/activate` | cmd：`venv\Scripts\activate`／PowerShell：`venv\Scripts\Activate.ps1` |
| 複製環境變數範本 | `cp .env.example .env` | PowerShell：`Copy-Item .env.example .env`／cmd：`copy .env.example .env` |
| 排程自動執行 | crontab（見下方〈定時自動執行爬蟲〉） | 工作排程器 Task Scheduler（同一節有獨立步驟說明） |

**為什麼另外列這張表，而不是每個指令旁邊都加註解**：本文件其餘段落的指令範例統一寫
`venv/bin/python xxx.py` 這種 macOS/Linux 路徑寫法，逐條加註解會讓每個程式碼區塊變得雜亂；
Windows 使用者只要記得把 `venv/bin/` 換成 `venv\Scripts\`（含斜線方向），指令其餘部分照抄即可。

---

## SQLite 本地快速起步

這是本專案唯一實際跑過、驗證過的路徑：全部資料存在本機的一個 SQLite 檔案
（`data/tsmc.db`），不需要任何雲端帳號、不需要網路上的資料庫服務。

### 第一步：初始化資料庫

```bash
venv/bin/python scripts/init_db.py
```

這支腳本做兩件事：執行 `db/schema_sqlite.sql` 建立四張資料表（`stocks`／
`daily_prices`／`news`／`supply_chain_companies`），接著種入台積電
（2330）的基本資料。成功會印出：

```
[init_db] 資料表已建立於：.../data/tsmc.db
[init_db] 已種入股票基本資料：2330 台積電（上市／半導體）
```

**為什麼要先種台積電這筆資料**：`daily_prices`／`news`／
`supply_chain_companies` 三張表都有欄位（`stock_symbol`／`anchor_symbol`）
指向 `stocks(symbol)`，這是資料庫的**外鍵（FOREIGN KEY）**約束——如果沒有先
在 `stocks` 表放一筆 `symbol = '2330'`，後面三支爬蟲想寫入資料時，資料庫會
直接拒絕（違反外鍵約束），因為它們指到的那個「股票」根本不存在。

**注意**：重複執行這支腳本是安全的（**冪等**，idempotent）。建表語句用
`CREATE TABLE IF NOT EXISTS`，表已存在就跳過；種子資料用
`upsert_stock()`，同一檔股票重複執行只會覆蓋成一樣的值，不會產生錯誤或
重複資料。

### 第二步：執行三支爬蟲

三支爬蟲可以各自單獨執行，也可以用整合入口一次跑完。先介紹各自單獨執行
（方便你先搞懂每一支在做什麼），下一節〈定時自動執行爬蟲〉再介紹整合入口。

```bash
# 股價（TWSE 官方 JSON API，requests）
venv/bin/python crawlers/stock_crawler.py --months 3
```

`--months` 只在資料庫**完全沒有股價資料**時才有作用：代表「第一次執行時，
要往前回補（backfill）幾個月」。已經有資料之後，爬蟲會改用**checkpoint**
機制——查詢資料庫裡目前最新的交易日期，只從那個月重新抓到本月為止，不需要
每次都重抓好幾年份的資料。這支爬蟲抓的是 TWSE（證交所）官方公開的 JSON
端點，不是解析網頁，所以速度快、格式穩定。

```bash
# 新聞（鉅亨網，Playwright 開瀏覽器渲染頁面）
venv/bin/python crawlers/news_crawler.py --limit 20
```

`--limit` 是這次最多擷取幾篇新聞（預設 20）。這支爬蟲會實際開一個無頭
Chromium 瀏覽器，因為目標頁面是 React 動態渲染的頁面，單純用 `requests`
抓到的 HTML 內容並不完整。執行時間會明顯比另外兩支久（每篇文章都要開一次
瀏覽器分頁），這是預期行為，不是卡住。

```bash
# 上下游供應鏈（TPEx 產業價值鏈平台，requests + BeautifulSoup）
venv/bin/python -m crawlers.supply_chain_crawler
```

**注意（這支跟另外兩支的執行方式不一樣）**：這支必須用 `-m` 以模組方式
執行（`venv/bin/python -m crawlers.supply_chain_crawler`），不能用
`venv/bin/python crawlers/supply_chain_crawler.py` 直接執行檔案——它內部
用 `from crawlers import common` 匯入共用工具，而這個檔案沒有像另外兩支
一樣手動把專案根目錄加進 `sys.path`，直接執行檔案會找不到 `crawlers` 這個
套件而報 `ModuleNotFoundError`。這支不吃 CLI 參數，固定抓台積電（2330）在
半導體產業鏈頁面上的上游／中游／下游公司清單。目標頁面是伺服器端直接輸出
完整 HTML（server-rendered），不需要瀏覽器就能拿到完整內容，所以用最簡單的
`requests + BeautifulSoup` 組合。

**注意（可能看到的 SSL 警告，屬已知情況，會自動復原，不用中斷執行）**：執行這支爬蟲時，有機會在
終端機看到類似這樣的 `WARNING`：「TLS/SSL 驗證失敗（通常是憑證鏈相容性問題，不是網路不穩定），
已提早結束重試」，緊接著另一則「requests 依標準流程仍失敗，改用系統 curl 指令備援」。這是已知情況：
`ic.tpex.org.tw` 的憑證鏈沒有帶新版規範建議的 Subject Key Identifier 欄位，Python 3.13 起 `ssl`
模組的預設驗證比瀏覽器／`curl` 嚴格，會把這類連線判定失敗；程式碼偵測到這種 SSL 錯誤會提早結束
重試（不用等完整套約 14 秒的 backoff），改用系統內建的 `curl`（一樣完整驗證憑證，沒有加
`-k`/`--insecure`）當備援抓取，通常幾秒內就會自動復原、正常完成爬取。看到這兩則 `WARNING` 不用
中斷執行；只有後面接著出現「curl 備援抓取也失敗」的 `ERROR`，才代表連備援都失敗了，需要留意。

**注意（初學者常見疑惑）**：三支爬蟲執行時，終端機與 `logs/crawler.log`
會同時出現大量訊息（含時間戳與等級，如 `INFO`／`WARNING`／`ERROR`）——這是
刻意設計成「用 `logging` 而不是 `print`」，方便事後回頭查「昨天晚上跑排程
時，哪一筆資料抓失敗了」。看到 `WARNING` 不用緊張，通常代表某一筆資料格式
特殊被跳過（例如 TWSE 用 `--` 表示某天沒有這個數值），不是程式壞掉；看到
反覆的 `ERROR` 才需要留意，可能是網路問題或目標網站真的改版了。

### 第三步：啟動 Dashboard

```bash
venv/bin/uvicorn dashboard.app:app --port 8300
```

啟動後，打開瀏覽器輸入：

```
http://localhost:8300
```

會看到版頭（台積電 2330 ＋最新收盤價與漲跌幅＋最後更新時間）；主要內容是
左右兩欄——左欄是收盤價折線圖與成交量長條圖（分開兩張圖、上下堆疊，不畫
雙軸圖），右欄是新聞列表；下方整寬顯示上下游供應鏈三欄卡片；原本的統計
摘要卡片降級成頁尾一行小字。

**為什麼是 FastAPI＋一個獨立的 uvicorn 指令，而不是 `python dashboard/app.py`
直接跑**：`dashboard/app.py` 裡定義的 `app` 只是一個「應用程式物件」，真正
負責「監聽某個 port、接收 HTTP 請求」的是 **uvicorn** 這個 ASGI 伺服器。
這樣拆開的好處是同一份 `app` 物件，開發階段可以用 uvicorn 簡單啟動，未來要
部署到正式環境時，也可以換成 gunicorn＋多個 uvicorn worker 之類更適合正式
流量的啟動方式，完全不用改 `app.py` 裡的程式碼。

Dashboard 前端頁面**只呼叫 API**（`/api/summary`、`/api/prices`、
`/api/news`、`/api/supply-chain`），不會直接連資料庫；如果你在爬蟲都還沒
跑過的情況下就啟動 Dashboard，頁面會顯示「尚無資料，請先執行爬蟲」的提示
文字，不會是空白或報錯畫面——因為前端拿到空陣列時有明確處理這個情況，你
也可以直接在瀏覽器打開 `http://localhost:8300/api/summary` 看原始 JSON，
確認資料庫目前實際存了多少筆。

---

## 如何切換到 Supabase（選用，本專案未實際串接）

**先誠實說明現況**：本專案的預設路徑、以及目前實際跑過驗證的路徑，都是
SQLite。切到 Supabase 需要的程式碼（`db/supabase_repo.py`）與 SQL schema
（`db/schema_supabase.sql`）都已經寫好、邏輯完整可讀，但作者並未實際申請
Supabase 專案連線測試過。如果你想練習「把本地資料庫換成雲端資料庫」這件事，
可以照下面步驟操作，但請自行驗證结果，不要假設它一定沒有任何小狀況。

### 1. 申請 Supabase 專案，拿到 URL 與 Key

1. 到 [supabase.com](https://supabase.com) 註冊帳號、建立一個新專案（New
   Project），選一個地區與資料庫密碼（自己保管好）。
2. 專案建立完成後，進入該專案的 **Project Settings → API**，可以看到：
   - **Project URL**：對應 `.env` 的 `SUPABASE_URL`
   - **anon public** 與 **service_role** 兩組 key：對應 `.env` 的
     `SUPABASE_KEY`

**注意（這兩把 key 差很多，不要選錯）**：`anon` key 是設計給「瀏覽器前端
直接呼叫」用的，權限受 Row Level Security（RLS）規則限制；`service_role`
key 則是給「後端伺服器」用的，會**繞過** RLS，等於擁有完整讀寫權限。本專案
的爬蟲是在你自己的電腦上、以「可信任的伺服器端流程」執行，所以應該填
`service_role` key。千萬不要把 `service_role` key 放進會被瀏覽器載入的
前端程式碼或公開的 repo——這等於把資料庫的完整權限公開給任何人。

### 2. 在 Supabase 建表

打開 Supabase 專案的 **SQL Editor**，把 `db/schema_supabase.sql` 的完整
內容貼上去執行一次。這個檔案跟本機用的 `db/schema_sqlite.sql` 定義同樣的
四張表（`stocks`／`daily_prices`／`news`／`supply_chain_companies`），只是
用 PostgreSQL 的語法與型別寫（例如自增主鍵用
`GENERATED ALWAYS AS IDENTITY`、日期用原生 `DATE`/`TIMESTAMPTZ`、金額用
`NUMERIC(10,2)` 而不是 SQLite 的 `REAL`）。兩份 schema 檔案開頭的註解都有
寫這些差異的教學說明，可以對照著讀。

### 3. 設定 `.env`

```
DB_BACKEND=supabase
SUPABASE_URL=你的 Project URL
SUPABASE_KEY=你的 service_role key
```

**注意**：`SUPABASE_URL`／`SUPABASE_KEY` 這類機密只放在本機的 `.env`，
不要 commit 進 git（`.env` 已在 `.gitignore` 內）；`.env.example` 裡的
對應欄位刻意留空，就是為了避免有人複製貼上時不小心把真正的金鑰寫進範本檔。

### 4. 之後怎麼用

`.env` 設定完成後，`db/factory.py` 的 `get_repository()` 會自動改回傳
`SupabaseRepository` 實例，之前介紹過的所有指令（`scripts/init_db.py` 的
seed 步驟、三支爬蟲、Dashboard）呼叫端程式碼完全不用改一行——這正是
repository pattern（見上方〈這個專案在教什麼〉一節）帶來的好處。

**注意**：`scripts/init_db.py` 目前只會在 `DB_BACKEND=sqlite` 時自動執行
建表；`DB_BACKEND=supabase` 時它只會做 seed（種入台積電基本資料）這一步，
建表請照上面第 2 步先在 SQL Editor 手動執行過一次。

---

## 定時自動執行爬蟲

`scripts/run_all_crawlers.py` 是設計給排程系統呼叫的**單一入口**：依序執行
股價、新聞、供應鏈三支爬蟲，其中一支失敗（例如某天新聞網站改版、TWSE API
暫時打不通）只會記一筆錯誤 log 並繼續跑下一支，不會讓整批排程中斷；三支都
跑完後會印出一份總結。

```bash
venv/bin/python scripts/run_all_crawlers.py
# 也可以帶參數，分別轉給股價爬蟲的 --months 與新聞爬蟲的 --limit：
venv/bin/python scripts/run_all_crawlers.py --months 3 --news-limit 20
```

### macOS / Linux：crontab

```bash
crontab -e
```

加入一行（範例：每天台灣時間早上 8 點執行一次，`cd` 到專案目錄後用 venv
的 Python 執行）：

```
0 8 * * * cd /path/to/tsmc-stock-analysis && venv/bin/python scripts/run_all_crawlers.py >> logs/cron.log 2>&1
```

**為什麼要寫絕對路徑、還要先 `cd`**：cron 執行時不會套用你平常在終端機裡
的環境設定（例如 `PATH`、目前所在目錄），如果直接寫
`venv/bin/python scripts/run_all_crawlers.py`，cron 會因為「不知道相對路徑
是相對哪裡」而找不到檔案。`>> logs/cron.log 2>&1` 是把這次執行的所有輸出
（包含錯誤訊息）都額外存一份到 `logs/cron.log`，方便你事後確認排程有沒有
真的跑起來——腳本本身雖然也會寫 `logs/crawler.log`，但多存一份 cron 本身的
輸出，可以抓到「腳本根本沒被執行到」這種更早期的問題。

### Windows：工作排程器

在「工作排程器」（Task Scheduler）建立一個基本工作，觸發程序設定你要的
時間頻率，動作選「啟動程式」，程式路徑填專案目錄底下的
`venv\Scripts\python.exe`，引數填 `scripts\run_all_crawlers.py`，「起始位置」
填專案根目錄的完整路徑。

**注意：本專案不會自動幫你安裝任何排程**（不管是 crontab 還是工作排程器），
是否要設定、多久執行一次，由你自己決定——尤其要考慮到爬蟲倫理（見下一節），
不建議設定過於頻繁的排程對目標網站造成負擔，每天一次通常已經足夠教學與
個人研究使用。

---

## 對外部署指引（進階，純文件）

本節只說明「如果你想把這個教學專案部署到雲端讓別人也能看」時的整體思路，
**本專案本身沒有實際部署到任何雲端環境**，也不包含任何部署設定檔
（如 Dockerfile、CI/CD 設定）。以下純粹是概念性指引，實際落地需要你自己
評估與操作。

### Dashboard 部署到雲端主機

`dashboard/app.py` 是一個標準的 FastAPI 應用程式，理論上可以用常見的方式
部署，例如：把專案打包成容器（Docker image），部署到任何支援容器的雲端
服務（如 Google Cloud Run、Render、Fly.io 等）；或直接在一台雲端主機上用
`uvicorn`／`gunicorn + uvicorn worker` 常駐執行，前面架一個反向代理
（Nginx／Caddy）處理 HTTPS 與網域。**為什麼提容器化**：本專案目前的
Dashboard 是唯讀的，不需要處理使用者上傳、不需要長時間背景工作，屬於「無
狀態（stateless）」服務，這類服務用容器部署最單純——重啟、擴充實例都不需要
擔心遺失狀態。

### 資料庫改用 Supabase 正式專案

本機開發用的是免費的 SQLite 檔案，部署到雲端後，多個地方（例如 Dashboard
服務本身、獨立的排程爬蟲）需要讀寫同一份資料，SQLite 檔案型資料庫就不適合
了（雲端環境的檔案系統通常不保證持久化，也難以讓多個服務同時安全寫入同一個
檔案）。這正是本專案一開始就把 `db/supabase_repo.py` 準備好的原因——部署到
雲端時，只要照上面〈如何切換到 Supabase〉的步驟建立正式的 Supabase 專案、
設定對應的環境變數，資料庫就從「本機檔案」換成「雲端 PostgreSQL」，爬蟲與
Dashboard 的程式碼完全不用改。

### 環境變數與金鑰管理原則

雲端環境不應該把 `.env` 檔案直接放進部署的容器或伺服器裡（原因跟本機不該
把 `.env` commit 進 git 一樣）。正式作法是使用部署平台自己提供的「環境變數」
或「密鑰管理」介面（例如 Cloud Run 的環境變數設定、GitHub Actions 的
Repository Secrets、各家雲端平台的 Secret Manager），在部署當下才把
`SUPABASE_URL`／`SUPABASE_KEY` 這類機密注入到執行環境，程式碼（`config.py`）
不需要更改，因為它本來就是透過 `os.getenv()` 讀取環境變數，`.env` 檔案
只是「本機開發時」的其中一種來源。

### 雲端排程

如果 Dashboard 部署到雲端了，通常也會希望爬蟲不再依賴你自己電腦的
crontab（畢竟電腦關機排程就不會跑），這時可以考慮：

- **GitHub Actions 的 cron 觸發**（`on: schedule`）：把
  `venv/bin/python scripts/run_all_crawlers.py` 這個指令包成一個 workflow，
  由 GitHub 的伺服器定時執行，執行環境即用即棄，不需要自己維護一台常駐主機。
- **Google Cloud Scheduler**：定時打一個 HTTP 端點或觸發一個 Cloud Run
  Job，由該 Job 內執行爬蟲邏輯。

兩種方式的共同概念都是「把 `scripts/run_all_crawlers.py` 這個排程入口，交給
雲端的排程服務定時觸發」，跟本機 crontab 的角色一樣，只是換了誰來按下
「執行」這個按鈕。這部分同樣只是概念說明，本專案未實際設定任何雲端排程。

---

## 爬蟲倫理與免責聲明

本專案的三支爬蟲設計時遵守以下原則，寫在 `crawlers/common.py`：

- 抓取前檢查目標網站的 `robots.txt`，不允許抓取的路徑一律跳過並記錄 log。
- 固定使用具名的 User-Agent（`tsmc-analysis-edu-crawler/1.0`），內含聯絡
  Email，讓對方網站管理員知道流量來源與可以怎麼聯絡到你。
- 每次請求之間有節流（rate limit）：股價 3 秒、新聞 2 秒、供應鏈頁面 2 秒，
  避免短時間內大量請求造成對方伺服器負擔。
- 失敗有限次重試（exponential backoff），仍失敗就跳過該筆繼續下一筆，不會
  對同一個端點無限重試造成騷擾。

即使遵守以上原則，**請仍自行負責任地使用本專案**：資料僅供教學與個人研究
用途，不用於商業用途、不用於高頻率或大規模的資料蒐集，且應遵守各資料來源
（TWSE、鉅亨網、TPEx）當下實際公告的使用條款——這些條款可能隨時間變動，
本文件記錄的是撰寫當下（2026 年）的實測結果，不代表永久有效。若你要把本
專案的爬蟲邏輯用在其他正式專案，請重新檢視當時的 robots.txt 與服務條款。

---

## 專案結構

```
tsmc-stock-analysis/
├── README.md                     # 本文件：給使用者的教學指南
├── DEVELOPMENT.md                # 給開發者/AI 的技術文件（架構、如何擴充）
├── docs/                         # 技術規格文件目錄（另行維護，非本文件範圍）
├── requirements.txt              # 主要相依套件（版本已鎖定）
├── .env.example                  # 環境變數範本
├── .gitignore
├── config.py                     # 讀 .env，提供 DB_BACKEND 等全域設定
├── db/                           # 資料存取層（repository pattern）
│   ├── __init__.py
│   ├── base.py                   # StockRepository 抽象介面（合約）
│   ├── factory.py                # get_repository()：依 DB_BACKEND 分派實作
│   ├── sqlite_repo.py            # SQLite 實作（已驗證）
│   ├── supabase_repo.py          # Supabase 實作（程式完整，未實際連線測試）
│   ├── schema_sqlite.sql
│   └── schema_supabase.sql
├── scripts/
│   ├── init_db.py                # 建表＋seed 台積電（2330）
│   └── run_all_crawlers.py       # 依序執行三支爬蟲，排程入口
├── crawlers/
│   ├── __init__.py
│   ├── common.py                 # robots 檢查、rate limit、UA、重試、logging
│   ├── stock_crawler.py          # 股價（TWSE API，requests）
│   ├── news_crawler.py           # 新聞（鉅亨網，Playwright）
│   └── supply_chain_crawler.py   # 上下游供應鏈（TPEx，requests+BeautifulSoup）
├── dashboard/
│   ├── app.py                    # FastAPI 唯讀 API＋靜態檔案服務
│   └── static/
│       ├── index.html
│       ├── style.css
│       └── main.js
├── tests/                        # pytest（107 個測試，見 DEVELOPMENT.md）
│   ├── conftest.py
│   ├── fixtures/
│   ├── test_repository.py
│   ├── test_stock_crawler.py
│   ├── test_news_crawler.py
│   ├── test_supply_chain_crawler.py
│   └── test_api.py
├── logs/                         # 執行 log（*.log 已 gitignore，只留 .gitkeep）
└── data/                         # SQLite 資料庫檔（*.db 已 gitignore，只留 .gitkeep）
```

想深入了解每一層在做什麼、資料怎麼流動、以及如何新增一支爬蟲或一種資料庫
後端，請見 [DEVELOPMENT.md](DEVELOPMENT.md)。
