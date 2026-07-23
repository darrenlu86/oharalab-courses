# API 文件

回上層：[stage5 README](../README.md)

- Base URL：開發模式 `http://localhost:8005`（前台另用 5173 + proxy、後台另用
  5175 + proxy，見 [`DEPLOY.md`](DEPLOY.md)）；正式合體模式跟前台/後台同源，
  直接用 `/api/...`。
- 全部端點都在 `/api` 前綴下。
- 需要登入的端點要帶 `Authorization: Bearer <token>`；沒帶或 token 無效一律回
  `401 {"detail":"請先登入"}`。`/api/admin/*` 額外要求 `role=admin`，否則回
  `403 {"detail":"需要管理員權限"}`。
- 以下所有 request/response 都是**實際執行 curl 拿到的原文**（2026-07-23，
  本機 `localhost:8005`，剛跑過 `init_db.py` 的乾淨狀態），不是手寫的範例；
  `id`／`created_at`／JWT 內容會因為你自己執行的時間而不同，其餘欄位形狀應該
  一致。

## 端點總覽

| 方法 | 路徑 | 需要登入 | 說明 |
|---|---|---|---|
| POST | `/api/auth/register` | 否 | 註冊新帳號（永遠是 `role=customer`） |
| POST | `/api/auth/login` | 否 | 登入拿 JWT（回傳的 `user` 含 `role`） |
| GET | `/api/auth/me` | 是 | 查自己的帳號資料 |
| GET | `/api/products` | 否 | 商品清單（僅 `is_active=1`；`category` / `search` 查詢參數） |
| GET | `/api/products/{id}` | 否 | 商品詳情（已下架回 404） |
| GET | `/api/cart` | 是 | 查自己的購物車 |
| POST | `/api/cart/items` | 是 | 加入購物車（同商品累加） |
| PATCH | `/api/cart/items/{product_id}` | 是 | 覆蓋數量（不是累加） |
| DELETE | `/api/cart/items/{product_id}` | 是 | 移除單一品項 |
| POST | `/api/orders` | 是 | 用購物車內容建立訂單（**不扣庫存**，見下方） |
| GET | `/api/orders` | 是 | 查自己的訂單列表 |
| GET | `/api/orders/{id}` | 是 | 查單筆訂單詳情 |
| POST | `/api/orders/{id}/cancel` | 是 | 取消訂單（僅限本人、且訂單是 pending） |
| POST | `/api/payments/mock` | 是 | 模擬付款（成功才扣庫存） |
| GET | `/api/admin/summary` | admin | 儀表板聚合數字 |
| GET | `/api/admin/products` | admin | 商品列表（含已下架） |
| POST | `/api/admin/products` | admin | 新增商品 |
| PATCH | `/api/admin/products/{id}` | admin | 編輯商品／上下架 |
| GET | `/api/admin/orders` | admin | 全站訂單列表（`order_status` 篩選） |
| PATCH | `/api/admin/orders/{id}/status` | admin | 訂單狀態流轉 |
| GET | `/api/admin/users` | admin | 會員清單（不含密碼欄位） |
| GET | `/api/health` | 否 | 健康檢查 |

## 與上一階段的差異（schema 層級）

1. `UserPublic` 多了 `role` 欄位（`customer` / `admin`）。
2. `ProductOut` 多了 `is_active` 欄位。
3. `OrderSummaryOut.status` 從只有 `'pending'` 一種值，擴充成
   `pending / paid / failed / shipped / completed / cancelled`。
4. 新增 `/api/payments/mock`、`/api/orders/{id}/cancel`、整組 `/api/admin/*`。
5. `CartItemOut` 多了 `is_active` 欄位——商品被下架不會自動從購物車移除，
   見下方「購物車 cart」一節。

## 認證 auth

### `POST /api/auth/register` → 201

```bash
curl -s -X POST http://localhost:8005/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"docs5@example.com","password":"password123","name":"文件範例"}'
```
```json
{"id":3,"email":"docs5@example.com","name":"文件範例","role":"customer","created_at":"2026-07-23 17:12:21"}
```

