# API 文件

回上層：[stage4 README](../README.md)

- Base URL：開發模式 `http://localhost:8004`（前端另外用 5173 + proxy，見
  [`DEPLOY.md`](DEPLOY.md)）；正式合體模式跟前端同源，直接用 `/api/...`。
- 全部端點都在 `/api` 前綴下。
- 需要登入的端點要帶 `Authorization: Bearer <token>`；沒帶或 token 無效一律
  回 `401 {"detail":"請先登入"}`。
- 以下所有 request/response 都是**實際執行 curl 拿到的原文**（2026-07-23，
  本機 `localhost:8004`，`backend/data/brewgo.db` 剛跑過 `init_db.py`、
  只有一個測試帳號 `docs@example.com` 的乾淨狀態），不是手寫的範例；`id`／
  `created_at`／JWT 內容會因為你自己執行的時間而不同，其餘欄位形狀應該一致。

## 端點總覽

| 方法 | 路徑 | 需要登入 | 說明 |
|---|---|---|---|
| POST | `/api/auth/register` | 否 | 註冊新帳號 |
| POST | `/api/auth/login` | 否 | 登入拿 JWT |
| GET | `/api/auth/me` | 是 | 查自己的帳號資料 |
| GET | `/api/products` | 否 | 商品清單（`category` / `search` 查詢參數） |
| GET | `/api/products/{id}` | 否 | 商品詳情 |
| GET | `/api/cart` | 是 | 查自己的購物車 |
| POST | `/api/cart/items` | 是 | 加入購物車（同商品累加） |
| PATCH | `/api/cart/items/{product_id}` | 是 | 覆蓋數量（不是累加） |
| DELETE | `/api/cart/items/{product_id}` | 是 | 移除單一品項 |
| POST | `/api/orders` | 是 | 用購物車內容建立訂單（扣庫存＋清空購物車） |
| GET | `/api/orders` | 是 | 查自己的訂單列表 |
| GET | `/api/orders/{id}` | 是 | 查單筆訂單詳情 |
| GET | `/api/health` | 否 | 健康檢查 |

## 認證 auth

### `POST /api/auth/register` → 201

```bash
curl -s -X POST http://localhost:8004/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"docs@example.com","password":"password123","name":"文件範例"}'
```
```json
{"id":1,"email":"docs@example.com","name":"文件範例","created_at":"2026-07-23 16:34:59"}
```

同 email 再註冊一次 → 409：
```json
{"detail":"這個 email 已經註冊過了"}
```

### `POST /api/auth/login` → 200

```bash
curl -s -X POST http://localhost:8004/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"docs@example.com","password":"password123"}'
```
```json
{"access_token":"eyJhbGciOiJIUzI1NiIs...(略)","token_type":"bearer","user":{"id":1,"email":"docs@example.com","name":"文件範例"}}
```

密碼錯誤 → 401（「查無此帳號」跟「密碼錯誤」刻意回同一句訊息，避免帳號列舉攻擊）：
```json
{"detail":"email 或密碼錯誤"}
```

### `GET /api/auth/me` → 200

```bash
curl -s http://localhost:8004/api/auth/me -H "Authorization: Bearer $TOKEN"
```
```json
{"id":1,"email":"docs@example.com","name":"文件範例","created_at":"2026-07-23 16:34:59"}
```

不帶 token → 401（`HTTP_401`）：
```json
{"detail":"請先登入"}
```

## 商品 products

### `GET /api/products` → 200（不需要登入）

```bash
curl -s http://localhost:8004/api/products
```
實測 `total=12`，`items` 節錄前兩筆：
```json
[
  {"id":1,"name":"耶加雪菲 淺焙單品豆 250g","description":"柑橘與茉莉花香，日曬處理","price":520,"stock":25,"category":"beans","image_url":"/images/p1.svg"},
  {"id":2,"name":"哥倫比亞 薇拉 中焙豆 250g","description":"焦糖甜感，堅果尾韻","price":460,"stock":30,"category":"beans","image_url":"/images/p2.svg"}
]
```

分類篩選（實測：`category=beans` 命中 4 筆，id 為 `[1, 2, 3, 4]`）：
```bash
curl -s "http://localhost:8004/api/products?category=beans"
```

