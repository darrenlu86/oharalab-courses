# MeowShop 喵喵商店 — 產品需求文件（PRD）

> 「毛孩的好日子，從喵喵商店開始」

---

## 1. 文件資訊與聯絡方式

| 項目 | 內容 |
|---|---|
| 文件版本 | v1.0 |
| 最後更新 | 2026-07-22 |
| 作者 | 呂紹民 Darren Lu |
| Email | kevin868686@gmail.com |
| LinkedIn | https://www.linkedin.com/in/shaominglu |
| Facebook | https://www.facebook.com/darrenlu86 |

如果對本文件或專案有任何問題，歡迎聯絡我。

> **這份文件是給誰看的？**
> MeowShop 是一個教學用的全端電商範例專案，這份 PRD 的目標讀者是「剛學完基礎程式語法、還沒做過完整專案」的學員。所以除了規格本身，文件裡會大量出現「為什麼這樣設計」的說明——工程上很多決定不是唯一解，理解背後的取捨，比背下規格本身更重要。

---

## 2. 專案概述與目標

### 2.1 這是什麼專案

MeowShop 喵喵商店是一個**虛構的**貓咪主題電商網站，販售貓糧、貓零食、貓玩具、貓砂、貓用品（窩/碗/抓板）五大類商品。整個專案的目的不是「做出一個真的能上線賣貨的商店」，而是透過打造一個功能完整、但範圍刻意收斂的電商系統，讓學員在動手實作的過程中理解一套典型全端服務長什麼樣子：前端怎麼呼叫 API、後端怎麼分層、資料庫怎麼設計、使用者從瀏覽商品到完成付款的一整條路徑是怎麼串起來的。

### 2.2 功能範圍

專案涵蓋以下核心流程，缺一不可，因為它們合起來才構成一個「完整」的電商體驗：

1. **會員系統**：註冊、登入、取得個人資料（JWT 驗證）
2. **商品瀏覽**：商品清單（可依分類、關鍵字篩選）、商品詳情
3. **購物車**：加入商品、修改數量、移除商品
4. **訂單**：從購物車建立訂單、查詢訂單列表與詳情
5. **付款**：模擬信用卡付款，含成功與失敗兩種結果

不包含的功能（刻意排除，見第 8 節「教學簡化聲明」）：管理後台、email 驗證信、真實金流串接、優惠券／折扣、商品評論、進階搜尋（如全文檢索）。這些都是真實電商會有、但會讓教學範例失焦的功能。

> **注意：本專案的付款功能是完全模擬的假金流，不會、也不可能發生任何真實金錢扣款。**
> `/api/payments/mock` 端點不會呼叫任何第三方金流服務（不是 PayUNI、不是 Stripe、不是任何銀行系統），所有的「信用卡卡號」都只是拿來走一段 if/else 邏輯的字串。系統用固定的測試卡號 `4000000000000002` 模擬「付款失敗」，其他任何 16 碼數字（建議示範用 `4242424242424242`）一律視為「付款成功」。這是業界常見的**測試卡號慣例**（例如 Stripe 的官方測試卡號也是類似設計），目的是讓學員不需要申請任何金流商帳號，就能完整體驗「付款成功」與「付款失敗」兩種分支的程式邏輯。

### 2.3 為什麼這樣設計：教學專案 vs 真實產品

真實電商系統要處理的東西非常多——金流商 webhook 簽章驗證、多倉庫庫存同步、促銷規則引擎、風控、A/B 測試……如果一開始就想著做「完整」的電商系統，學員會被淹沒在細節裡，抓不到核心的全端串接邏輯。MeowShop 選擇：**用真實的技術棧（FastAPI、JWT、bcrypt、真的資料庫），但用簡化過的業務規則**，讓學員練到的技術能力可以直接遷移到真實專案，同時又不會被邊角案例卡住進度。

---

## 3. 系統架構總覽

### 3.1 整體資料流

MeowShop 是典型的三層式架構，外加一個很關鍵的中間抽象層：

1. **前端**：純 HTML + CSS + 原生 JavaScript（沒有 React/Vue 這類框架，也沒有 build step）。使用者在瀏覽器上的每個操作（點擊「加入購物車」、送出結帳表單）都會透過 `fetch()` 呼叫後端 API。
2. **後端 Router 層**（FastAPI）：接收 HTTP 請求、用 Pydantic schema 驗證輸入格式、做權限檢查（是否登入），然後呼叫對應的 Repository 方法處理業務邏輯，最後把結果包成 JSON 回傳。
3. **Repository 抽象層**：這是本專案在架構上最重要的教學重點（見 3.2 節），所有跟資料庫有關的操作都要經過這一層，Router 完全不知道背後是 SQLite 還是 Supabase。
4. **實際資料庫**：依環境變數 `DB_BACKEND` 決定要接哪一種——本地開發預設用零設定的 SQLite，要接正式的雲端資料庫時切換成 Supabase（PostgreSQL）。

模擬金流模組（mock payment）是後端內部的一段邏輯，**不是外部服務**，所以整條付款流程可以完全離線測試，不需要網路連線、不需要任何金流商的 sandbox 帳號。

```mermaid
flowchart TD
    Browser["瀏覽器：靜態頁面 + 原生 JS<br/>fetch 呼叫 API"]

    subgraph BACKEND["後端服務：FastAPI（單一 Python 程序）"]
        Static["靜態檔掛載<br/>StaticFiles serve frontend/"]
        Router["Routers<br/>auth / products / cart / orders / payments"]
        Deps["deps.py<br/>get_current_user / get_repos"]
        Mock["Mock 金流模組<br/>依卡號規則判斷成功或失敗"]
        Repo["Repository 抽象介面<br/>base.py 定義的 ABC"]
    end

    subgraph IMPL["資料存取實作（擇一啟用）"]
        SQLiteImpl["SQLiteRepository"]
        SupabaseImpl["SupabaseRepository"]
    end

    SQLiteDB[("SQLite 檔案<br/>data/meowshop.db")]
    SupabaseDB[("Supabase / PostgreSQL")]

    Browser -- "GET 靜態頁面" --> Static
    Browser -- "fetch 呼叫 /api/*" --> Router
    Router --> Deps
    Router --> Repo
    Router -- "驗證卡號、判斷成功/失敗" --> Mock
    Mock -- "扣庫存、寫入付款紀錄" --> Repo
    Repo -. "DB_BACKEND=sqlite" .-> SQLiteImpl
    Repo -. "DB_BACKEND=supabase" .-> SupabaseImpl
    SQLiteImpl --> SQLiteDB
    SupabaseImpl --> SupabaseDB
```

**如何讀這張圖**：實線箭頭代表「一定會經過」的呼叫路徑；虛線箭頭代表「依設定二選一」的分岔——`DB_BACKEND` 這個環境變數決定了 Repository 抽象層實際會分派到 `SQLiteRepository` 還是 `SupabaseRepository`，但對 Router 層來說，這兩條路徑呼叫起來的程式碼長得一模一樣。

### 3.2 為什麼要做 Repository 抽象層（這節要講透）

這是整個專案架構設計上最值得學員花時間理解的一件事。如果不做這層抽象，最直覺的寫法會是在每個 router 裡直接寫 `sqlite3.connect(...)` 或直接呼叫 Supabase client——這樣寫得出來，但會遇到三個很實際的問題：

**問題一：換資料庫要改到業務邏輯**
如果 `routers/products.py` 裡直接寫 SQL 語句，將來想從本地 SQLite 換成正式環境的 Supabase，就得把每一個 router 檔案裡的資料庫呼叫全部重寫一遍——業務邏輯（例如「只回傳上架中的商品」）跟資料庫的存取方式（SQL 語法 vs Supabase client 語法）被綁在一起，改一邊就會動到另一邊。

> **為什麼這樣設計**：MeowShop 把「怎麼存取資料」和「用資料做什麼業務判斷」拆成兩層。`ProductRepository.list(category, search)` 這個方法名字描述的是「我要什麼資料」，至於背後是組一句 SQL 還是呼叫 Supabase 的 `.select()`，是 `SQLiteRepository` 或 `SupabaseRepository` 內部的事，router 完全不用關心。這樣一來，`DB_BACKEND` 這一個環境變數就能切換整個資料庫後端，routers 底下的程式碼一行都不用改。

**問題二：測試很難寫**
如果業務邏輯跟資料庫呼叫混在一起，要測試「購物車加入超過庫存的商品要回 409」這件事，就得真的架一個資料庫、塞測試資料、跑完再清掉，測試會變慢、變得不穩定（相依外部服務）。

> **為什麼這樣設計**：有了 Repository 抽象介面，測試時可以直接用一個乾淨的 SQLite 暫存檔案（`conftest.py` 就是做這件事），甚至未來可以寫一個完全在記憶體裡運作的假 Repository 拿來做單元測試，不需要動到真正的資料庫連線。測試跑得快，也跑得穩。

**問題三：抽象層就是團隊的契約**
`app/repositories/base.py` 定義的抽象類別（ABC）規定了每個 Repository 該有哙些方法、每個方法收什麼參數、回傳什麼格式。這份「介面」本身就是一份契約——不管背後換成哪一種資料庫實作，只要遵守這份契約（例如「找不到就回傳 `None`，不是丟例外」「一律回傳 plain dict，不是 ORM 物件」），呼叫端（routers）永遠可以用同一種方式使用它。

> **注意：這正是為什麼 SPEC 契約裡，Repository 的方法簽名要「固定」不能自己改。** 介面一旦變動，代表所有實作它的類別（`SQLiteRepository`、`SupabaseRepository`）跟所有呼叫它的 router 都要跟著改，這就是「介面即契約」的實際代價——契約穩定，才能讓兩邊各自獨立開發、獨立測試。

### 3.3 一次請求的完整資料流向（以「加入購物車」為例）