同 email 再註冊一次 → 409：
```json
{"detail":"這個 email 已經註冊過了"}
```

### `POST /api/auth/login` → 200

```bash
curl -s -X POST http://localhost:8005/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"docs5@example.com","password":"password123"}'
```
```json
{"access_token":"eyJhbGciOiJIUzI1NiIs...(略)","token_type":"bearer","user":{"id":3,"email":"docs5@example.com","name":"文件範例","role":"customer"}}
```

**已知限制（實測抓到、已修正的行為，誠實記錄）**：`UserLogin.email`
刻意用 `str` 而不是 `EmailStr`——原本沿用 stage4 用 `EmailStr`，實測發現
master spec 規定的測試帳號 `admin@brewgo.test` / `customer@brewgo.test` 連自己
都登入不了：`email-validator` 2.x 套件預設會拒絕 IANA 保留給文件/測試用途的
特殊網域（`.test` / `.invalid` / `.localhost` / `.arpa` / `.onion`，見 RFC
2606）。登入端點的 email 格式驗證意義本來就不大（格式不對就是查無此人，
一樣回 401），所以改用 `str`；`UserCreate.email`（註冊用）維持 `EmailStr`，
新註冊帳號的格式驗證還是有意義的。完整說明見 `backend/app/schemas.py` 的
`UserLogin` 註解。

## 商品 products

### `GET /api/products` → 200（不需要登入，僅回傳 `is_active=1` 的商品）

```bash
curl -s http://localhost:8005/api/products
```
實測 `total=12`（乾淨狀態下型錄 12 筆全部上架）。

### `GET /api/products/{id}` → 200 / 404 / 422

`{id}` 超過 SQLite `INTEGER` 欄位的 64-bit 範圍（例如 20 位數）→ 422，不是 500
（實測回應原文，完整理由見 `app/schemas.py` 的 `SQLITE_INT64_MAX`，行為與
stage4 一致）：
```bash
curl -s http://localhost:8005/api/products/99999999999999999999
```
```json
{"detail":[{"type":"less_than_equal","loc":["path","product_id"],"msg":"Input should be less than or equal to 9223372036854775807","input":"99999999999999999999","ctx":{"le":9223372036854775807}}]}
```

已下架商品的詳情，實測（先用 admin 把商品 2 下架）：
```bash
curl -s -X PATCH http://localhost:8005/api/admin/products/2 \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"is_active":false}'
```
```json
{"id":2,"name":"哥倫比亞 薇拉 中焙豆 250g","description":"焦糖甜感，堅果尾韻","price":460,"stock":30,"category":"beans","image_url":"/images/p2.svg","is_active":false}
```
```bash
curl -s http://localhost:8005/api/products/2
```
```json
{"detail":"找不到這個商品"}
```
跟「商品根本不存在」用同一個狀態碼與訊息（實測原文），理由跟 stage4「別人的
訂單一律 404」是同一套教學點：不讓外部分辨「這個 id 是不存在還是被下架」。

## 購物車 cart（全部需要登入，行為沿用 stage4，這裡不重複貼）

見 stage4 `docs/API.md` 對應章節；`product_id`／`quantity` 的輸入範圍限制
（`SQLITE_INT64_MAX`／`MAX_ITEM_QUANTITY`）完全一致。

stage5 差異：`CartItemOut` 多了一個 `is_active` 欄位。商品被後台下架
（`is_active=0`）之後，已經在購物車裡的品項**不會**被自動移除——`cart_items`
表本身沒有這個機制（見 `app/db/database.py` `get_cart_items()`）。如果回應
不帶這個欄位，購物車會「照常顯示、完全沒有任何標示」，使用者要一路到建單被
下方「訂單 orders」一節的 409 擋下，才第一次知道發生了什麼事，卻不知道該移除
哪一項——這是本頁修復前的實際行為。修復後前端（`frontend/src/pages/
Cart.jsx`）依這個欄位顯示「已下架」徽章、停用該品項的數量調整、並停用「前往
結帳」按鈕，但這整段前端邏輯純粹是體驗優化，真正擋住建單的仍然是後端的
409（「後端守門、前端好心提示」）。