關鍵字搜尋（實測：`search=壺` 命中 1 筆「手沖細口壺 600ml」）：
```bash
curl -s "http://localhost:8004/api/products?search=壺"
```
```json
{"items":[{"id":7,"name":"手沖細口壺 600ml","description":"不鏽鋼細口，水流穩定","price":980,"stock":15,"category":"gear","image_url":"/images/p7.svg"}],"total":1}
```

### `GET /api/products/{id}` → 200 / 404 / 422

```bash
curl -s http://localhost:8004/api/products/1
```
```json
{"id":1,"name":"耶加雪菲 淺焙單品豆 250g","description":"柑橘與茉莉花香，日曬處理","price":520,"stock":25,"category":"beans","image_url":"/images/p1.svg"}
```

```bash
curl -s http://localhost:8004/api/products/9999
```
```json
{"detail":"找不到這個商品"}
```

`{id}` 超過 SQLite `INTEGER` 欄位的 64-bit 範圍（例如 20 位數）→ 422，不是 500
（實測回應原文，完整理由見 `app/schemas.py` 的 `SQLITE_INT64_MAX`）：
```bash
curl -s http://localhost:8004/api/products/99999999999999999999
```
```json
{"detail":[{"type":"less_than_equal","loc":["path","product_id"],"msg":"Input should be less than or equal to 9223372036854775807","input":"99999999999999999999","ctx":{"le":9223372036854775807}}]}
```

## 購物車 cart（全部需要登入）

不帶 token → 401：
```bash
curl -s http://localhost:8004/api/cart
```
```json
{"detail":"請先登入"}
```

空購物車：
```bash
curl -s http://localhost:8004/api/cart -H "Authorization: Bearer $TOKEN"
```
```json
{"items":[],"total_amount":0,"total_quantity":0}
```

### `POST /api/cart/items` → 200 / 409 / 422

```bash
curl -s -X POST http://localhost:8004/api/cart/items \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"product_id":1,"quantity":2}'
```
```json
{"items":[{"product_id":1,"name":"耶加雪菲 淺焙單品豆 250g","price":520,"image_url":"/images/p1.svg","quantity":2,"stock":25,"subtotal":1040}],"total_amount":1040,"total_quantity":2}
```

超過庫存（商品 6 種子庫存只有 3 件，實測回應原文）：
```bash
curl -s -X POST http://localhost:8004/api/cart/items \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"product_id":6,"quantity":10}'
```
```json
{"detail":"庫存不足，目前只剩 3 件"}
```

`product_id` 超過 SQLite `INTEGER` 欄位的 64-bit 範圍 → 422（`CartItemIn.product_id`
的 `Field(..., le=SQLITE_INT64_MAX)`，實測回應原文）：
```bash
curl -s -X POST http://localhost:8004/api/cart/items \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"product_id":99999999999999999999,"quantity":2}'
```
```json
{"detail":[{"type":"less_than_equal","loc":["body","product_id"],"msg":"Input should be less than or equal to 9223372036854775807","input":99999999999999999999,"ctx":{"le":9223372036854775807}}]}
```

### `PATCH /api/cart/items/{product_id}` → 200（覆蓋數量，不是累加） / 422

```bash
curl -s -X PATCH http://localhost:8004/api/cart/items/1 \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"quantity":5}'
```
```json
{"items":[{"product_id":1,"name":"耶加雪菲 淺焙單品豆 250g","price":520,"image_url":"/images/p1.svg","quantity":5,"stock":25,"subtotal":2600}],"total_amount":2600,"total_quantity":5}
```

路徑裡的 `{product_id}` 超過 SQLite `INTEGER` 欄位的 64-bit 範圍 → 422（實測回應原文）：
```bash
curl -s -X PATCH http://localhost:8004/api/cart/items/99999999999999999999 \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"quantity":5}'
```
```json
{"detail":[{"type":"less_than_equal","loc":["path","product_id"],"msg":"Input should be less than or equal to 9223372036854775807","input":"99999999999999999999","ctx":{"le":9223372036854775807}}]}
```

### `DELETE /api/cart/items/{product_id}` → 200 / 404 / 422

```bash
curl -s -X DELETE http://localhost:8004/api/cart/items/1 -H "Authorization: Bearer $TOKEN"
```
```json
{"items":[],"total_amount":0,"total_quantity":0}
```