1. 使用者在 `product.html` 按下「加入購物車」按鈕
2. `js/pages/product.js` 呼叫 `api.js` 封裝好的 `fetch()`，帶上 `Authorization: Bearer <token>` 打 `POST /api/cart/items`
3. `routers/cart.py` 收到請求，先用 `deps.py` 的 `get_current_user` 解析 Bearer token，確認使用者身份
4. Router 呼叫 `products.get_by_id(product_id)` 確認商品存在、庫存足夠
5. Router 呼叫 `carts.upsert_item(user_id, product_id, quantity)` 寫入購物車
6. `SQLiteRepository`（或 `SupabaseRepository`）把這個操作轉成實際的 SQL/Supabase 呼叫，寫進資料庫
7. Router 再呼叫 `carts.get_items(user_id)` 把整台購物車的最新內容組回來
8. FastAPI 把結果序列化成 JSON，回傳給前端
9. `product.js` 收到回應，用 `ui.js` 的 toast 顯示「已加入購物車」，並更新 navbar 的購物車數量徽章

---

## 4. API 端點設計

### 4.1 共同慣例

- 所有 request/response body 一律是 JSON。
- 錯誤回應統一格式：`{"detail": "<訊息>"}`。
- 兩種錯誤訊息風格要分清楚：
  - **業務邏輯錯誤**（例如信箱重複、庫存不足）：`detail` 是一句完整的繁體中文訊息，狀態碼多半是 400/401/403/404/409。
  - **輸入格式錯誤**（例如密碼少於 8 碼、必填欄位缺漏）：由 Pydantic 自動驗證，`detail` 是 FastAPI 預設的**陣列**格式（不是單一字串），狀態碼固定是 422。範例見 4.2 節。
- 需要登入的端點，要在 header 帶 `Authorization: Bearer <JWT>`；缺少或 token 無效／過期，一律回 `401 {"detail": "請先登入"}`。

> **注意：422 跟其他 4xx 的 `detail` 格式不一樣。**
> 初學者很容易以為所有錯誤都是 `{"detail": "一句話"}`，但那只適用於「業務規則」錯誤（這是後端工程師自己用 `raise HTTPException(...)` 寫出來的）。422 是 FastAPI／Pydantic 在**進入 router 程式碼之前**就自動擋下來的格式驗證錯誤，它的 `detail` 是一個物件陣列，記錄了是哪個欄位、哪種驗證規則沒過。兩者觸發的時機不一樣：422 更早，代表請求連業務邏輯都還沒開始跑。

> **注意：本文件 JSON 範例裡的 `created_at`／`updated_at` 是 `DB_BACKEND=sqlite`（預設路徑）的實際輸出格式。**
> SQLite 沒有原生時間型別，`datetime('now')` 吐出來的是空白分隔、不含時區標記的 `"YYYY-MM-DD HH:MM:SS"` 字串（例如 `"2026-07-22 08:00:00"`），**不是**常見的 ISO 8601 `T`/`Z` 格式。如果 `DB_BACKEND=supabase`，PostgreSQL 的 `TIMESTAMPTZ` 型別會吐出真正帶時區的 ISO 8601 字串（例如 `"2026-07-22T08:00:00+00:00"`）——兩種後端這個欄位的字串格式並不一樣，前端不能對它的格式做死板假設。`frontend/js/pages/orders.js` 目前的因應方式是偵測字串裡有沒有 `T`，沒有就手動補上 `raw.replace(' ', 'T') + 'Z'` 再交給 `new Date(...)` 解析；如果你改用 Supabase 路徑，記得確認這段轉換邏輯對兩種格式都相容。

### 4.2 端點總覽

| # | Method | Path | 需登入 | 用途 |
|---|---|---|---|---|
| 1 | POST | `/api/auth/register` | 否 | 註冊新帳號 |
| 2 | POST | `/api/auth/login` | 否 | 登入，取得 JWT |
| 3 | GET | `/api/auth/me` | 是 | 取得目前登入者資料 |
| 4 | GET | `/api/products` | 否 | 商品清單（可依分類/關鍵字篩選） |
| 5 | GET | `/api/products/{id}` | 否 | 商品詳情 |
| 6 | GET | `/api/cart` | 是 | 取得目前購物車內容 |
| 7 | POST | `/api/cart/items` | 是 | 加入商品到購物車（已存在則累加） |
| 8 | PATCH | `/api/cart/items/{product_id}` | 是 | 直接覆蓋購物車中該商品的數量 |
| 9 | DELETE | `/api/cart/items/{product_id}` | 是 | 從購物車移除該商品 |
| 10 | POST | `/api/orders` | 是 | 從購物車建立訂單 |
| 11 | GET | `/api/orders` | 是 | 取得我的訂單列表 |
| 12 | GET | `/api/orders/{id}` | 是 | 取得單筆訂單詳情 |
| 13 | POST | `/api/payments/mock` | 是 | 模擬信用卡付款 |
| 14 | GET | `/api/health` | 否 | 健康檢查（含目前資料庫後端） |

以下逐一詳細說明。

---

### 4.3 `POST /api/auth/register`

註冊新帳號。不需登入。

**Request body**

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| email | string | 是 | 登入帳號，需符合 email 格式 |
| password | string | 是 | 至少 8 個字元，且**編碼成 UTF-8 位元組後不能超過 72 bytes**（bcrypt 演算法本身的長度上限，見下方注意） |
| name | string | 是 | 顯示名稱 |

**成功範例**

```http
POST /api/auth/register
Content-Type: application/json

{
  "email": "meow@example.com",
  "password": "cat123456",
  "name": "小橘"
}
```

```json
// 201 Created
{
  "id": 1,
  "email": "meow@example.com",
  "name": "小橘",
  "created_at": "2026-07-22 08:00:00"
}
```

**失敗範例（email 重複）**

```json
// 409 Conflict
{
  "detail": "這個 email 已經註冊過了"
}
```

**失敗範例（格式錯誤，422）**

```json
// 422 Unprocessable Entity
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "password"],
      "msg": "String should have at least 8 characters",
      "input": "abc123",
      "ctx": { "min_length": 8 }
    }
  ]
}
```

**所有可能狀態碼**

| 狀態碼 | 情境 |
|---|---|
| 201 | 註冊成功 |
| 409 | email 已被註冊 |
| 422 | password 少於 8 碼、password 編碼後超過 72 bytes、email 格式不對、缺必填欄位 |

> **為什麼這樣設計**：密碼在進資料庫前就要先經過 `bcrypt` 雜湊（見 5.6 節），資料庫裡永遠不會出現明文密碼。就算資料庫外洩，攻擊者拿到的也只是雜湊值，不是密碼本身。

> **注意：為什麼密碼有 72 bytes 的上限，而且要檢查「位元組數」而不是「字數」。** bcrypt 演算法本身有 72 bytes 的密碼長度上限，這是演算法規格的限制，不是本專案自己加的規則。`schemas.py` 的 `UserCreate` 會在密碼驗證時先 `.encode("utf-8")` 再檢查 bytes 長度，超過就回 422，`detail` 訊息是「密碼太長：最長 72 個位元組（bcrypt 演算法的限制）」。之所以要看 bytes 而不是 `len(字串)`，是因為英文字母 1 個字元＝1 byte，但中文字在 UTF-8 編碼下 1 個字通常是 3 bytes——如果只看字數，中文使用者可能在字數明明沒超過限制時就被拒絕（或反過來，字數沒超但 bytes 早就超了）。`security.py` 的 `hash_password()` 也重複做了一次同樣的檢查，當作「最後一道防線」（因為它是可以被 CLI 工具、批次腳本等直接呼叫的公用函式，不能假設呼叫端一定會先經過這裡的 schema 驗證）。

---

### 4.4 `POST /api/auth/login`

登入並取得 JWT。不需登入（這是取得登入憑證的端點）。

**Request body**

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| email | string | 是 | 註冊時的信箱 |
| password | string | 是 | 密碼明文（由 HTTPS 傳輸保護，不是由這裡加密） |

**成功範例**

```json
// 200 OK
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": { "id": 1, "email": "meow@example.com", "name": "小橘" }
}
```

**失敗範例**

```json
// 401 Unauthorized
{
  "detail": "email 或密碼錯誤"
}
```

**所有可能狀態碼**

| 狀態碼 | 情境 |
|---|---|
| 200 | 登入成功 |
| 401 | 帳號不存在，或密碼比對失敗 |
| 422 | 缺必填欄位、格式不對 |

> **為什麼這樣設計（安全教學重點）**：不管是「這個信箱沒註冊過」還是「信箱對但密碼錯」，一律回傳同一句「email 或密碼錯誤」，絕對不要分開講。如果分開講（例如「這個信箱不存在」），攻擊者就能拿一份 email 清單，用這支 API 一個一個試，篩出「哪些信箱確實有註冊」——這叫**帳號枚舉攻擊（account enumeration）**。回傳同一句模糊訊息，可以堵住這個資訊外洩管道。

---

### 4.5 `GET /api/auth/me`

取得目前登入者的個人資料。需登入。

**Request 參數**：無 query/body，只需要 `Authorization` header。

**成功範例**