實測：先把商品 1（耶加雪菲，種子庫存 25）加進購物車，admin 把商品 1 下架，
再查一次購物車：

```bash
curl -s -X POST http://localhost:8005/api/cart/items \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"product_id":1,"quantity":2}'

curl -s -X PATCH http://localhost:8005/api/admin/products/1 \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"is_active":false}'

curl -s http://localhost:8005/api/cart -H "Authorization: Bearer $TOKEN"
```
```json
{"items":[{"product_id":1,"name":"耶加雪菲 淺焙單品豆 250g","price":520,"image_url":"/images/p1.svg","quantity":2,"stock":25,"is_active":false,"subtotal":1040}],"total_amount":1040,"total_quantity":2}
```

## 訂單 orders（全部需要登入）

### `POST /api/orders` → 201 / 400 / 409

跟 stage4 最大的差異：**建單不扣庫存**。先加入商品 1（耶加雪菲淺焙豆，NT$520，
種子庫存 25）數量 2，再建單：

```bash
curl -s -X POST http://localhost:8005/api/cart/items \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"product_id":1,"quantity":2}'

curl -s -X POST http://localhost:8005/api/orders \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"recipient_name":"文件範例","recipient_address":"台北市大安區某路 5 號"}'
```
```json
{"id":8,"status":"pending","total_amount":1040,"recipient_name":"文件範例","recipient_address":"台北市大安區某路 5 號","created_at":"2026-07-23 17:12:30","updated_at":"2026-07-23 17:12:30","items":[{"product_id":1,"product_name":"耶加雪菲 淺焙單品豆 250g","unit_price":520,"quantity":2}]}
```

實測：建單後商品 1 的庫存**仍然是 25**（`GET /api/products/1` 的 `stock`
欄位），確認建單真的不會動用庫存——要付款成功才會扣，見下方「付款」一節。

購物車內有已下架商品時 → 409（實測：延續上方「購物車 cart」一節已經下架
商品 1 的狀態，直接嘗試建單）：

```bash
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8005/api/orders \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"recipient_name":"驗收測試","recipient_address":"台北市信義區某路 1 號"}'
# 409
```
```json
{"detail":"購物車內有商品已下架"}
```
建單失敗時購物車**不會**被清空（商品仍然留在購物車裡，讓使用者自己決定要
移除還是等重新上架）——但顧客其實不用等到這裡才第一次知道，購物車頁在建單
之前就已經用「已下架」徽章標示出來了（見上方「購物車 cart」一節）。

### `GET /api/orders` → 200

```bash
curl -s http://localhost:8005/api/orders -H "Authorization: Bearer $TOKEN"
```
```json
{"items":[{"id":9,"status":"pending","total_amount":460,"recipient_name":"文件範例","recipient_address":"台北市大安區某路 5 號","created_at":"2026-07-23 17:12:48","updated_at":"2026-07-23 17:12:48"},{"id":8,"status":"shipped","total_amount":1040,"recipient_name":"文件範例","recipient_address":"台北市大安區某路 5 號","created_at":"2026-07-23 17:12:30","updated_at":"2026-07-23 17:12:48"}]}
```
最新的訂單排最前面（`ORDER BY created_at DESC, id DESC`）。

### `POST /api/orders/{id}/cancel` → 200 / 409 / 422（stage5 新增）

`{id}` 超過 SQLite `INTEGER` 欄位的 64-bit 範圍 → 422，不是 500（實測回應原文）：
```bash
curl -s -X POST http://localhost:8005/api/orders/99999999999999999999/cancel -H "Authorization: Bearer $TOKEN"
```
```json
{"detail":[{"type":"less_than_equal","loc":["path","order_id"],"msg":"Input should be less than or equal to 9223372036854775807","input":"99999999999999999999","ctx":{"le":9223372036854775807}}]}
```

只有本人、且訂單還是 `pending` 才能取消：

