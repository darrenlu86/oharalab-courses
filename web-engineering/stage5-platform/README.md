# Stage 5 — 完整應用系統·前台＋後台（WEB-17）

回上層：[網站工程六階段課程總覽](../README.md)

BrewGo 沖沖咖啡「線上選購＋店家後台」完整電商系統：把 stage4 的購物流程接上
真正的付款（模擬金流）、獨立的後台管理端（商品／訂單／會員／儀表板）、角色
權限，商品、訂單、付款、會員全部是真的資料，前台顧客買東西、後台店長管生意。

> **金流警示：本站的付款功能是自建的模擬金流（mock payment），完全沒有串接
> 任何真實的第三方金流服務，不會有任何一筆真實金錢往來。** 不管你在付款頁面
> 輸入什麼卡號，都只是後端用「卡號字串」做規則判斷（見下方測試卡號表），
> 不會、也不可能真的請款。**請勿把本專案原封不動拿去對外收費使用。**

## 這一階段你會做出什麼

一個前台／後台分離、但可以合體部署的完整電商系統：

- **前台結帳兩步流程**：建單（不扣庫存）→ 付款頁（測試卡號表顯示在頁面上）
  → 成功導向訂單詳情、失敗可以換卡號重試
- **訂單狀態機**：`pending → paid →（admin）shipped → completed`，
  `pending/failed → cancelled`（顧客本人或 admin 都能取消 pending 訂單），
  `paid →（admin）cancelled`（僅 admin 可取消已付款訂單，不退款，見「教學簡化聲明」）
- **獨立後台管理端**（全新 `admin/` Vite React app）：登入（非 admin 被拒）、
  Dashboard（總營收／訂單數／待出貨數／低庫存清單／會員數，全部真實 SQL
  聚合）、商品管理（新增／編輯／上下架，不做刪除）、訂單管理（狀態篩選＋
  流轉按鈕）、會員清單（唯讀，不含密碼欄位）
- **角色權限**：`users.role` 分 `customer`／`admin`，全部 `/api/admin/*`
  端點都有權限檢查，customer 打會回 403（不是 401）

## 對應課綱與交付產出

課綱原文（WEB-17）：「完成一個含前台用戶端與後台管理端的完整應用系統
（CRM、電商、內容平台等），並部署至雲端。完成後產出：前後台專案架構說明、
含測試帳號的雲端部署連結（前台/後台）、含系統架構圖與 API 文件與資料庫設計
的技術文件。」

| 產出要求 | 對應本 repo 位置 |
|---|---|
| 含前台用戶端與後台管理端的完整應用系統本身 | `backend/` + `frontend/` + `admin/`，見下方「逐步教學導覽」 |
| 產出 1：前後台專案架構說明 | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| 產出 2：含測試帳號的雲端部署連結（前台/後台） | 課程本身不代學員部署 → 測試帳號見下方「快速開始」章節開頭表格；[`docs/DEPLOY.md`](docs/DEPLOY.md) 提供本地驗證（已實測）＋部署拓撲圖＋主流平台部署教學＋學員交付檢查表（讓學員填自己的連結） |
| 產出 3：含系統架構圖與 API 文件與資料庫設計的技術文件 | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)（系統架構圖）＋[`docs/API.md`](docs/API.md)（端點清單＋實測 request/response）＋[`docs/DATABASE.md`](docs/DATABASE.md)（ER 圖＋資料庫設計）＋[`docs/SYSTEM_DESIGN.md`](docs/SYSTEM_DESIGN.md)（權限矩陣＋狀態機＋付款流程） |

## 與上一階段的差異

這一節基於實際讀過 `stage4-fullstack/` 的程式碼（backend 與 frontend 全部
檔案）寫成，不是憑印象；builder 先完整複製 stage4 的 `backend/` 與
`frontend/`，再逐項擴充——`stage4-fullstack/` 本身沒有被改動一個字。

1. **新增獨立的後台 app（`admin/`）**：stage4 完全沒有這個資料夾，也沒有任何
   管理介面。這是 stage4 README「教學簡化聲明」自己點出的限制：「沒有管理
   後台，商品資料只能透過 `seed_products.json` 手動維護」——本階段用一個全新
   的 Vite React app 補上，跟前台是各自獨立的 `package.json`／build 產物，
   理由見 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) 第 3-4 節。