```http
GET /api/auth/me
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

```json
// 200 OK
{
  "id": 1,
  "email": "meow@example.com",
  "name": "小橘",
  "created_at": "2026-07-22 08:00:00"
}
```

**失敗範例**

```json
// 401 Unauthorized
{
  "detail": "請先登入"
}
```

**所有可能狀態碼**

| 狀態碼 | 情境 |
|---|---|
| 200 | 成功取得個人資料 |
| 401 | 缺少 token、token 格式錯、token 過期（超過 24 小時） |

---

### 4.6 `GET /api/products`

商品清單。不需登入。

**Request 參數（query string）**

| 名稱 | 型別 | 必填 | 說明 |
|---|---|---|---|
| category | string | 否 | 篩選分類：`food` / `snack` / `toy` / `litter` / `supplies` |
| search | string | 否 | 對商品名稱做模糊比對 |

**成功範例**

```http
GET /api/products?category=toy
```

```json
// 200 OK
{
  "items": [
    {
      "id": 3,
      "name": "逗貓棒羽毛三件組",
      "description": "三種羽毛頭隨便換，貓咪不會玩膩，木棒好抓不易斷。",
      "price": 260,
      "stock": 18,
      "category": "toy",
      "image_url": "/images/products/p3.svg",
      "is_active": true
    },
    {
      "id": 4,
      "name": "貓草薄荷魚抱枕",
      "description": "貓草加薄荷雙重誘惑，抱著咬著都療癒，貓咪的療癒小夥伴。",
      "price": 390,
      "stock": 3,
      "category": "toy",
      "image_url": "/images/products/p4.svg",
      "is_active": true
    }
  ],
  "total": 2
}
```

**「失敗」情境說明**：這支端點沒有登入限制，`category`／`search` 也都是選填的字串參數，因此沒有 SPEC 定義的業務錯誤路徑。查詢不到符合條件的商品**不算失敗**，會回 200 加空陣列，例如：

```json
// 200 OK — 查無資料不是錯誤
{ "items": [], "total": 0 }
```

> **為什麼這樣設計**：這是 REST API 常見的慣例——「清單類」端點查不到符合條件的資料，回傳空陣列而不是 404，因為「條件成立但沒有結果」跟「這個資源根本不存在」是兩回事。404 應該保留給「你要找的那個特定資源不存在」（例如商品詳情），不是「篩選條件沒有命中」。

**所有可能狀態碼**

| 狀態碼 | 情境 |
|---|---|
| 200 | 一律回 200，包含查無資料的情況 |

---

### 4.7 `GET /api/products/{id}`

單一商品詳情。不需登入。

**Request 參數（path）**

| 名稱 | 型別 | 必填 | 說明 |
|---|---|---|---|
| id | integer | 是 | 商品 ID |

**成功範例**

```json
// 200 OK — GET /api/products/4
{
  "id": 4,
  "name": "貓草薄荷魚抱枕",
  "description": "貓草加薄荷雙重誘惑，抱著咬著都療癒，貓咪的療癒小夥伴。",
  "price": 390,
  "stock": 3,
  "category": "toy",
  "image_url": "/images/products/p4.svg",
  "is_active": true
}
```

**失敗範例**

```json
// 404 Not Found — GET /api/products/999
{
  "detail": "找不到這個商品"
}
```

**所有可能狀態碼**

| 狀態碼 | 情境 |
|---|---|
| 200 | 商品存在且上架中 |
| 404 | 商品 id 不存在，或商品 `is_active=false`（下架） |

> **注意**：下架商品也回 404，而不是回傳資料但標示「已下架」。這是因為對前台使用者來說，下架商品應該表現得跟「不存在」一樣，避免使用者拿到已下架商品的連結還能看到詳情、甚至嘗試加入購物車。

---

### 4.8 `GET /api/cart`

取得目前登入使用者的購物車內容。需登入。

**Request 參數**：無，只需要登入 token。

**成功範例**

```json
// 200 OK
{
  "items": [
    {
      "product_id": 4,
      "name": "貓草薄荷魚抱枕",
      "price": 390,
      "image_url": "/images/products/p4.svg",
      "quantity": 2,
      "stock": 3,
      "subtotal": 780
    }
  ],
  "total_amount": 780,
  "total_quantity": 2
}
```

**失敗範例**

```json
// 401 Unauthorized
{ "detail": "請先登入" }
```

**所有可能狀態碼**

| 狀態碼 | 情境 |
|---|---|
| 200 | 成功取得購物車（空車也是 200，`items` 為空陣列） |
| 401 | 未登入或 token 無效 |

> **為什麼這樣設計**：`subtotal`（小計）跟 `total_amount`（總計）都是後端算好才回傳，前端不用自己重算金額。這是很重要的原則——**跟金額有關的計算永遠讓後端做**，前端只負責顯示。如果前端自己算小計、總計，等於把「這筆訂單該收多少錢」的決定權交給使用者的瀏覽器，惡意使用者可以直接改瀏覽器裡的 JS 變數來竄改金額。

> **注意：購物車查詢會自動過濾掉已下架（`is_active=false`）的商品，下架商品會直接從購物車「消失」。** `CartRepository.get_items()` 內部的 SQL 是 `cart_items JOIN products`，且明確加了 `AND p.is_active = 1` 這個條件。這是刻意的設計：如果不過濾，商品下架後仍會出現在購物車裡，看起來像一件庫存正常、可以購買的商品；但真正建單時 `orders.py` 用的是有過濾 `is_active` 的 `products.get_by_id()`，會查不到商品、報出「庫存不足」，其實真正原因是「商品已下架」，訊息文不對題容易誤導使用者。加上這層過濾之後，下架商品會直接從購物車消失——這是教學簡化，真實電商系統通常會保留這筆 `cart_items`、額外標示「已下架，請移除」讓使用者自己處理，而不是默默讓它消失。

---

### 4.9 `POST /api/cart/items`

加入商品到購物車；如果購物車裡已經有這件商品，數量會**累加**。需登入。

**Request body**

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| product_id | integer | 是 | 商品 ID |
| quantity | integer | 是 | 要加入的數量，必須 ≥ 1 |

**成功範例**

```json
// POST /api/cart/items
{ "product_id": 4, "quantity": 1 }
```

```json
// 200 OK — 回傳整台購物車最新內容
{
  "items": [
    {
      "product_id": 4,
      "name": "貓草薄荷魚抱枕",
      "price": 390,
      "image_url": "/images/products/p4.svg",
      "quantity": 1,
      "stock": 3,
      "subtotal": 390
    }
  ],
  "total_amount": 390,
  "total_quantity": 1
}
```

**失敗範例（超過庫存）**

```json
// POST /api/cart/items — 商品只剩 3 件，卻要求加入 5 件
{ "product_id": 4, "quantity": 5 }
```

```json
// 409 Conflict
{ "detail": "庫存不足，目前只剩 3 件" }
```

**失敗範例（商品不存在）**

```json
// 404 Not Found
{ "detail": "找不到這個商品" }
```

**所有可能狀態碼**

| 狀態碼 | 情境 |
|---|---|
| 200 | 加入成功，回傳整台購物車 |
| 401 | 未登入 |
| 404 | `product_id` 不存在或已下架 |
| 409 | 要加入的數量（含累加後的總量）超過目前庫存 |
| 422 | `quantity` 小於 1，或欄位型別錯誤 |

> **為什麼這樣設計**：「累加」而不是「覆蓋」，是為了符合「加入購物車」這個動作的直覺語意——使用者在商品頁按第二次「加入購物車」，是想再多買一件，不是想把數量重設成 1。如果要「直接指定成某個數量」（例如在購物車頁面把數量從 2 改成 5），那是下一個端點 `PATCH /api/cart/items/{product_id}` 的責任。這兩個端點刻意分開，對應 REST 慣例裡 POST（新增/累加）跟 PATCH（部分覆蓋更新）語意上的差異。

---

### 4.10 `PATCH /api/cart/items/{product_id}`

直接把購物車中某商品的數量**覆蓋**成指定值（不是累加）。需登入。

**Request 參數**

| 名稱 | 位置 | 型別 | 必填 | 說明 |
|---|---|---|---|---|
| product_id | path | integer | 是 | 商品 ID |
| quantity | body | integer | 是 | 覆蓋後的數量，必須 ≥ 1 |

**成功範例**

```json
// PATCH /api/cart/items/4
{ "quantity": 2 }
```

```json
// 200 OK — 回傳整台購物車最新內容
{
  "items": [
    {
      "product_id": 4,
      "name": "貓草薄荷魚抱枕",
      "price": 390,
      "image_url": "/images/products/p4.svg",
      "quantity": 2,
      "stock": 3,
      "subtotal": 780
    }
  ],
  "total_amount": 780,
  "total_quantity": 2
}
```

**失敗範例（超過庫存）**

```json
// 409 Conflict
{ "detail": "庫存不足，目前只剩 3 件" }
```

**所有可能狀態碼**

| 狀態碼 | 情境 |
|---|---|
| 200 | 覆蓋成功，回傳整台購物車 |
| 401 | 未登入 |
| 404 | 該商品原本就不在購物車裡（`CartRepository.set_quantity` 回傳 `False` 時觸發） |
| 409 | 指定的數量超過目前庫存 |
| 422 | `quantity` 小於 1 |

> **注意：SPEC 沒有逐字規定 404 情境的錯誤訊息文字，本文件依照全站一致的命名慣例補上（實作採用的字串是 `"購物車裡沒有這個商品"`，見 `backend/app/routers/cart.py`），實作時可直接採用，但請注意這是「依慣例補齊」而非逐字抄自規格。**

---

### 4.11 `DELETE /api/cart/items/{product_id}`

從購物車移除指定商品。需登入。

**Request 參數**

| 名稱 | 位置 | 型別 | 必填 | 說明 |
|---|---|---|---|---|
| product_id | path | integer | 是 | 商品 ID |

**成功範例**

```json
// 200 OK — DELETE /api/cart/items/4，回傳移除後的整台購物車
{
  "items": [],
  "total_amount": 0,
  "total_quantity": 0
}
```

**失敗範例**

```json
// 404 Not Found — 該商品原本就不在購物車裡
{ "detail": "購物車裡沒有這個商品" }
```

**所有可能狀態碼**

| 狀態碼 | 情境 |
|---|---|
| 200 | 移除成功，回傳整台購物車 |
| 401 | 未登入 |
| 404 | 該商品原本就不在購物車裡 |

---

### 4.12 `POST /api/orders`

從目前的購物車內容建立一筆訂單。需登入。

**Request body**

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| recipient_name | string | 是 | 收件人姓名 |
| recipient_address | string | 是 | 收件地址 |

**成功範例**

```json
// POST /api/orders
{
  "recipient_name": "陳小明",
  "recipient_address": "台北市信義區松仁路 100 號"
}
```

```json
// 201 Created
{
  "id": 12,
  "total_amount": 1660,
  "status": "pending",
  "recipient_name": "陳小明",
  "recipient_address": "台北市信義區松仁路 100 號",
  "created_at": "2026-07-22 09:00:00",
  "updated_at": "2026-07-22 09:00:00",
  "items": [
    { "product_id": 4, "product_name": "貓草薄荷魚抱枕", "unit_price": 390, "quantity": 2 },
    { "product_id": 1, "product_name": "鮭魚無穀貓糧 1.5kg", "unit_price": 880, "quantity": 1 }
  ]
}
```

**失敗範例（購物車是空的）**

```json
// 400 Bad Request
{ "detail": "購物車是空的" }
```

**失敗範例（超過庫存）**

```json
// 409 Conflict — 沿用與購物車相同的錯誤訊息慣例
{ "detail": "庫存不足，目前只剩 3 件" }
```

**所有可能狀態碼**

| 狀態碼 | 情境 |
|---|---|
| 201 | 建單成功；購物車內容轉成訂單，購物車同步清空 |
| 400 | 購物車是空的，沒有東西可以下單 |
| 401 | 未登入 |
| 409 | 購物車裡有商品目前庫存不足以支應下單數量 |
| 422 | 缺 `recipient_name` / `recipient_address` |

> **為什麼這樣設計（重要 trade-off，詳見第 8 節）**：這一步**只建立訂單，不扣庫存**。要等到使用者真的完成付款（`POST /api/payments/mock` 成功）那一刻，庫存才會被扣。這代表兩個人同時看到「只剩 1 件」的商品，都有可能各自建單成功——這是刻意的簡化，且有明確的超賣風險，細節與真實系統的替代做法在第 8 節詳談。

---

### 4.13 `GET /api/orders`

取得目前登入使用者的訂單列表，依建立時間新到舊排序。需登入。

**Request 參數**：無。

**成功範例**

```json
// 200 OK
{
  "items": [
    {
      "id": 12,
      "total_amount": 1660,
      "status": "paid",
      "recipient_name": "陳小明",
      "recipient_address": "台北市中正區貓咪路 100 號 5 樓",
      "created_at": "2026-07-22 09:00:00",
      "updated_at": "2026-07-22 09:01:30"
    },
    {
      "id": 11,
      "total_amount": 390,
      "status": "failed",
      "recipient_name": "陳小明",
      "recipient_address": "台北市中正區貓咪路 100 號 5 樓",
      "created_at": "2026-07-21 15:00:00",
      "updated_at": "2026-07-21 15:02:10"
    }
  ]
}
```

**失敗範例**

```json
// 401 Unauthorized
{ "detail": "請先登入" }
```

**所有可能狀態碼**

| 狀態碼 | 情境 |
|---|---|
| 200 | 成功取得列表（沒有訂單也是 200，空陣列） |
| 401 | 未登入 |

---

### 4.14 `GET /api/orders/{id}`

取得單筆訂單詳情，含商品明細（`order_items`）與付款紀錄。需登入。

**Request 參數**

| 名稱 | 位置 | 型別 | 必填 | 說明 |
|---|---|---|---|---|
| id | path | integer | 是 | 訂單 ID |

**成功範例**

```json
// 200 OK — GET /api/orders/12
{
  "id": 12,
  "total_amount": 1660,
  "status": "paid",
  "recipient_name": "陳小明",
  "recipient_address": "台北市信義區松仁路 100 號",
  "created_at": "2026-07-22 09:00:00",
  "updated_at": "2026-07-22 09:05:00",
  "items": [
    { "product_id": 4, "product_name": "貓草薄荷魚抱枕", "unit_price": 390, "quantity": 2 },
    { "product_id": 1, "product_name": "鮭魚無穀貓糧 1.5kg", "unit_price": 880, "quantity": 1 }
  ],
  "payments": [
    {
      "id": 7,
      "amount": 1660,
      "method": "mock_card",
      "status": "success",
      "transaction_id": "MOCK-3f9a2b6e-...",
      "card_last4": "4242",
      "created_at": "2026-07-22 09:05:00"
    }
  ]
}
```

**失敗範例（不是自己的訂單，或訂單不存在）**

```json
// 404 Not Found
{ "detail": "找不到這筆訂單" }
```

**所有可能狀態碼**

| 狀態碼 | 情境 |
|---|---|
| 200 | 訂單存在且屬於目前使用者 |
| 401 | 未登入 |
| 404 | 訂單 id 不存在，或這筆訂單屬於別人 |

> **為什麼這樣設計（安全教學重點：不要用 403）**：如果訂單存在但屬於別人，這裡刻意回 **404**，而不是「403 Forbidden」。如果回 403，等於告訴攻擊者「這個 id 確實存在一筆訂單，只是你不能看」——攻擊者可以拿連續的 id（1, 2, 3, 4...）去試，光靠回應是 403 還是 404，就能推算出系統裡總共有多少筆訂單、id 是怎麼分配的。這種手法叫 **IDOR（Insecure Direct Object Reference，不安全的直接物件參照）**，防禦的原則很簡單：**不屬於你的資源，一律表現得像它不存在一樣**，一視同仁回 404。

---

### 4.15 `POST /api/payments/mock`

模擬信用卡付款。需登入。

**Request body**

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| order_id | integer | 是 | 要付款的訂單 ID |
| card_number | string | 是 | 16 碼數字，允許包含空格（例如 `4242 4242 4242 4242`） |
| card_holder | string | 是 | 持卡人姓名 |

**業務規則**

- 卡號 `4000000000000002` → **付款失敗**（模擬「餘額不足」）：`payments` 寫入一筆 `status=failed`，訂單 `status` 改成 `failed`。這筆訂單之後還可以再次呼叫本端點重試付款。
- 其他任何 16 碼數字（示範建議用 `4242424242424242`）→ **付款成功**：`payments` 寫入一筆 `status=success`，訂單 `status` 改成 `paid`，並**逐項扣減商品庫存**。
- 訂單不存在，或不是目前登入使用者的訂單 → 404。
- 訂單目前已經是 `paid` → 409，`detail` 為「這筆訂單已經付款完成」（不能對已完成付款的訂單重複付款）。
- 訂單目前已經是 `cancelled` → 409，`detail` 為「這筆訂單已經取消，無法再付款」——訊息文字刻意跟上面「已完成付款」的情境分開講，避免使用者誤以為自己其實已經付過款了。**注意**：目前 14 支 API 沒有任何端點會把訂單狀態改成 `cancelled`（見 5.5 節），這條分支是對應 schema 保留值的 forward-looking 防呆，只有直接操作資料庫把某筆訂單改成 `cancelled` 才會走到。
- 訂單狀態是 `pending` 或 `failed` → 都允許呼叫本端點（等於「首次付款」或「付款失敗後重試」）。
- 付款當下如果發現商品庫存已經不足（例如同時間被別的訂單搶先扣完）→ 409，`detail` 固定為「庫存不足，無法完成付款」（**注意**：這句話不像購物車／建單那兩支端點會帶出實際剩餘庫存數字，是一句固定文案，因為判斷這件事的當下已經在「逐項扣減」的迴圈裡，不會針對單一商品組出「還剩幾件」的訊息），並把這筆訂單標記為 `failed`。

**成功範例（付款成功）**

```json
// POST /api/payments/mock
{
  "order_id": 12,
  "card_number": "4242 4242 4242 4242",
  "card_holder": "陳小明"
}
```

```json
// 200 OK
{
  "payment": {
    "transaction_id": "MOCK-3f9a2b6e-1c2d-4e5f-8a9b-0c1d2e3f4a5b",
    "status": "success",
    "amount": 1660,
    "card_last4": "4242"
  },
  "order": { "id": 12, "status": "paid" }
}
```

**「業務失敗」範例（測試卡號，一樣是 200）**

```json
// POST /api/payments/mock
{
  "order_id": 13,
  "card_number": "4000 0000 0000 0002",
  "card_holder": "陳小明"
}
```

```json
// 200 OK — 這不是 HTTP 錯誤，而是「付款這件事本身失敗了」
{
  "payment": {
    "transaction_id": "MOCK-a1b2c3d4-...",
    "status": "failed",
    "amount": 390,
    "card_last4": "0002"
  },
  "order": { "id": 13, "status": "failed" }
}
```

**HTTP 層級失敗範例（訂單已付款過）**

```json
// 409 Conflict
{ "detail": "這筆訂單已經付款完成" }
```

**HTTP 層級失敗範例（訂單已取消）**

```json
// 409 Conflict — 訂單狀態是 cancelled；目前沒有端點可以把訂單改成這個狀態，
// 此為對應 schema 保留值的 forward-looking 防呆範例
{ "detail": "這筆訂單已經取消，無法再付款" }
```

**HTTP 層級失敗範例（付款當下庫存不足）**

```json
// 409 Conflict — 卡號規則判斷「應該成功」，但逐項扣庫存時發現庫存已被搶走，
// 訂單同時被標記為 failed；注意這句訊息不含實際剩餘庫存數字
{ "detail": "庫存不足，無法完成付款" }
```

**所有可能狀態碼**

| 狀態碼 | 情境 |
|---|---|
| 200 | 呼叫本身成功；`payment.status` 可能是 `success` 或 `failed`，兩者都是 200 |
| 401 | 未登入 |
| 404 | 訂單不存在，或不是這個使用者的訂單 |
| 409 | 訂單已經是 `paid`（`這筆訂單已經付款完成`）；訂單已經是 `cancelled`（`這筆訂單已經取消，無法再付款`）；或付款當下逐項扣庫存失敗（`庫存不足，無法完成付款`，訂單同時被標為 `failed`） |
| 422 | 缺必填欄位、`card_number` 不是 16 碼數字 |

> **為什麼這樣設計（本端點最重要的教學重點：HTTP 狀態碼 vs 業務結果）**：「這張卡餘額不足」跟「這支 API 本身出錯了」是完全不同層次的事。API 呼叫本身完成了它該做的事——去驗證一張卡、記錄結果、回報結果——所以回 200；至於這張卡到底刷不刷得過，是**回應內容裡 `payment.status` 欄位**要回答的問題，不是 HTTP 狀態碼要回答的問題。這跟真實金流商的行為是一致的：Stripe、PayUNI 的付款 API 在「這筆交易被拒絕」時，通常也不是回一個 4xx/5xx，而是 200 加上內容說明交易被拒絕的原因。**這也是為什麼工作區鐵律裡反覆強調「HTTP 200 ≠ 業務成功」**——不管是驗收這支 API，還是未來接真實金流，永遠要去看回應內容裡實際的交易狀態欄位，不能只看 HTTP 狀態碼。

> **為什麼扣庫存要放在付款成功的當下，而不是建單的時候**：見第 8 節「建單不扣庫存」的詳細討論。這裡要補充的是扣庫存**怎麼做**才安全——`ProductRepository.decrease_stock(product_id, quantity)` 用的是一句「條件式 UPDATE」：`UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?`，然後檢查這句 UPDATE 到底影響了幾列。如果庫存不夠，`WHERE` 條件不成立，UPDATE 影響 0 列，代表扣款失敗；如果庫存夠，UPDATE 影響 1 列，代表扣款成功。這個寫法讓「檢查庫存夠不夠」跟「真的扣庫存」變成同一個原子操作（atomic），不會出現「兩個請求都先檢查完發現庫存夠，然後都各自扣一次，結果扣成負數」這種競爭條件（race condition）。

---

### 4.16 `GET /api/health`

健康檢查端點，回報服務狀態與目前使用的資料庫後端。不需登入。

**Request 參數**：無。

**成功範例**

```json
// 200 OK
{ "status": "ok", "db_backend": "sqlite" }
```

**「失敗」情境說明**：這是一支不需要登入、不需要任何輸入參數的端點，正常情況下永遠回 200。它存在的目的是給部署平台（例如 Cloud Run）或監控系統定期呼叫，確認服務還活著、還能正常回應。

**所有可能狀態碼**

| 狀態碼 | 情境 |
|---|---|
| 200 | 服務運作正常 |

> **為什麼這樣設計**：回應裡帶上 `db_backend`，是為了讓開發者或維運人員一眼就能確認「這台服務現在到底接的是本地 SQLite 還是正式的 Supabase」，不用另外登入伺服器看環境變數——這在排查「明明改了資料卻沒生效」這類問題時特別有用（很可能是接錯資料庫後端）。

---

## 5. 資料庫設計

### 5.1 六張表總覽

| 資料表 | 用途 |
|---|---|
| `users` | 會員帳號 |
| `products` | 商品主檔 |
| `cart_items` | 購物車內容（每人每商品一列） |
| `orders` | 訂單主檔 |
| `order_items` | 訂單明細（商品快照） |
| `payments` | 付款紀錄 |

### 5.2 `users`

| 欄位 | SQLite 型別 | PostgreSQL 型別 | 可空 | 鍵 | 預設值 | 說明 |
|---|---|---|---|---|---|---|
| id | `INTEGER PRIMARY KEY AUTOINCREMENT` | `BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY` | 否 | PK | 自動遞增 | 使用者流水號 |
| email | `TEXT NOT NULL UNIQUE` | `TEXT NOT NULL UNIQUE` | 否 | UNIQUE | 無 | 登入帳號 |
| password_hash | `TEXT NOT NULL` | `TEXT NOT NULL` | 否 | - | 無 | bcrypt 雜湊後的密碼，絕不存明文 |
| name | `TEXT NOT NULL` | `TEXT NOT NULL` | 否 | - | 無 | 顯示名稱 |
| created_at | `TEXT NOT NULL DEFAULT (datetime('now'))` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | 否 | - | 建立當下時間 | 註冊時間 |

### 5.3 `products`

| 欄位 | SQLite 型別 | PostgreSQL 型別 | 可空 | 鍵 | 預設值 | 說明 |
|---|---|---|---|---|---|---|
| id | `INTEGER PRIMARY KEY AUTOINCREMENT` | `BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY` | 否 | PK | 自動遞增 | 商品流水號 |
| name | `TEXT NOT NULL` | `TEXT NOT NULL` | 否 | - | 無 | 商品名稱 |
| description | `TEXT NOT NULL` | `TEXT NOT NULL` | 否 | - | 無 | 商品描述 |
| price | `INTEGER NOT NULL` | `INTEGER NOT NULL` | 否 | - | 無 | 售價，新台幣整數元 |
| stock | `INTEGER NOT NULL DEFAULT 0` | `INTEGER NOT NULL DEFAULT 0` | 否 | - | 0 | 庫存數量 |
| category | `TEXT NOT NULL` | `TEXT NOT NULL` | 否 | - | 無 | 值域：`food`/`snack`/`toy`/`litter`/`supplies` |
| image_url | `TEXT NOT NULL` | `TEXT NOT NULL` | 否 | - | 無 | 商品圖片路徑，例如 `/images/products/p1.svg` |
| is_active | `INTEGER NOT NULL DEFAULT 1` | `BOOLEAN NOT NULL DEFAULT true` | 否 | - | 上架 | 是否上架中 |
| created_at | `TEXT NOT NULL DEFAULT (datetime('now'))` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | 否 | - | 建立當下時間 | 建立時間 |

> **為什麼這樣設計：金額用 `INTEGER`，不用 `FLOAT`/`REAL`。**
> 這是新手很容易踩的坑。浮點數（float）在電腦裡是用二進位近似表示小數的，`0.1 + 0.2` 在絕大多數程式語言裡都不會精準等於 `0.3`，而是類似 `0.30000000000000004`。金額計算最怕的就是這種誤差——幾筆訂單加總下來，總金額可能就跟預期差了幾分錢，而且很難重現、很難除錯。既然本專案的商品定價都是新台幣整數元（沒有角、分），乾脆整個系統的金額欄位（`price`、`total_amount`、`unit_price`、`amount`）全部用整數存，加減乘除都是整數運算，完全不會有誤差問題。真實世界如果要支援到「分」，常見做法是「最小貨幣單位整數化」（例如美元系統常把金額都以「分」為單位存整數），原則相同：**金額永遠不要用浮點數存。**

### 5.4 `cart_items`

| 欄位 | SQLite 型別 | PostgreSQL 型別 | 可空 | 鍵 | 預設值 | 說明 |
|---|---|---|---|---|---|---|
| id | `INTEGER PRIMARY KEY AUTOINCREMENT` | `BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY` | 否 | PK | 自動遞增 | 流水號 |
| user_id | `INTEGER NOT NULL` | `BIGINT NOT NULL` | 否 | FK → `users.id` | 無 | 這台購物車屬於哪個使用者 |
| product_id | `INTEGER NOT NULL` | `BIGINT NOT NULL` | 否 | FK → `products.id` | 無 | 商品 |
| quantity | `INTEGER NOT NULL CHECK(quantity > 0)` | `INTEGER NOT NULL CHECK(quantity > 0)` | 否 | - | 無 | 數量，必須大於 0 |
| created_at | `TEXT NOT NULL DEFAULT (datetime('now'))` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | 否 | - | 建立當下時間 | 加入時間 |

額外限制：`UNIQUE(user_id, product_id)`——同一個使用者對同一件商品，購物車裡只會有一列（用累加數量的方式表示買多件，而不是插入多列重複資料）。

**索引**：`user_id`（原因見 5.7 節）。

### 5.5 `orders`

| 欄位 | SQLite 型別 | PostgreSQL 型別 | 可空 | 鍵 | 預設值 | 說明 |
|---|---|---|---|---|---|---|
| id | `INTEGER PRIMARY KEY AUTOINCREMENT` | `BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY` | 否 | PK | 自動遞增 | 訂單編號 |
| user_id | `INTEGER NOT NULL` | `BIGINT NOT NULL` | 否 | FK → `users.id` | 無 | 下單者 |
| total_amount | `INTEGER NOT NULL` | `INTEGER NOT NULL` | 否 | - | 無 | 訂單總金額 |
| status | `TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','paid','failed','cancelled'))` | 同左 | 否 | - | `pending` | 訂單狀態 |
| recipient_name | `TEXT NOT NULL` | `TEXT NOT NULL` | 否 | - | 無 | 收件人姓名 |
| recipient_address | `TEXT NOT NULL` | `TEXT NOT NULL` | 否 | - | 無 | 收件地址 |
| created_at | `TEXT NOT NULL DEFAULT (datetime('now'))` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | 否 | - | 建立當下時間 | 建單時間 |
| updated_at | `TEXT NOT NULL DEFAULT (datetime('now'))` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | 否 | - | 建立當下時間 | 狀態最後更新時間 |