不在購物車裡的商品 → 404（實測原文）：
```json
{"detail":"購物車裡沒有這個商品"}
```

`{product_id}` 超過 SQLite `INTEGER` 欄位的 64-bit 範圍 → 422（實測回應原文）：
```bash
curl -s -X DELETE http://localhost:8004/api/cart/items/99999999999999999999 -H "Authorization: Bearer $TOKEN"
```
```json
{"detail":[{"type":"less_than_equal","loc":["path","product_id"],"msg":"Input should be less than or equal to 9223372036854775807","input":"99999999999999999999","ctx":{"le":9223372036854775807}}]}
```

## 訂單 orders（全部需要登入）

### `POST /api/orders` → 201 / 400 / 409

空購物車 → 400：
```bash
curl -s -X POST http://localhost:8004/api/orders \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"recipient_name":"文件範例","recipient_address":"台北市大安區某路 5 號"}'
```
```json
{"detail":"購物車是空的"}
```

先加入商品 2（哥倫比亞 薇拉 中焙豆，NT$460，種子庫存 30）數量 3，再建單：
```bash
curl -s -X POST http://localhost:8004/api/cart/items \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"product_id":2,"quantity":3}'

curl -s -X POST http://localhost:8004/api/orders \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"recipient_name":"文件範例","recipient_address":"台北市大安區某路 5 號"}'
```
```json
{"id":1,"status":"pending","total_amount":1380,"recipient_name":"文件範例","recipient_address":"台北市大安區某路 5 號","created_at":"2026-07-23 16:35:24","updated_at":"2026-07-23 16:35:24","items":[{"product_id":2,"product_name":"哥倫比亞 薇拉 中焙豆 250g","unit_price":460,"quantity":3}]}
```

實測：商品 2 的庫存在建單後從 30 變成 27（`GET /api/products/2` 的 `stock` 欄位），
確認扣庫存有真的落地到資料庫，不是只回應假裝成功。庫存不足時（見
[`DATABASE.md`](DATABASE.md)「訂單狀態與扣庫存時機」一節）回 409，訊息格式跟
購物車一致：`{"detail":"庫存不足，目前只剩 N 件"}`。

### `GET /api/orders` → 200

```bash
curl -s http://localhost:8004/api/orders -H "Authorization: Bearer $TOKEN"
```
```json
{"items":[{"id":1,"status":"pending","total_amount":1380,"recipient_name":"文件範例","recipient_address":"台北市大安區某路 5 號","created_at":"2026-07-23 16:35:24","updated_at":"2026-07-23 16:35:24"}]}
```

### `GET /api/orders/{id}` → 200 / 404 / 422

```bash
curl -s http://localhost:8004/api/orders/1 -H "Authorization: Bearer $TOKEN"
```
```json
{"id":1,"status":"pending","total_amount":1380,"recipient_name":"文件範例","recipient_address":"台北市大安區某路 5 號","created_at":"2026-07-23 16:35:24","updated_at":"2026-07-23 16:35:24","items":[{"product_id":2,"product_name":"哥倫比亞 薇拉 中焙豆 250g","unit_price":460,"quantity":3}]}
```

`{id}` 超過 SQLite `INTEGER` 欄位的 64-bit 範圍 → 422，不是 500（實測回應原文）：
```bash
curl -s http://localhost:8004/api/orders/99999999999999999999 -H "Authorization: Bearer $TOKEN"
```
```json
{"detail":[{"type":"less_than_equal","loc":["path","order_id"],"msg":"Input should be less than or equal to 9223372036854775807","input":"99999999999999999999","ctx":{"le":9223372036854775807}}]}
```

查不存在的訂單、或別人的訂單 → 一律 404（實測原文，理由見
`backend/app/routers/orders.py` 的安全性註解——別人的訂單不能回 403，
否則等於洩漏「這個訂單 id 存在」）：
```json
{"detail":"找不到這筆訂單"}
```

## 健康檢查

```bash
curl -s http://localhost:8004/api/health
```
```json
{"status":"ok"}
```

## 互動式文件

後端啟動後打開 [http://localhost:8004/docs](http://localhost:8004/docs) 就是
FastAPI 自動產生的 Swagger UI，每支 API 都能在網頁上直接展開、填參數、按
「Execute」試打，右上角「Authorize」按鈕可以貼 `Bearer <token>` 測需要登入的端點。
