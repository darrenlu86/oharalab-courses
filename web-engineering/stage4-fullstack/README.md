# Stage 4 — 互動式動態網頁·後端（WEB-16）

回上層：[網站工程六階段課程總覽](../README.md)

BrewGo 沖沖咖啡「線上選購」全端教學專案：把 stage3 的純前端 SPA 接上真正的
FastAPI 後端與 SQLite 資料庫，會員註冊登入、伺服器端購物車、真實庫存檢查、
訂單落庫全部改成真的，不再是打包進前端的假資料。

> 本專案是教學範例。**沒有金流、沒有付款流程**：`POST /api/orders` 建單當下就
> 視為成立、直接扣庫存，沒有「付款成功才算數」這個中間狀態——真實電商至少
> 需要金流串接與 webhook 回呼確認付款，這是 stage5 才會處理的範圍，詳見下方
> 「教學簡化聲明」與 [`docs/DATABASE.md`](docs/DATABASE.md)。

## 這一階段你會做出什麼

一個前後端分離、但可以合體部署的完整購物流程：

- **會員系統**：Email + 密碼註冊登入（bcrypt 雜湊、JWT 24 小時過期），Header
  即時顯示登入狀態
- **商品列表／詳情**：分類篩選＋關鍵字搜尋改成真的打後端 API、由 SQLite 的
  SQL 做篩選，不再是前端對本地陣列 `.filter()`
- **伺服器端購物車**：登入後購物車存在資料庫，換裝置登入同一個帳號還在；
  加入／改數量／移除都會即時向後端查詢當下庫存，超過庫存回 409
  並顯示錯誤訊息
- **建立訂單**：結帳送出會真的在資料庫建立訂單、扣減商品庫存、清空購物車；
  訂單查詢改打 API，只能看到自己帳號底下的訂單
- **匯率 widget**：沿用 stage3 的第三方 API 串接，沒有改動
- 開發模式（Vite proxy）與正式合體模式（FastAPI serve 前端 build 產物）
  兩種跑法都能用

## 對應課綱與交付產出

課綱原文（WEB-16）：「使用後端框架建立 RESTful API 與資料庫，並串接前端完成一個
有資料讀寫的互動應用。完成後產出：前後端專案架構說明、可實際操作完整功能的
前後端部署連結、含 ER Diagram 與 API 端點清單的資料庫 Schema 與 API 文件。」

| 產出要求 | 對應本 repo 位置 |
|---|---|
| 有資料讀寫的互動應用本身 | `backend/` + `frontend/`，見下方「逐步教學導覽」 |
| 產出 1：前後端專案架構說明 | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| 產出 2：可實際操作完整功能的前後端部署連結 | 課程本身不代學員部署 → [`docs/DEPLOY.md`](docs/DEPLOY.md) 提供本地驗證（已實測）＋主流平台部署教學＋學員交付檢查表 |
| 產出 3：含 ER Diagram 與 API 端點清單的資料庫 Schema 與 API 文件 | [`docs/DATABASE.md`](docs/DATABASE.md)（ER Diagram＋逐表說明）＋[`docs/API.md`](docs/API.md)（端點總覽＋實測 request/response） |

## 與上一階段的差異

這一節基於實際讀過 `stage3-spa/` 的程式碼寫成，不是憑印象。stage3 是純前端
SPA：商品資料是打包進前端的 `src/data/products.json`，購物車用 React Context
（`CartContext.jsx`）搭配 `useReducer`（`cartReducer.js`）管理，全部狀態存在
瀏覽器的 `localStorage`，訂單靠 `utils/generateOrderId.js` 用 `Math.random()`
產生的 `BG-XXXXXXXX` 編號、存進 `utils/ordersStorage.js`。stage3 README「與上一
階段的差異」自己也點出這個限制的代價：「換一台裝置看不到自己的購物車與訂單、
沒有真正的庫存管理…也沒有真正的付款」。stage4 就是把這些「假的」一一換成「真的」：

1. **新增整個後端**（stage3 完全沒有 `backend/` 資料夾）：FastAPI + SQLite，
   5 張資料表（`users` / `products` / `cart_items` / `orders` / `order_items`），
   JWT 認證、bcrypt 密碼雜湊，12 支 REST API（見 [`docs/API.md`](docs/API.md)）。