**索引**：`user_id`（原因見 5.7 節）。

> **注意：`status` 的值域包含 `cancelled`，但目前 14 支 API 裡沒有任何一支能把訂單改成 `cancelled`。** 這是刻意保留的欄位值——schema 先把「取消訂單」這個未來可能會加的狀態放進 `CHECK` 約束裡，但這個版本沒有實作對應的端點。學員如果想練習擴充功能，「加一支取消訂單的 API」會是一個很適合的練習題，因為資料庫端完全不用改。

### 5.6 `order_items`

| 欄位 | SQLite 型別 | PostgreSQL 型別 | 可空 | 鍵 | 預設值 | 說明 |
|---|---|---|---|---|---|---|
| id | `INTEGER PRIMARY KEY AUTOINCREMENT` | `BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY` | 否 | PK | 自動遞增 | 流水號 |
| order_id | `INTEGER NOT NULL` | `BIGINT NOT NULL` | 否 | FK → `orders.id` | 無 | 屬於哪筆訂單 |
| product_id | `INTEGER NOT NULL` | `BIGINT NOT NULL` | 否 | FK → `products.id` | 無 | 商品（用來回頭查商品現況，例如現在的圖片） |
| product_name | `TEXT NOT NULL` | `TEXT NOT NULL` | 否 | - | 無 | **下單當下**的商品名稱快照 |
| unit_price | `INTEGER NOT NULL` | `INTEGER NOT NULL` | 否 | - | 無 | **下單當下**的單價快照 |
| quantity | `INTEGER NOT NULL` | `INTEGER NOT NULL` | 否 | - | 無 | 購買數量 |

