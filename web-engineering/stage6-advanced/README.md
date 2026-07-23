# Stage 6 — 進階版·即時通訊/效能/壓測（WEB-18）

回上層：[網站工程六階段課程總覽](../README.md)

在 stage5 完整電商系統（前台＋後台）的基礎上，讓 BrewGo 沖沖咖啡「活起來」：
後台不用按重新整理就看到新訂單、客服問題逐字打字回覆、商品列表變快、後台
訂單列表不再逐單查資料庫，最後用真實壓力測試量出「優化前後到底差多少」——
過程中還意外挖出一個只有在真實併發下才會出現的資料庫 bug。

> **金流警示**：本站的付款功能是自建的模擬金流（mock payment），完全沒有
> 串接任何真實的第三方金流服務，不會有任何一筆真實金錢往來，理由與細節
> 沿用 stage5，見 [`docs/DEPLOY.md`](docs/DEPLOY.md) 開頭。

## 這一階段你會做出什麼

- **WebSocket 即時訂單看板**：`WS /ws/admin/orders`（後台，任何人建單/付款/
  狀態變化都即時推播給所有連線的管理員）、`WS /ws/my/orders`（前台，顧客
  本人的訂單狀態被店家更新時即時看到），自寫 `ConnectionManager` ＋前端
  exponential backoff 斷線重連。
- **SSE 客服助理**：`GET /api/support/stream?question=...` 用 Server-Sent
  Events 逐字串流回覆（規則式 FAQ 比對，誠實聲明非真 AI），前台客服頁做出
  打字機效果。
- **四項效能調校（各自有教學文件＋實跑證據）**：`products(category,
  is_active)` 複合索引（`EXPLAIN QUERY PLAN` 前後對照）、後台訂單列表 N+1
  查詢修復（單次 JOIN，實測查詢次數從 8 次降到 1 次）、商品列表 30 秒 TTL
  記憶體快取（含 cache invalidation）、`GZipMiddleware` 回應壓縮。
- **壓力測試**：`loadtest/` 資料夾，locust 混合場景（匿名逛商品 3 : 登入
  完整下單流 1），對照 stage5（優化前）與 stage6（優化後）——過程中意外
  發現 stage5 在 50 併發下有 20.63% 的請求會 500（真實 bug，非估算），
  完整證據見 [`docs/PERFORMANCE_REPORT.md`](docs/PERFORMANCE_REPORT.md)。
- **CI 教材**：`ci/github-actions-ci.yml`（跑後端 pytest ＋前後台 build），
  搭配雲端架構願景圖，見 [`docs/CICD.md`](docs/CICD.md)。

## 對應課綱與交付產出

課綱原文（WEB-18）：「完成一個進階應用系統，涵蓋特定進階套件
（Socket.IO/Streaming）、雲端部署與效能調校，並提供壓力測試報告。完成後
產出：含技術選型與關鍵程式片段的完整系統架構說明、含雲端架構圖與 CI/CD
的部署連結、含瓶頸分析與優化對照的效能/壓力測試報告。」

| 產出要求 | 對應本 repo 位置 |
|---|---|
| 特定進階套件（本課程選 WebSocket＋SSE，取代 Socket.IO，理由見下方） | `backend/app/routers/ws.py`、`backend/app/routers/support.py`、`backend/app/ws_manager.py`；設計文件 [`docs/REALTIME.md`](docs/REALTIME.md) |
| 產出 1：含技術選型與關鍵程式片段的完整系統架構說明 | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) 第 7-10 節（stage6 新增部分） |
| 產出 2：含雲端架構圖與 CI/CD 的部署連結 | 課程本身不代學員部署 → [`docs/CICD.md`](docs/CICD.md)（CI/CD 概念、workflow 逐段講解、雲端架構願景圖）＋[`docs/DEPLOY.md`](docs/DEPLOY.md)（本地驗證、部署教學指引、學員交付檢查表） |
| 產出 3：含瓶頸分析與優化對照的效能/壓力測試報告 | [`docs/PERFORMANCE_REPORT.md`](docs/PERFORMANCE_REPORT.md) |