2. **新增 `frontend/src/api/client.js`**（stage3 沒有這個檔案，因為沒有後端可以
   呼叫）：集中 fetch 封裝，統一處理 `/api` 前綴、Authorization header、401
   自動導登入、錯誤訊息解析。
3. **新增 `frontend/src/context/AuthContext.jsx`**（stage3 沒有登入概念，
   完全不需要）：全站共享的登入狀態，跟 `CartContext` 一樣用 Context 集中管理。
4. **`CartContext.jsx` 整個改造**：stage3 版本（`useReducer` + `cartReducer.js`
   純函式 + `localStorage`）被拿掉，改成呼叫 API、把後端回傳的最新購物車內容
   整包存進 `useState`——「購物車狀態怎麼變化」的邏輯搬到後端了，前端不再需要
   reducer。庫存上限從「加入購物車當下的快照」（stage3 `cartReducer.js` 開頭
   註解點名的限制）變成「後端當下的即時值」。
5. **商品列表／詳情、訂單相關頁面全部從讀本地 JSON／localStorage 改成
   `fetch`**：`Products.jsx`、`ProductDetail.jsx`、`Cart.jsx`、`Checkout.jsx`、
   `Orders.jsx`、`OrderComplete.jsx` 都因此需要處理 stage3 完全不用考慮的
   loading／錯誤狀態（例如「後端還沒啟動」、「庫存被別人買走了」）。
6. **新增 `Login.jsx` 頁面**與 `App.jsx` 的 `/login` 路由（stage3 的路由表完全
   沒有這一條）。
7. **`Checkout.jsx` 表單欄位簡化**：stage3 有姓名／手機／地址／備註四欄，
   stage4 收斂成姓名／地址兩欄，因為後端 `OrderCreateIn`（見
   `backend/app/schemas.py`）目前只收這兩個欄位——這是刻意的教學簡化，
   完整取捨說明在 `frontend/src/pages/Checkout.jsx` 檔案開頭的註解。
8. **元件層幾乎沒動**：`ProductCard` / `PriceTag` / `StockBadge` /
   `QuantityStepper` / `CategoryTabs` / `SearchBox` / `Footer`（文字微調）/
   `NotFound` 全部原封不動或只改一個欄位名稱（`image` → `image_url`，對齊
   後端回應的欄位命名），`ExchangeRateContext.jsx` 與 `useExchangeRate.js`
   完全沒有改動——第三方 API 串接這件事跟「資料層從假的換成真的」無關，
   不需要跟著重寫。

**代價（誠實聲明，也是下一階段的入口）**：本階段還是沒有付款/金流，
`orders.status` 目前只有 `pending` 一種值；沒有管理後台，商品資料只能透過
`seed_products.json` 手動維護；沒有 debounce 的關鍵字搜尋在使用者快速輸入時
會連續打好幾次 API。這些問題需要更完整的後台管理與使用者體驗優化，是
stage5（前台＋後台）要處理的範圍。

## 課綱單元表

| 單元 | 學什麼 | 對應檔案 |
|---|---|---|
| 1. RESTful API 設計 | 資源導向路由、HTTP 方法對應語意（GET/POST/PATCH/DELETE）、狀態碼 | `backend/app/routers/`，說明見 [`API.md`](docs/API.md) |
| 2. 資料庫 schema 設計 | 資料表關聯、外鍵、UNIQUE/CHECK 約束、資料快照 vs 即時查詢 | `backend/app/db/schema.sql`，說明見 [`DATABASE.md`](docs/DATABASE.md) |
| 3. 認證與授權 | bcrypt 密碼雜湊、JWT 簽發/驗證、`Depends()` 依賴注入 | `backend/app/security.py`、`backend/app/deps.py` |
| 4. 並發安全 | 條件式 `UPDATE` 防止超賣、單一連線交易的 commit/rollback | `backend/app/db/database.py:106`（`decrease_stock`）、`backend/app/routers/orders.py:53` |
| 5. 前端串接真實後端 | 集中 fetch 封裝、token 管理、401 自動導登入 | `frontend/src/api/client.js:48` |
| 6. 前端狀態管理接上伺服器 | Context 從管理本地 state 改成同步伺服器狀態 | `frontend/src/context/CartContext.jsx`、`AuthContext.jsx` |
| 7. 開發環境代理 vs CORS | Vite proxy、`CORSMiddleware`、同源 vs 跨網域 | `frontend/vite.config.js:17`、`backend/app/main.py` |
| 8. 後端測試 | pytest + `TestClient`、`tmp_path` 隔離資料庫 | `backend/tests/` |
| 9. 全端部署 | 開發分離模式、正式合體模式、SPA fallback | [`DEPLOY.md`](docs/DEPLOY.md)、`backend/app/main.py:64`（`serve_spa`） |