**索引**：`order_id`（原因見 5.7 節）。

> **為什麼這樣設計：為什麼要把商品名稱、單價「複製」一份存進 order_items，明明 products 表就有？**
> 這是初學者最容易忽略、但實務上非常重要的設計。假設商品「鮭魚無穀貓糧」現在賣 880 元，使用者用這個價格下單了；三天後，店家調漲售價到 980 元。這時候如果 `order_items` 沒有存自己的 `unit_price`、而是每次都去 `JOIN products` 抓「現在」的價格，這筆舊訂單的金額會憑空從 880 元變成 980 元——**歷史訂單的金額，絕對不能因為商品之後改價而跟著變動**。同樣的道理也適用在商品名稱：如果店家把商品改名，舊訂單上應該還是顯示當初下單時的名字，而不是現在的新名字。這種「在某個時間點把當下的資料複製一份存下來，之後不再跟著來源資料變動」的做法，叫做**快照（snapshot）**，是電商、記帳、開票系統裡非常常見的模式。

### 5.7 `payments`

| 欄位 | SQLite 型別 | PostgreSQL 型別 | 可空 | 鍵 | 預設值 | 說明 |
|---|---|---|---|---|---|---|
| id | `INTEGER PRIMARY KEY AUTOINCREMENT` | `BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY` | 否 | PK | 自動遞增 | 流水號 |
| order_id | `INTEGER NOT NULL` | `BIGINT NOT NULL` | 否 | FK → `orders.id` | 無 | 對應哪筆訂單 |
| amount | `INTEGER NOT NULL` | `INTEGER NOT NULL` | 否 | - | 無 | 這次付款嘗試的金額 |
| method | `TEXT NOT NULL DEFAULT 'mock_card'` | `TEXT NOT NULL DEFAULT 'mock_card'` | 否 | - | `mock_card` | 付款方式（本專案固定值） |
| status | `TEXT NOT NULL CHECK(status IN ('success','failed'))` | 同左 | 否 | - | 無 | 這次付款嘗試的結果 |
| transaction_id | `TEXT NOT NULL UNIQUE` | `TEXT NOT NULL UNIQUE` | 否 | UNIQUE | 無 | 格式 `MOCK-<uuid4>` |
| card_last4 | `TEXT NOT NULL` | `TEXT NOT NULL` | 否 | - | 無 | 卡號末 4 碼（不存完整卡號） |
| created_at | `TEXT NOT NULL DEFAULT (datetime('now'))` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | 否 | - | 建立當下時間 | 這次付款嘗試發生的時間 |