```bash
curl -s -X POST http://localhost:8005/api/orders/10/cancel -H "Authorization: Bearer $TOKEN"
```
```json
{"id":10,"status":"cancelled","total_amount":480,"recipient_name":"文件範例","recipient_address":"台北市大安區某路 5 號","created_at":"2026-07-23 17:12:57","updated_at":"2026-07-23 17:12:57","items":[{"product_id":3,"product_name":"瓜地馬拉 安提瓜 深焙豆 250g","unit_price":480,"quantity":1}]}
```
已取消的訂單再取消一次 → 409（實測原文）：
```json
{"detail":"訂單目前狀態是「cancelled」，無法由顧客自行取消"}
```

## 付款 payments（stage5 新增）

測試卡號規則（照 meowshop 的規則，也顯示在結帳頁面上）：

| 卡號 | 結果 |
|---|---|
| `4242 4242 4242 4242` | 付款成功 |
| `4000 0000 0000 0002` | 付款失敗（訂單狀態變 `failed`，可以重新輸入卡號重試） |
| 其他任意 13-19 碼數字 | 一律視為成功 |

### `POST /api/payments/mock` → 200 / 404 / 409 / 422

`order_id` 超過 SQLite `INTEGER` 欄位的 64-bit 範圍 → 422（`PaymentIn.order_id`
的 `Field(..., le=SQLITE_INT64_MAX)`，實測回應原文）：
```bash
curl -s -X POST http://localhost:8005/api/payments/mock \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"order_id":99999999999999999999,"card_number":"4242424242424242","card_holder":"文件範例"}'
```
```json
{"detail":[{"type":"less_than_equal","loc":["body","order_id"],"msg":"Input should be less than or equal to 9223372036854775807","input":99999999999999999999,"ctx":{"le":9223372036854775807}}]}
```

先用失敗卡號：

```bash
curl -s -X POST http://localhost:8005/api/payments/mock \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"order_id":8,"card_number":"4000000000000002","card_holder":"文件範例"}'
```
```json
{"payment":{"id":7,"order_id":8,"amount":1040,"card_last4":"0002","status":"failed","created_at":"2026-07-23 17:12:37"},"order":{"id":8,"status":"failed","total_amount":1040,"recipient_name":"文件範例","recipient_address":"台北市大安區某路 5 號","created_at":"2026-07-23 17:12:30","updated_at":"2026-07-23 17:12:37","items":[{"product_id":1,"product_name":"耶加雪菲 淺焙單品豆 250g","unit_price":520,"quantity":2}]}}
```

用同一筆訂單重試，換成成功卡號：

```bash
curl -s -X POST http://localhost:8005/api/payments/mock \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"order_id":8,"card_number":"4242 4242 4242 4242","card_holder":"文件範例"}'
```
```json
{"payment":{"id":8,"order_id":8,"amount":1040,"card_last4":"4242","status":"success","created_at":"2026-07-23 17:12:37"},"order":{"id":8,"status":"paid","total_amount":1040,"recipient_name":"文件範例","recipient_address":"台北市大安區某路 5 號","created_at":"2026-07-23 17:12:30","updated_at":"2026-07-23 17:12:37","items":[{"product_id":1,"product_name":"耶加雪菲 淺焙單品豆 250g","unit_price":520,"quantity":2}]}}
```

實測：這時商品 1 的庫存從 25 變成 23（`GET /api/products/1`），確認付款成功
才是真正扣庫存的時間點。已付款的訂單再付一次 → 409（實測原文）：
```json
{"detail":"這筆訂單已經付款完成"}
```

## 後台 admin（stage5 新增，全部需要 `role=admin`）

### `GET /api/admin/summary` → 200

```bash
curl -s http://localhost:8005/api/admin/summary -H "Authorization: Bearer $ADMIN_TOKEN"
```
```json
{"total_revenue":6090,"total_orders":9,"pending_shipment_orders":1,"low_stock_products":[{"id":11,"name":"冷萃咖啡瓶 1L","description":"冷萃專用密封瓶（補貨中示範）","price":550,"stock":0,"category":"gear","image_url":"/images/p11.svg","is_active":true},{"id":6,"name":"深焙醇厚掛耳包 10 入","description":"深焙配方掛耳，牛奶絕配","price":300,"stock":3,"category":"drip","image_url":"/images/p6.svg","is_active":true}],"member_count":2}
```
`total_revenue` 是 `paid`＋`shipped`＋`completed` 三種狀態的訂單金額總和；
`low_stock_products` 是庫存 <5 的上架商品（種子資料 id=6／id=11 一定會出現）；
`member_count` 只算 `role=customer`（不含 admin 帳號本身）。聚合正確性有實測
（造數據自己驗算），見 `backend/tests/test_admin.py`
`test_admin_summary_aggregation_matches_hand_calculated_numbers`。