## 環境需求

- Python **3.10 以上**（本次建置實測環境為 **3.13.11**）
- Node.js **20 以上**（本次建置實測環境為 **v24.11.1**，npm **11.6.2**）
- 一個現代瀏覽器

## 快速開始

以下每一步都附上本次撰寫教材時**實際執行**的輸出，指令假設你已經
`cd stage4-fullstack`。

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
預期輸出：
```
建立資料表於：/你的路徑/backend/data/brewgo.db
已匯入 12 筆種子商品資料。
SQLite 資料庫初始化完成！
```

> 防呆設計：這支腳本重複執行不會刪掉既有資料，只會印出提示叫你要不要加
> `--reset`，理由跟做法見 `backend/scripts/init_db.py` 檔案開頭的註解。

**跑測試**：

```bash
pytest -q
```
實測結果：**51 個測試全部通過**（`test_auth.py` 9 個、`test_products.py` 10 個、
`test_cart.py` 16 個、`test_orders.py` 11 個、`test_config.py` 5 個——`test_config.py`
是 `SECRET_KEY` 預設值偵測 helper 的測試，`test_products.py`／`test_cart.py`／
`test_orders.py` 各多了一支「超界 id 回 422 不是 500」的代表性測試）。會看到
幾條 `InsecureKeyLengthWarning`（測試用的 `SECRET_KEY` 故意設得比較短）跟
`httpx`/`starlette` 的 deprecation 警告，那是套件本身的提醒，不影響測試結果。

**啟動後端**：

```bash
uvicorn app.main:app --port 8004
```
預期看到 log 出現 `Application startup complete.`；另開一個終端機執行
`curl http://localhost:8004/api/health`，預期回應：
```json
{"status":"ok"}
```

### 前端（開發模式，另開一個終端機視窗）

```bash
cd frontend
npm install
```
實測輸出（節錄）：
```
added 117 packages, and audited 118 packages in 2s
...
found 0 vulnerabilities
```
套件數與秒數會隨相依套件版本與網路環境浮動，重點是 `found 0 vulnerabilities`，
以你實際看到的為準。

**跑測試**：
```bash
npm test -- --run
```
實測輸出：
```
 Test Files  6 passed (6)
      Tests  31 passed (31)
```

**啟動開發伺服器**：
```bash
npm run dev
```
預期看到終端機印出本地網址（通常是 `http://localhost:5173/`），瀏覽器打開
會看到 BrewGo 首頁；前端所有 `/api/...` 請求會透過 Vite proxy 轉給後端的 8004
埠（見 `frontend/vite.config.js:17` 的說明），確認後端也已經在跑，否則首頁
「精選商品」會顯示讀取失敗。

**打包正式版**：
```bash
npm run build
```
實測輸出：
```
dist/index.html                   0.66 kB │ gzip:  0.47 kB
dist/assets/index-MKKrbm6k.css   10.77 kB │ gzip:  2.44 kB
dist/assets/index-Xo2z7aIf.js   261.26 kB │ gzip: 82.07 kB

✓ built in 362ms
```
build 檔名雜湊與大小會隨相依 patch 版本浮動，重點是 build 成功產出這三類檔案，
以你實際看到的為準。build 完之後重新啟動後端（`uvicorn app.main:app --port 8004`），後端會自動
偵測到 `frontend/dist/` 存在並直接 serve 這份前端，`curl -o /dev/null -w
"%{http_code}" http://localhost:8004/` 實測回應 `200`。完整驗證（含 SPA
client-side 路由的 fallback）見 [`docs/DEPLOY.md`](docs/DEPLOY.md)。

## 逐步教學導覽