**索引**：`order_id`（原因見下）。

> **注意：一筆訂單可以對應多筆 `payments` 紀錄。** 因為「付款失敗可以重試」，一筆訂單如果先刷卡失敗一次、再重刷成功，`payments` 表裡就會有兩列——一列 `status=failed`，一列 `status=success`。這也是為什麼 `payments` 不是 `orders` 的 1 對 1 附屬欄位，而要獨立成一張表：每一次付款嘗試都是一筆值得保留的紀錄，不能被下一次嘗試覆蓋掉。

> **只存卡號末 4 碼，不存完整卡號**：即使這是假的信用卡號，這裡也刻意示範真實系統該有的資安習慣——完整卡號屬於高度敏感資料（PCI-DSS 規範明確要求），系統不應該持久化儲存，通常最多只保留末 4 碼用於使用者辨識自己刷了哪張卡。

### 5.8 資料表關聯與教學理由小結

- `users` 1 對多 `cart_items`、1 對多 `orders`：一個人可以有很多購物車項目、很多筆訂單。
- `products` 1 對多 `cart_items`、1 對多 `order_items`：一個商品可以被很多人放進購物車、出現在很多筆訂單明細裡。
- `orders` 1 對多（至少 1 筆）`order_items`：一筆訂單至少包含一項商品明細（因為空購物車不能建單）。
- `orders` 1 對多（含 0 筆）`payments`：訂單建立時還沒有付款紀錄，之後每嘗試付款一次就多一列。

### 5.9 需要索引的欄位與原因

| 資料表 | 索引欄位 | 原因 |
|---|---|---|
| `cart_items` | `user_id` | 「取得我的購物車」（`GET /api/cart`）是高頻查詢，用 `user_id` 過濾整張表 |
| `cart_items` | `UNIQUE(user_id, product_id)` | 同時是唯一性約束也是索引，用來快速判斷「這個人的購物車裡有沒有這件商品」，支援 4.9 節的累加邏輯 |
| `orders` | `user_id` | 「取得我的訂單列表」（`GET /api/orders`）是高頻查詢 |
| `order_items` | `order_id` | 每次讀訂單詳情都要撈出該訂單的所有明細 |
| `payments` | `order_id` | 每次讀訂單詳情都要撈出該訂單的所有付款紀錄 |
| `payments` | `transaction_id`（UNIQUE） | 保證交易編號全域唯一，同時加速用交易編號查詢的情境 |

> **為什麼這樣設計**：索引的取捨原則很單純——挑「最常被拿來當 `WHERE` 條件」的欄位建索引。上面每一個索引都對應到某支 API 實際查詢時會用到的過濾條件；沒有列進來的欄位（例如 `products.category`）目前資料量小（10 筆種子資料），教學階段不需要為了效能特別建索引，但如果商品數量成長到幾萬筆，`category` 就會是下一個該加索引的欄位。

### 5.10 同一套 schema，兩種資料庫怎麼對應

MeowShop 刻意讓 `sqlite_schema.sql` 跟 `supabase_schema.sql` 的**欄位名稱完全一致**，只有型別和少數語法不同，這樣 `SQLiteRepository` 跟 `SupabaseRepository` 才能用同一套 Repository 介面操作、回傳一致的 dict 結構。

| 差異點 | SQLite | PostgreSQL / Supabase | 說明 |
|---|---|---|---|
| 自增主鍵 | `INTEGER PRIMARY KEY AUTOINCREMENT` | `BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY` | SQLite 用 `AUTOINCREMENT` 關鍵字；PostgreSQL 現代寫法用 `GENERATED ALWAYS AS IDENTITY`（比舊式的 `SERIAL` 更標準） |
| 布林值 | `INTEGER`（0/1），例如 `is_active` | `BOOLEAN`（true/false） | SQLite 沒有原生布林型別，慣例上用整數 0/1 代替；Supabase／PostgreSQL 有原生 `BOOLEAN` |
| 時間戳記 | `TEXT`，用 `datetime('now')` 存純文字時間 | `TIMESTAMPTZ`，用 `now()` | SQLite 沒有原生日期時間型別，`datetime('now')` 吐出的是不含時區的 `YYYY-MM-DD HH:MM:SS` 純文字（**不是** ISO 8601 格式，見 4.1 節注意）；PostgreSQL 有帶時區的原生時間型別，`now()` 才會真的輸出 ISO 8601 格式並支援時間運算與時區轉換 |
| 外鍵約束是否預設生效 | **預設關閉**，需要每個連線手動開啟 | 預設生效 | 見下方「注意」 |

> **注意：SQLite 的外鍵約束預設是關閉的！**
> 這是初學者最容易忽略、但一定要知道的 SQLite 特性：就算你在 `sqlite_schema.sql` 裡寫了 `FOREIGN KEY (user_id) REFERENCES users(id)`，SQLite **預設並不會真的去檢查**這個約束——你甚至可以插入一筆 `user_id` 指向不存在使用者的 `cart_items`，SQLite 完全不會擋。要讓外鍵約束真的生效，**每一個資料庫連線**都要先執行一次：
> ```sql
> PRAGMA foreign_keys = ON;
> ```
> 這不是「設定一次全域生效」，而是每個連線（每個 `sqlite3.connect(...)`）都要各自下這道指令。`SQLiteRepository` 在建立連線的地方要記得補上這一步，否則外鍵約束形同虛設。PostgreSQL／Supabase 則沒有這個問題，外鍵約束預設就是強制生效的。

---

## 6. ER 圖

下圖完整畫出 6 張表的欄位與關聯。屬性型別用簡化名稱標示（`int`/`text`/`bool`），實際的 SQLite/PostgreSQL 型別對照請看第 5 節的欄位表。

```mermaid
erDiagram
    USERS ||--o{ CART_ITEMS : "擁有"
    USERS ||--o{ ORDERS : "下單"
    PRODUCTS ||--o{ CART_ITEMS : "被加入購物車"
    PRODUCTS ||--o{ ORDER_ITEMS : "出現在訂單明細"
    ORDERS ||--|{ ORDER_ITEMS : "包含"
    ORDERS ||--o{ PAYMENTS : "對應付款嘗試"

    USERS {
        int id PK
        text email
        text password_hash
        text name
        text created_at
    }

    PRODUCTS {
        int id PK
        text name
        text description
        int price
        int stock
        text category
        text image_url
        bool is_active
        text created_at
    }

    CART_ITEMS {
        int id PK
        int user_id FK
        int product_id FK
        int quantity
        text created_at
    }

    ORDERS {
        int id PK
        int user_id FK
        int total_amount
        text status
        text recipient_name
        text recipient_address
        text created_at
        text updated_at
    }

    ORDER_ITEMS {
        int id PK
        int order_id FK
        int product_id FK
        text product_name
        int unit_price
        int quantity
    }

    PAYMENTS {
        int id PK
        int order_id FK
        int amount
        text method
        text status
        text transaction_id
        text card_last4
        text created_at
    }
```

**如何讀這張圖**：`||--o{` 代表「一對多（多的那邊可以是 0 筆）」，例如一個使用者可以有 0 筆或多筆購物車項目；`||--|{` 代表「一對多（多的那邊至少 1 筆）」，只用在 `ORDERS` 到 `ORDER_ITEMS`，因為業務規則規定空購物車不能建單，所以一筆訂單成立的當下就至少會有 1 筆明細。

---

## 7. 循序圖