## 與上一階段的差異

這一節基於實際讀過 `stage5-platform/` 的程式碼（backend 與 frontend/admin
全部相關檔案）寫成，不是憑印象；builder 先完整複製 stage5 的
`backend/`／`frontend/`／`admin/`，再逐項擴充——`stage5-platform/` 本身
沒有被改動一個字。

1. **新增 WebSocket 即時通訊**：stage5 完全沒有這個能力，後台要看新訂單
   只能自己重新整理頁面（見 stage5 `admin/src/pages/Orders.jsx`，完全沒有
   任何自動更新機制）。本階段新增 `app/ws_manager.py`（自寫連線管理）與
   `app/routers/ws.py`（兩支 WebSocket 端點），並把
   `orders.py`／`payments.py`／`admin.py` 三支路由從 `def` 改成 `async def`
   以便能 `await` 推播——這個改動意外揭露了一個 stage5 就存在、只有在真實
   高併發下才會出現的 SQLite 跨執行緒 bug（見下方第 8 點與
   [`PERFORMANCE_REPORT.md`](docs/PERFORMANCE_REPORT.md)）。

2. **新增 SSE 客服串流**：stage5 完全沒有客服功能。新增
   `app/routers/support.py`（規則式 FAQ 比對＋逐字串流回覆）與前台
   `pages/Support.jsx`（打字機效果），誠實聲明非真 AI。

3. **商品列表加上 TTL 快取**：stage5 的 `GET /api/products`（見 stage5
   `backend/app/routers/products.py`）每次都直接查 SQLite，沒有任何快取層。
   本階段新增 `app/cache.py`（30 秒 TTL，key 是 `(category, search)`），
   後台商品新增/編輯時呼叫 `invalidate_all()` 主動失效。

4. **後台訂單列表 N+1 查詢修復**：讀過 stage5 `backend/app/db/database.py`
   的 `list_all_orders()` 確認實際寫法是「先查全部訂單，再對每一筆各自查
   一次品項」（1+N 次查詢）。本階段改成單次 `LEFT JOIN`，實測（7 筆訂單）
   查詢次數從 8 次降到 1 次，舊寫法原封不動保留成
   `list_all_orders_naive_n_plus_one()` 純供對照，完整證據見
   [`DATABASE.md`](docs/DATABASE.md)。

5. **新增 `products(category, is_active)` 複合索引**：讀過 stage5
   `backend/app/db/schema.sql` 才發現 `orders.user_id`／
   `order_items.order_id`／`payments.order_id` 這三個索引 stage5 其實
   **已經建過**（不是本階段的功勞，如實記錄這個落差）；真正缺的只有
   `products` 表這個複合索引，本階段補上，`EXPLAIN QUERY PLAN` 實測從
   `SCAN products` 變成 `SEARCH ... USING INDEX`。

6. **新增 GZip 回應壓縮**：stage5 的 `app/main.py` 沒有掛任何壓縮
   middleware。本階段加上 `GZipMiddleware`，實測回應帶
   `content-encoding: gzip`；順便查證了 FastAPI `StaticFiles` 的預設行為
   （有 ETag/Last-Modified，沒有 Cache-Control），見
   [`ARCHITECTURE.md`](docs/ARCHITECTURE.md) 第 9 節。

7. **新增壓力測試工具與報告**：stage5 完全沒有 `loadtest/` 這個概念。
   本階段新增 `loadtest/locustfile.py`（主要工具）與
   `loadtest/asyncio_load_test.py`（fallback），兩份場景一致（匿名逛商品 3
   : 登入完整下單流 1）。