1. **後端入口與正式模式的 SPA fallback**：[`backend/app/main.py:64`](backend/app/main.py#L64)
   判斷 `frontend/dist/` 是否存在才掛載靜態檔；[`main.py:83`](backend/app/main.py#L83)
   的 `serve_spa()` 是本階段跟 meowshop 最大的技術差異——因為前端是
   client-side routing，找不到對應檔案就一律回 `index.html`，讓 react-router
   自己接手判斷要顯示哪個頁面。
2. **並發安全的扣庫存**：[`backend/app/db/database.py:106`](backend/app/db/database.py#L106)
   的 `decrease_stock()` 用條件式 `UPDATE products SET stock = stock - ?
   WHERE id = ? AND stock >= ?` 一句 SQL 同時完成「檢查」與「扣減」，避免
   「先讀庫存、判斷夠不夠、再扣」拆成兩步驟時的 race condition。
3. **多品項訂單的交易一致性**：[`backend/app/routers/orders.py:53`](backend/app/routers/orders.py#L53)
   的迴圈裡，扣庫存失敗會立刻 `conn.rollback()`，確保「全部品項都扣成功」跟
   「完全不變」是唯二可能的結果，不會留下扣了一半的中間狀態；完整測試見
   `backend/tests/test_orders.py` 的 `test_create_order_insufficient_stock_returns_409_and_no_order_created`。
4. **前端集中 fetch 封裝**：[`frontend/src/api/client.js:48`](frontend/src/api/client.js#L48)
   的 `apiFetch()` 是全站唯一呼叫後端的入口，自動帶 `/api` 前綴、
   Authorization header、解析 `{"detail": "..."}` 錯誤格式；`AuthContext.jsx`
   在 [第 35 行](frontend/src/context/AuthContext.jsx#L35) 註冊「收到 401 該
   怎麼辦」（清登入態、導去 `/login`）。
5. **購物車從本地狀態變成伺服器同步**：[`frontend/src/context/CartContext.jsx:27`](frontend/src/context/CartContext.jsx#L27)
   的 `refreshCart()` 取代了 stage3 的 `useReducer` + `localStorage`，未登入時
   直接把購物車視為空（[`CartContext.jsx:31`](frontend/src/context/CartContext.jsx#L31)），
   因為 `/api/cart` 本來就需要登入才查得到。
6. **開發環境代理**：[`frontend/vite.config.js:17`](frontend/vite.config.js#L17)
   的 `server.proxy` 讓開發時的 `/api` 請求在瀏覽器眼中永遠是同源請求，完全
   不會觸發 CORS——這跟正式合體模式（前後端本來就同源）殊途同歸，只有
   「前後端分開部署」才需要真的處理 CORS，見 [`docs/DEPLOY.md`](docs/DEPLOY.md)。
7. **後端測試如何隔離資料庫**：`backend/tests/conftest.py` 用 pytest 的
   `tmp_path` fixture 幫每個測試建一個獨立的暫存 SQLite 檔案，搭配
   `monkeypatch.setenv("SQLITE_PATH", ...)` 讓 `app.config.get_settings()`
   （刻意設計成每次呼叫都重新讀環境變數）在測試期間指向暫存檔案，完全不會
   動到你本機 `backend/data/brewgo.db` 的資料。

## 驗收清單

- [x] 會員系統：註冊（含重複 email 409）、登入（含帳密錯誤 401，錯誤訊息不分
      是哪個錯）、JWT 驗證、`/api/auth/me`
- [x] 商品 API：分類篩選、關鍵字搜尋皆由後端 SQL 完成，商品詳情 404
- [x] 購物車：需登入、加入（含超庫存 409）、改數量（PATCH 覆蓋）、移除、
      跨裝置同一帳號共用
- [x] 建立訂單：扣庫存（實測驗證庫存數字真的變化）、清空購物車、僅能查到
      自己的訂單（別人的訂單一律 404）
- [x] 前後端串接：開發模式 proxy／正式模式合體 serve 皆已實測，含 SPA
      client-side 路由 fallback
- [x] 後端測試 ≥30 個且全綠（實測 51 個，見上方「快速開始」）
- [x] 前端測試 ≥15 個且全綠、fetch 一律 mock（實測 31 個，見上方「快速開始」）
- [x] ER Diagram 與 API 端點清單文件（[`DATABASE.md`](docs/DATABASE.md)、
      [`API.md`](docs/API.md)）
- [ ] 部署到你選擇的平台（見 [`docs/DEPLOY.md`](docs/DEPLOY.md) 學員交付檢查表，
      由學員自行完成）

## 延伸挑戰

1. 目前購物車操作沒有做樂觀更新（optimistic update），每次點擊都要等一次
   網路來回才會看到畫面變化。試著幫「移除商品」加上樂觀更新：先假設會成功、
   立刻從畫面上移除，如果後端回錯誤再復原並顯示錯誤訊息。
2. `Products.jsx` 的關鍵字搜尋目前每個字都會立刻打一次 API，沒有做 debounce。
   試著加上「使用者停止輸入 300ms 後才發出請求」的防抖動處理（stage3 的
   延伸挑戰也提過類似題目，這次要處理的是「打 API」而不是「改網址」的節流）。
3. 目前「建單」與「扣庫存」是同一個時間點，沒有付款流程。試著設計一套
   「建單先保留庫存 30 分鐘、超時自動釋放」的機制（提示：需要一個背景排程
   或是在下次讀取時檢查時間戳），並想清楚：如果使用者在保留期限內完成
   「付款」，該怎麼把保留轉成正式扣庫存？
4. 目前只有商品的擁有者（後端硬寫死的 12 筆種子資料）才看得到自己下的訂單。
   試著加一支只有你自己（不對外開放）能呼叫的除錯端點，列出全站目前的訂單
   總數與各狀態的統計——這是 stage5「後台管理」的一個小小預告。

## 教學簡化聲明

- **沒有付款/金流**：`orders.status` 目前只有 `pending` 一種值，建單當下就
  直接扣庫存。真實電商至少需要金流串接、webhook 回呼確認付款狀態，這是
  stage5 才會處理的範圍，完整取捨說明在 [`docs/DATABASE.md`](docs/DATABASE.md)
  「訂單狀態與扣庫存時機」一節。
- **沒有 Repository Pattern**：跟參考教材 meowshop 不同，`backend/app/db/database.py`
  沒有抽象介面層，因為本課程六個階段永遠只用 SQLite，永遠不會真的切換資料庫。
  完整理由見該檔案開頭的長註解與 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。
- **購物車沒有做樂觀更新**：每次加入／改數量／移除都要等後端回應才更新畫面，
  是刻意換取程式碼簡單、初學者好理解的取捨，代價是操作有感受得到的網路延遲。
- **未登入不能操作購物車，也沒有「訪客購物車合併」機制**：點「加入購物車」
  直接導去登入頁，不像很多正式電商會先讓訪客把商品放進一個本機暫存的購物車，
  登入後才合併——那種合併邏輯本身就有不少邊界情況要處理，對初學者是不必要的
  複雜度，理由見 `frontend/src/context/CartContext.jsx` 的註解。
- **結帳表單欄位比 stage3 少**：後端 `OrderCreateIn` 目前只收姓名與地址，
  拿掉了 stage3 的手機與備註欄位；要加回來需要同時改 `schemas.py`、
  `schema.sql` 與前端表單。
- **關鍵字搜尋沒有 debounce**：每個字都會立刻打一次 API，正式產品通常會加上
  防抖動處理減少不必要的請求量（見「延伸挑戰」第 2 題）。
- **`SECRET_KEY` 開發預設值是固定字串**：`.env.example` 裡的
  `dev-secret-change-me` 只適合本機開發，正式部署務必換成長隨機字串
  （`.env.example` 有附產生指令）。這個值還是預設值時，後端啟動時會在
  終端機印出醒目警告（見 `backend/app/config.py` 的
  `warn_if_default_secret_key()`），本機開發可以忽略，部署前務必處理。

## 作者與聯絡資訊

本專案為呂紹民（Darren Lu）製作的教學範例，供學員學習全端服務開發使用。如果對本文件或專案有任何問題，或有課程教學、顧問諮詢、專案導入需求，歡迎與我聯絡。

- Email：kevin868686@gmail.com
- LinkedIn：https://www.linkedin.com/in/shaominglu
- Facebook：https://www.facebook.com/darrenlu86