以下三張循序圖統一使用五個角色（participant），對應第 3 節架構圖裡的分層：**前端頁面**、**FastAPI Router**、**Repository 層**、**資料庫**、**Mock 金流模組**。就算某張圖裡某個角色沒有互動（例如註冊登入流程用不到金流模組），也會把五個角色都列出來，方便跟另外兩張圖對照著看同一套分層架構。

### 7.1 註冊與登入

這張圖示範 bcrypt 密碼雜湊跟 JWT 簽發分別發生在哪一步。

```mermaid
sequenceDiagram
    participant FE as 前端頁面
    participant API as FastAPI Router
    participant REPO as Repository 層
    participant DB as 資料庫
    participant PAY as Mock 金流模組

    Note over FE,DB: 註冊流程
    FE->>API: POST /api/auth/register 帶 email/password/name
    API->>API: 用 bcrypt 把 password 雜湊成 password_hash
    API->>REPO: users.create(email, password_hash, name)
    REPO->>DB: INSERT INTO users ...

    alt email 已存在
        DB-->>REPO: UNIQUE 約束違反
        REPO-->>API: raise DuplicateEmailError
        API-->>FE: 409，detail 這個 email 已經註冊過了
    else 建立成功
        DB-->>REPO: 新使用者列
        REPO-->>API: 回傳 dict id/email/name/created_at
        API-->>FE: 201，回傳使用者資料
    end

    Note over FE,DB: 登入流程
    FE->>API: POST /api/auth/login 帶 email/password
    API->>REPO: users.get_by_email(email)
    REPO->>DB: SELECT * FROM users WHERE email = ?
    DB-->>REPO: 使用者列或查無資料
    REPO-->>API: dict 或 None

    alt 帳號不存在，或密碼比對失敗
        API-->>FE: 401，detail email 或密碼錯誤
    else 驗證通過
        API->>API: bcrypt 驗證密碼、PyJWT 簽發 24 小時效期 token
        API-->>FE: 200，回傳 access_token 與 user
    end
```

### 7.2 瀏覽商品到加入購物車（含未登入分支）

這張圖示範「瀏覽商品」完全不需要登入，但「加入購物車」需要，未帶 token 或 token 失效時會在進到業務邏輯前就被擋下來。

```mermaid
sequenceDiagram
    participant FE as 前端頁面
    participant API as FastAPI Router
    participant REPO as Repository 層
    participant DB as 資料庫
    participant PAY as Mock 金流模組

    Note over FE,DB: 瀏覽商品，不需要登入
    FE->>API: GET /api/products?category=toy
    API->>REPO: products.list(category, search)
    REPO->>DB: SELECT * FROM products WHERE is_active=1 AND ...
    DB-->>REPO: 商品列表
    REPO-->>API: list[dict]
    API-->>FE: 200，回傳 items 與 total

    Note over FE,DB: 加入購物車，需要登入
    FE->>API: POST /api/cart/items 帶 product_id/quantity，含 Authorization header

    alt 缺少或無效的 token
        API-->>FE: 401，detail 請先登入
    else token 驗證通過
        API->>REPO: products.get_by_id(product_id)
        REPO->>DB: SELECT * FROM products WHERE id=? AND is_active=1
        DB-->>REPO: 商品資料或查無資料

        alt 商品不存在或已下架
            REPO-->>API: None
            API-->>FE: 404，detail 找不到這個商品
        else 商品存在但庫存不足
            REPO-->>API: dict，stock 小於要求數量
            API-->>FE: 409，detail 庫存不足目前只剩 N 件
        else 庫存足夠
            API->>REPO: carts.upsert_item(user_id, product_id, quantity)
            REPO->>DB: 寫入或累加 cart_items
            DB-->>REPO: 寫入成功
            API->>REPO: carts.get_items(user_id)
            REPO->>DB: SELECT cart_items JOIN products
            DB-->>REPO: 購物車最新內容
            REPO-->>API: list[dict]
            API-->>FE: 200，回傳整台購物車
        end
    end
```

### 7.3 結帳：建單到模擬付款（成功與失敗兩分支）

這張圖是全站最完整的一條流程，涵蓋「建單不扣庫存、付款才扣庫存」的關鍵設計，以及付款成功／失敗兩條分支各自怎麼更新訂單狀態與庫存。

```mermaid
sequenceDiagram
    participant FE as 前端頁面
    participant API as FastAPI Router
    participant REPO as Repository 層
    participant DB as 資料庫
    participant PAY as Mock 金流模組

    Note over FE,DB: 第一步，從購物車建立訂單，尚未扣庫存
    FE->>API: POST /api/orders 帶 recipient_name/recipient_address
    API->>REPO: carts.get_items(user_id)
    REPO->>DB: SELECT 購物車內容 JOIN products
    DB-->>REPO: 購物車商品列表
    REPO-->>API: list[dict]

    alt 購物車是空的
        API-->>FE: 400，detail 購物車是空的
    else 有商品但某項超過庫存
        API-->>FE: 409，detail 庫存不足目前只剩 N 件
    else 建單成功
        API->>REPO: orders.create(user_id, total_amount, recipient_name, recipient_address, items)
        REPO->>DB: INSERT orders 與 order_items，快照商品名與單價
        DB-->>REPO: 新訂單資料
        API->>REPO: carts.clear(user_id)
        REPO->>DB: DELETE FROM cart_items WHERE user_id=?
        API-->>FE: 201，訂單詳情，status 為 pending
    end

    Note over FE,PAY: 第二步，呼叫模擬付款
    FE->>API: POST /api/payments/mock 帶 order_id/card_number/card_holder
    API->>REPO: orders.get_by_id(order_id, user_id)
    REPO->>DB: SELECT 訂單資料
    DB-->>REPO: 訂單資料或查無資料
    REPO-->>API: dict 或 None

    alt 訂單不存在或不是本人的訂單
        API-->>FE: 404，detail 找不到這筆訂單
    else 訂單已經是 paid
        API-->>FE: 409，detail 這筆訂單已經付款完成
    else 訂單已經是 cancelled（forward-looking 防呆，目前沒有端點會產生這個狀態）
        API-->>FE: 409，detail 這筆訂單已經取消，無法再付款
    else 訂單為 pending 或 failed，允許付款
        API->>PAY: 依卡號規則判斷這次付款結果
        PAY-->>API: 回傳模擬結果，成功或失敗

        alt 卡號為 4000000000000002，模擬餘額不足
            API->>REPO: orders.add_payment(order_id, amount, failed, transaction_id, card_last4)
            REPO->>DB: INSERT INTO payments，status 為 failed
            API->>REPO: orders.update_status(order_id, failed)
            REPO->>DB: UPDATE orders SET status 為 failed
            API-->>FE: 200，payment.status 為 failed，order.status 為 failed
        else 其他 16 碼卡號，例如 4242424242424242
            API->>REPO: products.decrease_stock(product_id, quantity) 逐項執行
            REPO->>DB: 條件式 UPDATE，扣庫存前先確認 stock 足夠

            alt 條件式 UPDATE 影響 0 筆，代表庫存不足
                DB-->>REPO: 扣庫存失敗
                REPO-->>API: False
                API->>REPO: orders.update_status(order_id, failed)
                API-->>FE: 409，detail 庫存不足，無法完成付款，訂單標為 failed
            else 扣庫存成功
                DB-->>REPO: 扣庫存成功
                REPO-->>API: True
                API->>REPO: orders.add_payment(order_id, amount, success, transaction_id, card_last4)
                REPO->>DB: INSERT INTO payments，status 為 success
                API->>REPO: orders.update_status(order_id, paid)
                REPO->>DB: UPDATE orders SET status 為 paid
                API-->>FE: 200，payment.status 為 success，order.status 為 paid
            end
        end
    end
```

### 7.4 補充：訂單狀態轉換圖

三張循序圖分別展示了訂單狀態變化的「觸發時機」，這張補充的狀態圖把 `orders.status` 所有可能的轉換整理在一起，方便對照第 5.5 節的 `CHECK` 約束。

```mermaid
stateDiagram-v2
    [*] --> pending: POST /api/orders 建單成功
    pending --> paid: 付款成功
    pending --> failed: 付款失敗，測試卡號 4000000000000002
    failed --> paid: 重新呼叫付款，這次成功
    failed --> failed: 重新呼叫付款，仍然失敗
    paid --> [*]

    note right of pending
        cancelled 是 schema 保留值
        目前 14 支 API 沒有取消訂單端點
        因此本圖未畫出對應轉換
    end note
```

---

## 8. 教學簡化聲明

這一節誠實列出 MeowShop 為了教學目的做了哪些簡化，以及對應到真實系統會怎麼處理。**這不是「做錯了」，而是刻意的取捨**——目的是讓學員在有限的時間裡，把心力放在全端串接的核心邏輯上，同時清楚知道「如果這是真的要上線的產品，還缺哪些東西」。

### 8.1 JWT token 存放在 `localStorage`

- **簡化了什麼**：`auth.js` 直接把 `access_token` 存進瀏覽器的 `localStorage`，每次呼叫 API 時從 `localStorage` 讀出來塞進 `Authorization` header。
- **真實系統怎麼做**：正式產品通常會把 token 放進 `httpOnly` + `Secure` + `SameSite` 的 cookie。`httpOnly` 讓瀏覽器端的 JavaScript 完全讀不到 cookie 內容，這樣就算網站被注入了惡意的 XSS script，攻擊者也偷不走 token；而 `localStorage` 裡的任何內容，只要頁面上跑得動一段惡意 JS，就能被讀走。
- **為什麼教學階段選擇 localStorage**：`httpOnly` cookie 沒辦法用前端 JS 讀取，這對「想在瀏覽器 devtool 裡親眼看到 JWT 長什麼樣子、理解 token 怎麼被帶著到處跑」的初學情境不太友善；改用 cookie 也會牽扯到 CSRF token 防護、跨網域 cookie 屬性設定，這些是進階資安主題，先跳過能讓學員專注在「登入 → 拿 token → 帶著 token 呼叫受保護 API」這條主線上。

### 8.2 建單不扣庫存，付款成功才扣庫存