2. **`users` 新增 `role` 欄位**：stage4 的 `schema.sql` 完全沒有這個欄位
   （見 stage4 `backend/app/db/schema.sql:7-13`），所有使用者一視同仁。本階段
   需要區分「誰能打 `/api/admin/*`」，新增 `role`（`customer`/`admin`），
   公開的 `POST /api/auth/register` 端點（stage4 就存在、程式碼幾乎沒動）
   永遠只會建立 `customer` 角色——管理員帳號只能靠 seed 資料建立。

3. **付款流程與扣庫存時機整個演進**：stage4 完全沒有付款概念，`orders.status`
   的 `CHECK` 約束只允許 `'pending'` 一種值（見 stage4
   `backend/app/db/schema.sql:40-41`），`create_order_route()` 在建單當下就
   直接呼叫 `decrease_stock()`（見 stage4
   `backend/app/routers/orders.py:53-65`）。**這是本階段最重要的架構演進**：
   加入 `/api/payments/mock`（全新模組）之後，「建單」跟「付款」變成兩個
   獨立的時間點，如果繼續在建單當下扣庫存，會出現「下單但沒付款」的訂單
   長期佔用庫存、讓真正想買、也準備好要付款的顧客反而買不到的問題——所以
   本階段把 `create_order_route()` 改成完全不動庫存，`decrease_stock()`
   延後到 `mock_payment_route()` 付款成功那一刻才呼叫。完整取捨見
   [`docs/DATABASE.md`](docs/DATABASE.md)「訂單狀態與扣庫存時機」一節。

4. **`products` 新增 `is_active` 欄位**：stage4 的 `schema.sql`（見
   `backend/app/db/schema.sql:15-24`）完全沒有這個欄位，12 筆商品在整個
   stage4 生命週期裡都是「上架」狀態。本階段有了後台商品管理，新增
   `is_active` 做軟刪除（下架），前台 `GET /api/products` 只回傳
   `is_active=1` 的商品，下架商品的詳情頁回 404（跟商品不存在共用同一個
   狀態碼），但**不做真正的 `DELETE`**——保留歷史訂單品項快照的完整性
   （教學上的資料保護點）。

5. **新增訂單狀態機模組 `app/order_state.py`**：stage4 完全沒有這個檔案
   （不需要，訂單只有一種狀態）。本階段訂單有六種合法狀態
   （`pending`/`paid`/`failed`/`shipped`/`completed`/`cancelled`），合法轉移
   規則集中在這個模組，`orders.py`／`payments.py`／`admin.py` 三個路由共用
   同一份規則，不會各自維護一份容易漏改的邏輯，完整狀態圖見
   [`docs/SYSTEM_DESIGN.md`](docs/SYSTEM_DESIGN.md)。

6. **新增 `require_admin` 依賴**：stage4 的 `app/deps.py`（見該檔案）只有
   `get_db` 與 `get_current_user` 兩支依賴，沒有角色檢查的概念。本階段疊在
   `get_current_user` 之上新增 `require_admin`，角色不是 `admin` 回 403
   （跟「沒登入」的 401 明確區分語意）。

7. **前台結帳從一步變兩步**：stage4 的 `Checkout.jsx` 送出表單當下同時完成
   「建單」跟「（沒有真的存在的）付款」（見 stage4
   `frontend/src/pages/Checkout.jsx` 的 `handleSubmit`）。本階段 `Checkout.jsx`
   改成只負責「填地址 → 建單」，建好之後導去全新的 `pages/Pay.jsx`（stage4
   完全沒有這個檔案）繼續付款流程；`Orders.jsx` 也新增了狀態徽章、
   「去付款」／「取消訂單」的操作按鈕（stage4 版本完全是唯讀的訂單列表，
   沒有任何互動按鈕）。