8. **意外發現並修復一個 stage5 就存在的併發 bug**：`app/db/database.py`
   的 `get_connection()` 新增 `check_same_thread=False`。這不在原本規劃
   清單裡——是把三支路由改成 `async def` 之後，開發階段自己的 `pytest -q`
   先炸出 `sqlite3.ProgrammingError: SQLite objects created in a thread
   can only be used in that same thread`，修好之後才發現這個問題**在
   stage5 純同步路由上，高併發下同樣會發生**（stage5 baseline 壓測實測
   20.63% 的請求收到 500，根因與完整證據見
   [`PERFORMANCE_REPORT.md`](docs/PERFORMANCE_REPORT.md)）。

9. **新增 CI 教材**：stage5 完全沒有任何 CI 設定。本階段新增
   `ci/github-actions-ci.yml`（跑後端 pytest＋前後台 build，放在資料夾當
   教材，不直接生效）＋ `docs/CICD.md`（概念、逐段講解、雲端架構願景圖）。

10. **前台／後台元件幾乎沒動**：`ProductCard`／`AuthContext`／
    `AdminAuthContext`／訂單狀態機（`order_state.py`）等 stage5 既有邏輯
    完全沒有改動，只在 `Orders.jsx`（前台/後台）與 `Dashboard.jsx`（後台）
    掛上新的 WebSocket hook 做即時更新提示——資料層的擴充不影響既有的
    呈現邏輯，這也印證了 stage5 的分層設計撐得住這一輪擴充。

## 課綱單元表