- **簡化了什麼**：`POST /api/orders` 只是把購物車內容轉成訂單快照，完全不動 `products.stock`；要等到 `POST /api/payments/mock` 判定付款成功，才會真的執行 `decrease_stock`。
- **真實系統怎麼做**：常見的進階做法是「預留庫存」（stock reservation）——使用者建單的當下就先把庫存暫扣起來（例如另開一個「已預留」欄位，或設定一個有效期限的 hold），如果超過某個時間沒有完成付款，系統自動把預留的庫存釋放回去。這樣可以避免「訂單建立了、但庫存其實已經被別人買走」的窘境。
- **超賣風險（本專案存在的真實限制）**：假設某商品只剩 1 件庫存，A、B 兩人幾乎同時看到商品頁、幾乎同時按下建單，兩筆訂單都可能建立成功（因為建單不檢查扣庫存後是否為負，只檢查「當下庫存夠不夠支撐這張訂單」，而兩人建單時看到的庫存數字都還沒被彼此的操作影響）。最後只有先完成付款的那個人，才真的扣得到庫存；晚到的那個人在付款時，`decrease_stock` 的條件式 UPDATE 會抓到庫存已經不足，該筆訂單會被 409 擋下並標記為 `failed`。**這是刻意示範給學員看的真實 trade-off**：本專案選擇用比較簡單的規則換取程式碼的易讀性，代價是留有超賣的可能性。

### 8.3 SQLite 沒有處理高併發下更細緻的交易鎖定機制

- **簡化了什麼**：`decrease_stock` 用單一句「條件式 UPDATE」（`WHERE stock >= quantity`）確保庫存不會被扣成負值，這解決了「扣過頭」的問題，但沒有進一步處理 SQLite 檔案層級的鎖定、重試佇列等更細緻的高併發控制。
- **真實系統怎麼做**：正式環境的關聯式資料庫（例如 PostgreSQL）通常會搭配資料庫交易（transaction）、列鎖（`SELECT ... FOR UPDATE`），或是樂觀鎖（在資料表加一個版本號欄位，更新時檢查版本號有沒有被別人改過），來確保大流量下庫存扣減的正確性。SQLite 本身設計上就偏向單機、輕量的使用情境，不是為了應付大量併發寫入而生的。

### 8.4 密碼沒有強度規則、註冊沒有 email 驗證信、沒有管理後台

- **簡化了什麼**：`POST /api/auth/register` 只檢查密碼長度是否 ≥ 8 個字元，不檢查是否包含大小寫字母、數字、符號；帳號註冊完成立刻可以登入使用，不需要收驗證信、點連結確認信箱是本人的；整個系統也沒有讓店家上下架商品、調整庫存、看營收報表的後台介面。
- **真實系統怎麼做**：正式產品通常會加入密碼強度評分（例如用 `zxcvbn` 這類套件），要求密碼不能是常見弱密碼；註冊後寄送一封含驗證連結的 email，`users` 表會多一個 `email_verified` 欄位，未驗證的帳號可能會被限制某些功能；管理後台則通常是完全獨立的一個前端應用，搭配獨立的權限控管，不會跟消費者前台共用同一套介面。

### 8.5 Mock 金流沒有簽章驗證、沒有非同步回呼（webhook）

- **簡化了什麼**：`/api/payments/mock` 是前端直接呼叫、後端同步判斷結果直接回傳，整個過程沒有任何第三方服務參與。
- **真實系統怎麼做**：像 PayUNI、Stripe 這類真實金流服務，典型流程是：使用者被導去金流商的付款頁面輸入卡號 → 金流商完成扣款後，**非同步**呼叫商家後端預先註冊好的 webhook URL，通知交易結果 → 商家後端收到 webhook 之後，第一件事是**驗證這個請求真的是金流商發出的**（通常是驗證一段簽章/簽名，防止有心人偽造一個「付款成功」的假 webhook 請求）→ 驗證通過後才更新訂單狀態。這個「非同步回呼 + 簽章驗證」的模式，是真實金流整合裡最容易被忽略、卻也是最容易出資安漏洞的一步——如果忘記驗證簽章，任何人都可以直接偽造一個 webhook 請求，把自己的訂單標記成「已付款」。

---

## 9. 開發指引

建議按照以下順序開發，每個階段都建立在前一個階段之上，且每個階段結束後都要能跑得動對應的 pytest 測試，再往下一階段推進。

### 階段 1：環境與資料庫

- [ ] 建立 `backend/` 虛擬環境，安裝 `requirements.txt` 所有套件
- [ ] 撰寫 `.env.example`，並在本機複製一份 `.env`
- [ ] 撰寫 `db/sqlite_schema.sql` 與 `db/supabase_schema.sql`，欄位名稱完全對齊第 5 節
- [ ] 撰寫 `db/seed_products.json`（10 筆種子商品，對齊 SPEC §8）
- [ ] 撰寫 `scripts/init_db.py`：建表 + 匯入種子資料，預設已存在就跳過，`--reset` 旗標才允許重建

**驗收標準**

- [ ] 在全新的空 `backend/data/` 資料夾下執行 `python scripts/init_db.py` 能成功建出 `meowshop.db`
- [ ] 不加 `--reset` 重複執行 `init_db.py`，不會報錯，也不會清空既有資料
- [ ] 加 `--reset` 執行會重建資料表
- [ ] 打開 `meowshop.db` 檢查 `products` 表，確實有 10 筆種子資料，欄位與第 5 節、SPEC §8 完全一致

### 階段 2：認證模組

- [ ] `security.py`：bcrypt 雜湊/驗證、JWT 簽發/解碼（HS256，24 小時效期）
- [ ] `schemas.py`：註冊、登入、使用者相關的 Pydantic model
- [ ] `repositories/base.py`、`sqlite_repo.py`：`UserRepository` 介面與 SQLite 實作
- [ ] `deps.py`：`get_current_user` 依賴，解析 `Authorization: Bearer` header
- [ ] `routers/auth.py`：3 支端點（register / login / me）

**驗收標準**

- [ ] 可成功註冊新帳號，回傳 201 與正確欄位
- [ ] 重複 email 註冊回 409，訊息符合 4.3 節
- [ ] 登入成功回 `access_token`；帳密其中一個錯，一律回 401「email 或密碼錯誤」（不分開講）
- [ ] `/api/auth/me` 帶正確 token 回 200；不帶或帶壞 token 一律回 401「請先登入」
- [ ] `pytest tests/test_auth.py` 全部通過

### 階段 3：商品模組

- [ ] `repositories/base.py`、`sqlite_repo.py`：`ProductRepository` 介面與 SQLite 實作（含 `decrease_stock` 條件式 UPDATE）
- [ ] `routers/products.py`：2 支端點（清單 / 詳情）

**驗收標準**

- [ ] `GET /api/products` 可依 `category`、`search` 篩選，且只回傳 `is_active=true` 的商品
- [ ] `GET /api/products/{id}` 對不存在或已下架的商品回 404「找不到這個商品」
- [ ] `pytest tests/test_products.py` 全部通過

### 階段 4：購物車模組

- [ ] `repositories/base.py`、`sqlite_repo.py`：`CartRepository` 介面與 SQLite 實作（`upsert_item`/`set_quantity`/`remove_item`/`clear`）
- [ ] `routers/cart.py`：4 支端點

**驗收標準**

- [ ] 未登入呼叫任一購物車端點，一律回 401「請先登入」
- [ ] 加入超過目前庫存的數量會回 409，訊息包含實際剩餘庫存數字
- [ ] 同一商品重複呼叫 `POST /api/cart/items` 會累加數量，不是覆蓋
- [ ] `PATCH` 直接覆蓋數量、`DELETE` 正確移除該項目
- [ ] `pytest tests/test_cart.py` 全部通過

### 階段 5：訂單與付款模組

- [ ] `repositories/base.py`、`sqlite_repo.py`：`OrderRepository` 介面與 SQLite 實作（`create` 一次寫入 `orders` + `order_items`、`update_status`、`add_payment`）
- [ ] `routers/orders.py`：3 支端點
- [ ] `routers/payments.py`：mock 金流邏輯（卡號 `4000000000000002` 判定失敗，其他判定成功）

**驗收標準**

- [ ] 空購物車呼叫 `POST /api/orders` 回 400「購物車是空的」
- [ ] 建單成功後，購物車被清空，`order_items` 正確快照當下的商品名稱與單價
- [ ] 用測試失敗卡號 `4000000000000002` 付款：`payments` 寫入一筆 `status=failed`，訂單變成 `failed`，商品庫存不變
- [ ] 用一般卡號（如 `4242424242424242`）付款：`payments` 寫入一筆 `status=success`，訂單變成 `paid`，對應商品庫存正確減少
- [ ] 對已經是 `paid` 的訂單再次付款，回 409「這筆訂單已經付款完成」
- [ ] `failed` 狀態的訂單可以重新呼叫 `/api/payments/mock` 付款
- [ ] `pytest tests/test_orders_payments.py` 全部通過，含完整下單到付款的 E2E 流程

### 階段 6：前端整合

- [ ] `js/api.js`、`js/auth.js`、`js/ui.js` 共用模組完成
- [ ] 7 個頁面（首頁、商品清單、商品詳情、登入、購物車、結帳、我的訂單）分別串接對應 API

**驗收標準**

- [ ] 首頁精選商品、商品清單、商品詳情的資料都來自 API，沒有任何寫死在 HTML/JS 裡的商品資料
- [ ] 未登入狀態點「加入購物車」會跳出提示，並導向 `login.html`
- [ ] 結帳流程可以分別用兩組測試卡號，實際看到「付款成功」與「付款失敗」兩種畫面
- [ ] 「我的訂單」頁能正確顯示 `pending`/`paid`/`failed` 三種狀態徽章，`pending`/`failed` 訂單有「重新付款」按鈕
- [ ] 手機寬度（< 768px）版面正常，不破版

---

*本文件版本 v1.0，最後更新 2026-07-22。如果對本文件或專案有任何問題，歡迎聯絡我：呂紹民 Darren Lu（kevin868686@gmail.com）。*