8. **元件與其他 Context 幾乎沒動**：`ProductCard`／`PriceTag`／`StockBadge`／
   `QuantityStepper`／`CategoryTabs`／`SearchBox`（沿用 stage4 完全沒改）、
   `AuthContext.jsx`／`CartContext.jsx`／`ExchangeRateContext.jsx`（沿用
   stage4，`AuthContext` 讀寫的 `UserPublic` 現在多了 `role` 欄位，元件本身
   沒有因此改邏輯）——資料層的擴充（付款、狀態機、後台）不影響「怎麼呈現
   商品」「怎麼管登入態」這些既有邏輯，這也印證了 stage4 分層設計本身是
   撐得住擴充的。

## 課綱單元表

| 單元 | 學什麼 | 對應檔案 |
|---|---|---|
| 1. 訂單狀態機設計 | 有限狀態機、合法/非法轉移驗證、集中規則避免邏輯散落 | `backend/app/order_state.py`，說明見 [`SYSTEM_DESIGN.md`](docs/SYSTEM_DESIGN.md) |
| 2. 付款流程與交易一致性 | 「建單」與「付款」分離、扣庫存時機、rollback 保證原子性 | `backend/app/routers/payments.py`，說明見 [`DATABASE.md`](docs/DATABASE.md) |
| 3. 角色權限設計（RBAC） | `role` 欄位、依賴注入疊加（`require_admin` 疊在 `get_current_user` 之上）、401 vs 403 | `backend/app/deps.py`、`backend/app/routers/admin.py`，權限矩陣見 [`SYSTEM_DESIGN.md`](docs/SYSTEM_DESIGN.md) |
| 4. 軟刪除與資料保護 | `is_active` 下架 vs 真正 DELETE、保留歷史資料完整性 | `backend/app/db/database.py`（`update_product`）、`schema.sql` |
| 5. 後台聚合查詢 | SQL 聚合（`SUM`／`COUNT`）取代前端重算、後端算好給前端顯示 | `backend/app/db/database.py`（`admin_summary`），前端見 `admin/src/pages/Dashboard.jsx` |
| 6. 多應用前端架構 | 獨立 Vite app（各自 `package.json`／`base` 設定）、後端多組 SPA fallback | `admin/vite.config.js`、`backend/app/main.py`，說明見 [`ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| 7. 前端路由保護 | 整頁擋登入態（`ProtectedLayout`）vs 單支 API 擋（前台的作法） | `admin/src/App.jsx` |
| 8. 後端測試（狀態機／權限） | pytest 驗證合法/非法轉移、403 vs 401、聚合正確性（造數據驗算） | `backend/tests/test_admin.py`、`backend/tests/test_payments.py` |

## 環境需求

- Python **3.10 以上**（本次建置實測環境為 **3.13.11**）
- Node.js **20 以上**（本次建置實測環境為 **v24.11.1**，npm **11.6.2**）
- 一個現代瀏覽器

## 快速開始

### 測試帳號（比照課綱「含測試帳號」要求，顯著列在這裡）

| 角色 | Email | 密碼 |
|---|---|---|
| 管理員（後台） | `admin@brewgo.test` | `Admin12345` |
| 顧客（前台） | `customer@brewgo.test` | `Customer12345` |

兩個帳號都是 `backend/scripts/init_db.py` 的種子資料自動建立，顧客帳號底下
另外附了 7 筆示範訂單（固定日期 2026-07-14~20，狀態涵蓋整個訂單狀態機，
明確標示為示範資料），讓後台 Dashboard 一開始就有東西可以看。

以下每一步都附上本次撰寫教材時**實際執行**的輸出，指令假設你已經
`cd stage5-platform`。

### 後端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**初始化資料庫**（含 12 筆種子商品、2 個測試帳號、7 筆示範訂單）：

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

> 防呆設計：這支腳本重複執行不會刪掉既有資料，只會印出提示叫你要不要加
> `--reset`，理由跟做法見 `backend/scripts/init_db.py` 檔案開頭的註解。

**跑測試**：

```bash
pytest -q
```
實測結果：**92 個測試全部通過**（`test_auth.py` 9 個、`test_products.py` 10
個、`test_cart.py` 18 個、`test_orders.py` 17 個、`test_payments.py` 10 個、
`test_admin.py` 23 個、`test_config.py` 5 個——`test_config.py` 是 `SECRET_KEY`
預設值偵測 helper 的測試，`test_products.py`／`test_cart.py`／`test_orders.py`／
`test_admin.py` 各多了「超界 id／欄位回 422 不是 500」的代表性測試；
`test_cart.py`／`test_orders.py` 另外多了「商品下架後仍留在購物車、回應要標示
`is_active=false`、建單仍然被 409 擋下」這組測試，見「已下架商品體驗」修復）。
會看到幾條 `InsecureKeyLengthWarning`（測試用的 `SECRET_KEY` 故意設得比較短）
的警告，那是套件本身的提醒，不影響測試結果。

**啟動後端**：

```bash
uvicorn app.main:app --port 8005
```
預期看到 log 出現 `Application startup complete.`；另開一個終端機執行
`curl http://localhost:8005/api/health`，預期回應：
```json
{"status":"ok"}
```

### 前台（開發模式，另開一個終端機視窗）

```bash
cd frontend
npm install
npm run dev
```
瀏覽器打開 `http://localhost:5173/`，會看到 BrewGo 首頁；前端 `/api/...`
請求會透過 Vite proxy 轉給後端的 8005 埠（見 `frontend/vite.config.js`）。

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
dist/index.html                   0.66 kB │ gzip:  0.47 kB
dist/assets/index-C47FMfZj.css   11.83 kB │ gzip:  2.62 kB
dist/assets/index-DKEihZsI.js   267.96 kB │ gzip: 83.46 kB

✓ built in 392ms
```
build 檔名雜湊與大小會隨相依 patch 版本浮動、秒數會隨機器負載浮動，重點是
build 成功產出這三類檔案，以你實際看到的為準。

### 後台（開發模式，再另開一個終端機視窗）

```bash
cd admin
npm install
npm run dev
```
瀏覽器打開 `http://localhost:5175/admin/`（注意要有 `/admin/` 路徑），會看到
後台登入頁，用上方「測試帳號」表格的管理員帳號登入。

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
dist/index.html                   0.47 kB │ gzip:  0.32 kB
dist/assets/index-B_1NZC7Z.css    4.96 kB │ gzip:  1.44 kB
dist/assets/index-DFMuMT7d.js   251.78 kB │ gzip: 79.03 kB

✓ built in 358ms
```
build 檔名雜湊與大小會隨相依 patch 版本浮動、秒數會隨機器負載浮動，重點是
build 成功產出這三類檔案，以你實際看到的為準。

### 三合一正式模式（重啟後端後，前台跟後台會一起被 serve 出來）

前台跟後台都 build 完之後，重新啟動後端：
```bash
cd ../backend && uvicorn app.main:app --port 8005
```
實測驗證：
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8005/
# 200（前台）
curl -s -o /dev/null -w "%{http_code}" http://localhost:8005/admin/
# 200（後台）
```
完整驗證（含 SPA client-side 路由的 fallback）見 [`docs/DEPLOY.md`](docs/DEPLOY.md)。

## 逐步教學導覽

1. **訂單狀態機的單一真相來源**：`backend/app/order_state.py` 定義
   `PAYMENT_ALLOWED_FROM`／`ADMIN_STATUS_TRANSITIONS`／
   `CUSTOMER_CANCEL_ALLOWED_FROM` 三張表，`orders.py`／`payments.py`／
   `admin.py` 都呼叫這個模組的函式判斷「這個轉移合不合法」，不會有「改了
   一個地方的規則，另一個地方忘記跟著改」的問題。
2. **付款成功才扣庫存**：`backend/app/routers/payments.py` 的
   `mock_payment_route()` 在卡號驗證通過之後，才逐品項呼叫
   `decrease_stock()`，任一品項不夠就 `conn.rollback()`，訂單狀態與 payments
   表都不會被這次失敗的嘗試污染——原子性保證的做法沿用 stage4，只是把時機
   點從「建單」搬到「付款成功」，理由見 [`docs/DATABASE.md`](docs/DATABASE.md)。
3. **角色權限的依賴注入疊加**：`backend/app/deps.py` 的 `require_admin()`
   把 `get_current_user` 當自己的依賴（先確定有登入，再確定角色對），
   `backend/app/routers/admin.py` 的 `router = APIRouter(..., dependencies=
   [Depends(require_admin)])` 讓整個路由模組的所有端點自動套用這個檢查，
   不用每支函式各自宣告一次。
4. **後台聚合查詢**：`backend/app/db/database.py` 的 `admin_summary()` 用
   SQL 的 `SUM`／`COUNT` 直接算出總營收、訂單數、待出貨數、低庫存清單、
   會員數，前端 `admin/src/pages/Dashboard.jsx` 完全不做任何加總計算——
   能在資料庫層做的聚合就不要搬到前端重算一次。
5. **前後端各自獨立的 SPA fallback**：`backend/app/main.py` 掛了兩組
   catch-all 路由（後台那組必須先註冊，理由見 [`docs/DEPLOY.md`](docs/DEPLOY.md)
   的教學點），`admin/vite.config.js` 的 `base: '/admin/'` 讓 build 產物的
   資源網址自動對齊後端的掛載路徑。
6. **前端路由層級的登入保護**：`admin/src/App.jsx` 的 `ProtectedLayout` 沒有
   登入就直接 `<Navigate to="/login" />`，是前台完全沒有的寫法（前台只在
   個別 API 層擋，見 stage4 `CartContext.jsx`）——後台顯示的是全站營運資料，
   多一層「整頁擋」的縱深防禦，但真正擋住資料外洩的仍然是後端的
   `require_admin`（前端這層永遠只是體驗優化）。
7. **前台結帳兩步流程**：`frontend/src/pages/Checkout.jsx` 建單成功後
   `navigate('/pay/'+order.id)`，`frontend/src/pages/Pay.jsx`（全新頁面）
   對已存在的訂單嘗試付款，付款失敗會把最新的 `order`（狀態變成
   `'failed'`）存回 state，同一頁可以直接換卡號重試，不用重新走一次建單。

## 驗收清單

- [x] 後端測試 ≥45 個且全綠（實測 92 個，見上方「快速開始」）
- [x] 前台 vitest 沿用全綠（實測 33 個）；後台 build 成功＋至少 3 個元件測試
      （實測 9 個：`Login.test.jsx` 3 個、`Dashboard.test.jsx` 2 個、
      `Members.test.jsx` 1 個、`client.test.js` 3 個）
- [x] 購物車已下架商品體驗：商品被下架後仍留在購物車、`GET /api/cart` 標示
      `is_active:false`、購物車頁顯示「已下架」徽章並停用結帳按鈕、建單仍被
      409 擋下（實測見 [`API.md`](docs/API.md)「購物車 cart」「訂單 orders」
      兩節）
- [x] Mock 付款：成功／失敗／重試／已付 409／扣庫存時點皆已實測（見
      [`API.md`](docs/API.md)「付款 payments」一節）
- [x] 訂單狀態機：合法轉移（paid→shipped→completed）與非法轉移
      （pending→completed 409）皆已實測
- [x] 權限矩陣：customer 打 admin 端點 403、無 token 401、admin 正常 200
      皆已實測（見 [`SYSTEM_DESIGN.md`](docs/SYSTEM_DESIGN.md)）
- [x] 商品上下架：下架後前台列表／詳情皆看不到（實測 404），重新上架後恢復
- [x] Dashboard 聚合正確性：以造數據自動驗算（`test_admin_summary_
      aggregation_matches_hand_calculated_numbers`），不是憑感覺猜對
- [x] 前台＋後台各自 `npm run build` 成功；`/` 與 `/admin/` 皆回 200（實測）
- [x] 含系統架構圖、資料庫設計、API 文件、部署拓撲圖的技術文件齊全
- [ ] 部署到你選擇的平台（見 [`docs/DEPLOY.md`](docs/DEPLOY.md) 學員交付
      檢查表，由學員自行完成）

## 延伸挑戰

1. 目前「建單」完全不檢查庫存（見 `backend/tests/test_orders.py` 的
   `test_create_order_can_exceed_stock_because_it_does_not_reserve_it`），
   一直要到付款那一刻才會發現庫存不夠。試著設計一套「建單先鎖 30 分鐘、
   超時自動釋放」的機制（需要背景排程或在讀取時檢查時間戳），並想清楚：
   如果使用者在保留期限內完成付款，該怎麼把保留轉成正式扣庫存？
2. 目前 Dashboard 的「最近訂單」只抓最新 5 筆（`admin/src/pages/
   Dashboard.jsx`），沒有分頁。試著替 `GET /api/admin/orders` 加上
   `limit`／`offset` 查詢參數，前端做成可以翻頁的表格。
3. 目前商品下架是全站唯一的「軟刪除」示範，會員清單卻完全沒有對應的「停用
   帳號」功能（`backend/app/routers/admin.py` 的說明有提到這個取捨）。試著
   幫 `users` 表加一個 `is_disabled` 欄位，後台可以停用/恢復帳號，被停用的
   帳號登入時應該回什麼錯誤訊息？
4. 目前的付款失敗只有「卡號等於特定值」這一種模擬情境。試著擴充
   `backend/app/routers/payments.py`，讓「金額超過某個門檻」也模擬成需要
   人工審核（新增一個 `pending_review` 狀態），並想清楚這個新狀態要接進
   現有的 `order_state.py` 狀態機的哪個位置。

## 教學簡化聲明

- **付款是完全模擬的金流**：見本文件開頭的金流警示，`routers/payments.py`
  的判斷邏輯只有「卡號字串等不等於一個固定值」，沒有任何真實的信用卡驗證、
  簽章、webhook 回呼。要接上真實金流（例如 PayUNI、Stripe），需要換掉整支
  模組，並處理好本教材刻意省略的簽章驗證與非同步回呼確認。
- **取消已付款訂單不處理退款**：`paid` 狀態可以被 admin 取消（見
  `order_state.py` 的 `ADMIN_STATUS_TRANSITIONS`），但沒有真的退錢的動作——
  沒有金流串接就沒有真的收到錢，自然也沒有「退錢」這回事，真實產品接上金流
  後，取消已付款訂單必須同時呼叫金流的退款 API。
- **示範訂單不影響商品庫存**：`scripts/init_db.py` 的 7 筆示範訂單是直接寫進
  `orders`／`order_items`／`payments` 三張表的歷史示意資料，**不會**連動扣減
  `products.stock`——這是為了讓商品庫存永遠精準對照 master 型錄公告的原始值
  （master spec 規定商品型錄「不得增刪改」），完整說明見
  `scripts/init_db.py` 檔案開頭的誠實聲明。
- **建單不預留庫存**：見上方「延伸挑戰」第 1 題，這是本階段從 stage4
  「建單就扣庫存」演進而來、但還沒完全解決的已知限制，完整說明見
  [`docs/DATABASE.md`](docs/DATABASE.md)「訂單狀態與扣庫存時機」一節。
- **會員清單沒有停用/刪除功能**：唯讀清單，理由是隱私與資料完整性的取捨
  （見 `backend/app/routers/admin.py` 開頭的說明），完整功能留給延伸挑戰第
  3 題。
- **後台沒有分頁**：商品／訂單/會員清單目前都是一次全部撈出來，正式產品
  資料量大了之後需要加分頁，本教材的資料量（12 筆商品、個位數訂單）用不到，
  刻意沒有實作，留給延伸挑戰第 2 題。
- **`SECRET_KEY` 開發預設值是固定字串**：跟 stage4 一致，`.env.example`
  裡的 `dev-secret-change-me` 只適合本機開發，正式部署務必換成長隨機字串。
  這個值還是預設值時，後端啟動時會在終端機印出醒目警告（見
  `backend/app/config.py` 的 `warn_if_default_secret_key()`），本機開發可以
  忽略，部署前務必處理。

## 作者與聯絡資訊

本專案為呂紹民（Darren Lu）製作的教學範例，供學員學習全端服務開發使用。如果對本文件或專案有任何問題，或有課程教學、顧問諮詢、專案導入需求，歡迎與我聯絡。

- Email：kevin868686@gmail.com
- LinkedIn：https://www.linkedin.com/in/shaominglu
- Facebook：https://www.facebook.com/darrenlu86