customer token 打這支端點 → 403（實測原文）：
```json
{"detail":"需要管理員權限"}
```

### `PATCH /api/admin/orders/{id}/status` → 200 / 404 / 409 / 422

`{id}` 超過 SQLite `INTEGER` 欄位的 64-bit 範圍 → 422，不是 500（實測回應原文，
同樣的上限也套用在 `PATCH /api/admin/products/{id}` 的 `{id}`，以及
`POST /api/admin/products` 的 `price`／`stock` 欄位，見 `app/schemas.py` 的
`SQLITE_INT64_MAX`／`MAX_PRODUCT_PRICE`／`MAX_PRODUCT_STOCK`）：
```bash
curl -s -X PATCH http://localhost:8005/api/admin/orders/99999999999999999999/status \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"status":"paid"}'
```
```json
{"detail":[{"type":"less_than_equal","loc":["path","order_id"],"msg":"Input should be less than or equal to 9223372036854775807","input":"99999999999999999999","ctx":{"le":9223372036854775807}}]}
```

非法轉移（pending 直接跳去 completed）→ 409：
```bash
curl -s -X PATCH http://localhost:8005/api/admin/orders/9/status \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"status":"completed"}'
```
```json
{"detail":"不允許從「pending」轉換成「completed」"}
```

合法轉移（paid → shipped）：
```bash
curl -s -X PATCH http://localhost:8005/api/admin/orders/8/status \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"status":"shipped"}'
```
```json
{"id":8,"status":"shipped","total_amount":1040,"recipient_name":"文件範例","recipient_address":"台北市大安區某路 5 號","created_at":"2026-07-23 17:12:30","updated_at":"2026-07-23 17:12:48","items":[{"product_id":1,"product_name":"耶加雪菲 淺焙單品豆 250g","unit_price":520,"quantity":2}],"user_id":3}
```

完整合法轉移規則見 [`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md)「訂單狀態機」一節。

### `GET /api/admin/orders?order_status=shipped` → 200（狀態篩選）

```bash
curl -s "http://localhost:8005/api/admin/orders?order_status=shipped" -H "Authorization: Bearer $ADMIN_TOKEN"
```
實測回傳 2 筆（剛出貨的訂單 8，以及種子資料裡本來就是 `shipped` 狀態的訂單
3），欄位比顧客端多一個 `user_id`，方便對照是哪個會員下的單。

### `GET /api/admin/users` → 200（不含密碼欄位）

```bash
curl -s http://localhost:8005/api/admin/users -H "Authorization: Bearer $ADMIN_TOKEN"
```
```json
{"items":[{"id":1,"email":"admin@brewgo.test","name":"店長 Admin","role":"admin","created_at":"2026-07-23 17:12:14"},{"id":2,"email":"customer@brewgo.test","name":"測試顧客","role":"customer","created_at":"2026-07-23 17:12:14"},{"id":3,"email":"docs5@example.com","name":"文件範例","role":"customer","created_at":"2026-07-23 17:12:21"}]}
```
每筆都沒有 `password_hash` 欄位（`app/db/database.py` 的 `list_users()` 在
SQL 層就沒有 SELECT 這個欄位，不是回傳後才過濾）。

## 健康檢查

```bash
curl -s http://localhost:8005/api/health
```
```json
{"status":"ok"}
```

## 互動式文件

後端啟動後打開 [http://localhost:8005/docs](http://localhost:8005/docs) 就是
FastAPI 自動產生的 Swagger UI，每支 API 都能在網頁上直接展開、填參數、按
「Execute」試打，右上角「Authorize」按鈕可以貼 `Bearer <token>` 測需要登入的
端點。