| 單元 | 學什麼 | 對應檔案 |
|---|---|---|
| 1. WebSocket 連線管理 | 自寫 `ConnectionManager`、連線生命週期、頻道隔離 | `backend/app/ws_manager.py`、`backend/app/routers/ws.py`，說明見 [`REALTIME.md`](docs/REALTIME.md) |
| 2. 前端斷線重連 | exponential backoff、認證失敗不重連 | `frontend/src/hooks/useOrdersSocket.js`、`admin/src/hooks/useAdminOrdersSocket.js` |
| 3. SSE 串流回應 | async generator、`StreamingResponse`、`EventSource` | `backend/app/routers/support.py`、`frontend/src/pages/Support.jsx` |
| 4. 資料庫索引 | `EXPLAIN QUERY PLAN`、複合索引欄位順序 | `backend/app/db/schema.sql`、`backend/scripts/explain_query_plans.py`，說明見 [`DATABASE.md`](docs/DATABASE.md) |
| 5. N+1 查詢與修復 | 單次 JOIN vs 逐筆查詢、查詢次數實測計數 | `backend/app/db/database.py`（`list_all_orders`），`backend/scripts/n_plus_one_demo.py` |
| 6. In-memory 快取與失效 | TTL 快取、cache invalidation 的難、多 worker 的限制 | `backend/app/cache.py`，說明見 [`ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| 7. HTTP 回應壓縮 | GZip middleware、靜態資產快取標頭查證 | `backend/app/main.py`，說明見 [`ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| 8. 併發與執行緒安全 | FastAPI threadpool 執行模型、SQLite 跨執行緒限制 | `backend/app/db/database.py`（`get_connection`），完整故事見 [`PERFORMANCE_REPORT.md`](docs/PERFORMANCE_REPORT.md) |
| 9. 壓力測試方法論 | locust 場景設計、RPS/p50/p95、聚合數字的解讀陷阱 | `loadtest/locustfile.py`、`loadtest/asyncio_load_test.py`，報告見 [`PERFORMANCE_REPORT.md`](docs/PERFORMANCE_REPORT.md) |
| 10. CI/CD 基礎概念 | build→test→deploy、workflow 檔案結構、路徑過濾 | `ci/github-actions-ci.yml`，說明見 [`CICD.md`](docs/CICD.md) |

## 環境需求

- Python **3.10 以上**（本次建置實測環境為 **3.13.11**）
- Node.js **20 以上**（本次建置實測環境為 **v24.11.1**，npm **11.6.2**）
- 一個現代瀏覽器

## 快速開始

### 測試帳號（沿用 stage5）

| 角色 | Email | 密碼 |
|---|---|---|
| 管理員（後台） | `admin@brewgo.test` | `Admin12345` |
| 顧客（前台） | `customer@brewgo.test` | `Customer12345` |

以下每一步都附上本次撰寫教材時**實際執行**的輸出，指令假設你已經
`cd stage6-advanced`。

### 後端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**初始化資料庫**：

```bash
python scripts/init_db.py
```
實測輸出：
```
建立資料表於：/你的路徑/backend/data/brewgo.db
已匯入 12 筆種子商品資料。
已建立管理員帳號：admin@brewgo.test（id=1）
已建立顧客測試帳號：customer@brewgo.test（id=2）
已匯入 7 筆示範訂單（含對應 payments 紀錄）。
SQLite 資料庫初始化完成！
```

**跑測試**：

```bash
pytest -q
```
實測結果：**117 個測試全部通過**（`test_admin.py` 23 個、
`test_auth.py` 9 個、`test_cache.py` 5 個、`test_cart.py` 18 個、
`test_config.py` 5 個、`test_database_indexes.py` 5 個、
`test_n_plus_one_demo.py` 3 個、`test_orders.py` 17 個、`test_payments.py`
10 個、`test_products.py` 10 個、`test_support_sse.py` 4 個、`test_ws.py`
8 個——`test_config.py` 是 `SECRET_KEY` 預設值偵測 helper 的測試，
`test_products.py`／`test_cart.py`／`test_orders.py`／`test_admin.py` 各多了
「超界 id／欄位回 422 不是 500」的代表性測試；`test_cart.py`／`test_orders.py`
另外多了「商品下架後仍留在購物車、回應要標示 `is_active=false`、建單仍然被
409 擋下」這組測試，見「已下架商品體驗」修復）。會看到幾條
`InsecureKeyLengthWarning` 的警告，那是套件本身的提醒，不影響測試結果。

**啟動後端**：

```bash
uvicorn app.main:app --port 8006
```
實測 `curl http://localhost:8006/api/health`：
```json
{"status":"ok"}
```

**（選做）實測索引與 N+1 修復的實際數字**：

```bash
python scripts/explain_query_plans.py
python scripts/n_plus_one_demo.py
```
輸出直接被收錄進 [`docs/DATABASE.md`](docs/DATABASE.md)，這裡不重複貼。

### 前台（開發模式，另開一個終端機視窗）

```bash
cd frontend
npm install
npm run dev
```
瀏覽器打開 `http://localhost:5173/`；`/api` 與 `/ws` 請求都會透過 Vite
proxy 轉給後端的 8006 埠（見 `frontend/vite.config.js`）。

**跑測試**：
```bash
npx vitest run
```
實測輸出：
```
 Test Files  6 passed (6)
      Tests  33 passed (33)
```
（`Cart.test.jsx` 新增 2 個：已下架品項顯示「已下架」徽章＋停用數量調整與
結帳按鈕、正常品項時「前往結帳」維持可點擊，見「已下架商品體驗」修復。）

**打包正式版**：
```bash
npm run build
```
實測輸出：
```
dist/index.html                   0.66 kB │ gzip:  0.46 kB
dist/assets/index-CeBWoskw.css   12.91 kB │ gzip:  2.89 kB
dist/assets/index-DXfBPRRe.js   271.09 kB │ gzip: 84.56 kB

✓ built in 382ms
```
build 檔名雜湊與大小會隨相依 patch 版本浮動、秒數會隨機器負載浮動，重點是
build 成功產出這三類檔案，以你實際看到的為準。

### 後台（開發模式，再另開一個終端機視窗）

```bash
cd admin
npm install
npm run dev
```
瀏覽器打開 `http://localhost:5176/admin/`（注意要有 `/admin/` 路徑）。

**跑測試**：
```bash
npx vitest run
```
實測輸出：
```
 Test Files  4 passed (4)
      Tests  9 passed (9)
```

**打包正式版**：
```bash
npm run build
```
實測輸出：
```
dist/index.html                   0.47 kB │ gzip:  0.31 kB
dist/assets/index-W5vmnr0h.css    5.78 kB │ gzip:  1.64 kB
dist/assets/index-DElvUPQ5.js   254.18 kB │ gzip: 79.80 kB

✓ built in 350ms
```
build 檔名雜湊與大小會隨相依 patch 版本浮動、秒數會隨機器負載浮動，重點是
build 成功產出這三類檔案，以你實際看到的為準。

### 三合一正式模式（重啟後端後，前台跟後台會一起被 serve 出來）

```bash
cd ../backend && uvicorn app.main:app --port 8006
```
實測驗證：
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8006/
# 200（前台）
curl -s -o /dev/null -w "%{http_code}" http://localhost:8006/admin/
# 200（後台）
```

### 壓力測試煙囪跑（快速確認腳本能動，完整兩輪對照見 PERFORMANCE_REPORT.md）

```bash
cd ../loadtest
python asyncio_load_test.py --host http://localhost:8006 --concurrency 10 --duration 15
```
實測輸出：
```
總請求數：11918
RPS：794.53
p50 延遲：6.6 ms
p95 延遲：36.3 ms
錯誤率：0.00%
```

## 逐步教學導覽

1. **WebSocket 連線的完整生命週期**：`backend/app/routers/ws.py` 的
   `admin_orders_ws()`——先驗證 query string 的 `token`，失敗就
   `accept()` 後立刻用自訂 close code（`4401`/`4403`）關閉；成功就交給
   `ws_manager.py` 的 `connect_admin()` 加入連線清單，`receive_text()`
   卡在迴圈裡等待斷線，斷線時的 `finally` 保證一定會呼叫
   `disconnect_admin()`——連線的「加入」與「移除」永遠成對出現。
2. **訊息怎麼從 HTTP 請求變成 WebSocket 推播**：`backend/app/routers/
   orders.py` 的 `create_order_route()` 在寫入訂單成功後，呼叫
   `await manager.broadcast_admin({...})`——這正是這支路由要改成
   `async def` 的原因，也是意外揭露 stage5 併發 bug 的起點（見下方第 8 點）。
3. **SSE 串流的核心：async generator**：`backend/app/routers/support.py`
   的 `_stream_reply()` 每次 `yield` 一段文字，`StreamingResponse` 立刻把
   它送給瀏覽器，不用等整個函式跑完；前端 `frontend/src/pages/Support.jsx`
   用 `EventSource` 接收，逐段接起來做出打字機效果。
4. **索引怎麼查證有沒有真的被用到**：`backend/scripts/
   explain_query_plans.py` 用 `EXPLAIN QUERY PLAN` 實測「加索引前是
   `SCAN products`（全表掃描），加索引後變成
   `SEARCH products USING INDEX ...`」，這是判斷索引有沒有生效的標準方法，
   不是看 schema.sql 裡有寫就假設一定有用。
5. **N+1 查詢怎麼被量出來的**：`backend/scripts/n_plus_one_demo.py` 用
   `sqlite3.Connection.set_trace_callback()`（SQLite 官方介面，每執行一句
   SQL 就呼叫一次 callback）實測「7 筆訂單，舊寫法發出 8 次查詢，新寫法
   發出 1 次」，不是憑印象宣稱「應該有變快」。
6. **TTL 快取與 cache invalidation**：`backend/app/cache.py` 的
   `TTLCache` 用 `clock` 參數讓測試可以注入假時鐘，不用真的等 30 秒；
   `backend/app/routers/admin.py` 的商品新增/編輯端點在寫入成功後呼叫
   `products_cache.invalidate_all()`，示範「資料改變時必須記得通知快取」
   這個 cache invalidation 最基本也最容易漏掉的一步。
7. **前端斷線重連的 exponential backoff**：
   `frontend/src/hooks/useOrdersSocket.js` 的 `connect()` 函式，`onclose`
   時依據 close code 判斷「該不該重連」，該重連的話 backoff 時間每次翻倍
   （上限 16 秒），連上後重設回 1 秒——避免暴力重連把伺服器打垮。

## 驗收清單

- [x] 後端測試 ≥55 個且全綠（實測 117 個，見上方「快速開始」）
- [x] 前台 vitest 全綠（實測 33 個）；後台 build 成功＋測試全綠（實測 9 個：
      `Login.test.jsx` 3 個、`Dashboard.test.jsx` 2 個、`Members.test.jsx`
      1 個、`client.test.js` 3 個）
- [x] 購物車已下架商品體驗：商品被下架後仍留在購物車、`GET /api/cart` 標示
      `is_active:false`、購物車頁顯示「已下架」徽章並停用結帳按鈕、建單仍被
      409 擋下（實測見 [`API.md`](docs/API.md)「購物車 cart」「訂單 orders」
      兩節）
- [x] WebSocket：`TestClient.websocket_connect()` 實測認證失敗（401/403
      close code）、admin 收到建單/付款事件、顧客本人收到狀態變更事件、
      頻道隔離（別人的事件收不到）皆已測試（見 `backend/tests/test_ws.py`）
- [x] SSE：串流回應逐塊到齊、規則命中/未命中、不需要登入皆已測試（見
      `backend/tests/test_support_sse.py`）
- [x] TTL 快取：命中/過期/失效皆已測試（見 `backend/tests/test_cache.py`）
- [x] 索引存在性檢查：五個索引皆已用 `PRAGMA index_list` 實測存在（見
      `backend/tests/test_database_indexes.py`）
- [x] N+1 修復：實測查詢次數對照（8 次 vs 1 次），非估算（見
      `backend/tests/test_n_plus_one_demo.py`）
- [x] 真實 WebSocket 連線煙囪測試：用 Python `websockets` 套件實連，收到
      的 JSON 事件已貼在 [`REALTIME.md`](docs/REALTIME.md)
- [x] 壓力測試：locust 混合場景，50 併發／60 秒，stage5 vs stage6 完整
      對照（含意外發現的併發 bug），見
      [`PERFORMANCE_REPORT.md`](docs/PERFORMANCE_REPORT.md)
- [x] 含技術選型表、關鍵程式片段、雲端架構圖、瓶頸分析的技術文件齊全
- [ ] 部署到你選擇的平台（見 [`docs/DEPLOY.md`](docs/DEPLOY.md) 學員交付
      檢查表，由學員自行完成）

## 延伸挑戰

1. `app/cache.py` 的 `TTLCache` 目前是「整包清空」的失效策略（見該檔案
   `invalidate_all()` 的說明）。試著改成精準失效：只清掉「被編輯的那個
   商品所屬分類」相關的 key，需要想清楚一件事——如果商品的 `category`
   欄位本身被改了（從 `beans` 改成 `gear`），舊分類跟新分類的快取都要清，
   不能只清其中一邊。
2. 目前 `ConnectionManager`（`app/ws_manager.py`）只存在單一 process 的
   記憶體裡，`docs/ARCHITECTURE.md`「uvicorn workers」一節解釋了為什麼
   多 worker 會出問題。試著設計（不用真的實作，畫出架構圖＋文字說明即可）：
   如果要用 Redis Pub/Sub 讓多個 worker 之間同步 WebSocket 訊息，
   `broadcast_admin()` 這支函式的邏輯要怎麼改？
3. `loadtest/locustfile.py` 目前只測「匿名逛商品」與「登入完整下單流」
   兩種場景。試著加一個新的 `HttpUser` 子類別，專門測試「後台管理員同時
   打開 Dashboard、瘋狂重整」的場景，觀察 `GET /api/admin/summary`
   （沒有快取的端點）在高併發下的表現，跟有快取的 `GET /api/products`
   對照。
4. `backend/app/routers/support.py` 的規則式 FAQ 目前只有 5 條規則。
   試著把它改接一個真的 LLM API（需要你自己的 API key，本課程沒有提供），
   保留 SSE 串流的介面不變，想清楚：串流過程中如果 LLM API 回傳錯誤，
   要怎麼優雅地把錯誤訊息也用同樣的 SSE 格式送給前端？

## 教學簡化聲明

- **`SECRET_KEY` 開發預設值是固定字串**：跟 stage4/stage5 一致，
  `.env.example` 裡的 `dev-secret-change-me` 只適合本機開發，正式部署務必
  換成長隨機字串。這個值還是預設值時，後端啟動時會在終端機印出醒目警告
  （見 `backend/app/config.py` 的 `warn_if_default_secret_key()`），本機
  開發可以忽略，部署前務必處理。
- **WebSocket 認證用 query string，不是 header**：瀏覽器原生 `WebSocket`
  建構子沒辦法附加自訂 header，這是瀏覽器 API 的先天限制，不是本專案的
  設計選擇；缺點是 token 會出現在伺服器存取日誌，正式產品更嚴謹的做法是
  改用一次性票證，見 `backend/app/routers/ws.py` 開頭的說明。
- **客服助理不是真的 AI**：規則式 FAQ 比對，完整聲明見
  `backend/app/routers/support.py` 開頭；真實產品這裡通常接 LLM
  streaming，介面（SSE 逐字送出文字）長得完全一樣。
- **快取／WebSocket 連線清單只支援單一 worker**：見上方「延伸挑戰」第 2
  題與 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)「uvicorn workers」
  一節，多 worker 需要 Redis 之類的外部共享狀態，本課程刻意不實作。
- **GZip 對本機壓測數字的貢獻量不出來**：見
  [`docs/PERFORMANCE_REPORT.md`](docs/PERFORMANCE_REPORT.md) 第 6 節，
  GZip 確實有正確運作（實測 `content-encoding: gzip`），但本機
  localhost 測試沒有網路延遲/頻寬限制，量不出它對延遲的直接貢獻，這裡
  誠實聲明「有做、有驗證、但這份測試方法看不出效果」而不是硬掰一個數字。
- **壓力測試數字受機器規格影響**：本報告的 RPS／延遲數字只在本機環境下
  有意義，不能直接當作「正式環境能扛多少人」的保證，完整聲明見
  [`docs/PERFORMANCE_REPORT.md`](docs/PERFORMANCE_REPORT.md) 開頭。
- **CI 只做到 build+test，deploy 留白**：master spec 規定不呼叫任何需要
  帳號/金鑰的雲端服務，`ci/github-actions-ci.yml` 因此沒有真正的部署步驟，
  完整理由見 [`docs/CICD.md`](docs/CICD.md) 第 3 節。
- **前端 WebSocket／SSE hook 沒有自動化測試**：`useOrdersSocket.js` 等
  hook 依賴瀏覽器原生的 `WebSocket`／`EventSource` API，vitest 預設的
  jsdom 測試環境沒有完整實作這兩個 API，要測試需要額外的 mock 套件（不在
  master spec 的依賴白名單內），這裡誠實記錄為未測試範圍——這兩個 hook
  的行為是透過真實瀏覽器手動走查＋後端 `TestClient.websocket_connect()`
  的整合測試間接驗證，不是完全沒驗證過。

## 作者與聯絡資訊

本專案為呂紹民（Darren Lu）製作的教學範例，供學員學習全端服務開發使用。如果對本文件或專案有任何問題，或有課程教學、顧問諮詢、專案導入需求，歡迎與我聯絡。

- Email：kevin868686@gmail.com
- LinkedIn：https://www.linkedin.com/in/shaominglu
- Facebook：https://www.facebook.com/darrenlu86
