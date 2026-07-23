# 效能／壓力測試報告

回上層：[stage6 README](../README.md)

**誠實聲明（開頭先講）**：本報告的所有數字都來自本機（單機、非正式雲端環境）
實際跑 `loadtest/locustfile.py` 的結果，**不是估算或典型值**。本機壓測數字
會受機器效能、當下背景程式、SQLite 檔案系統快取狀態等因素影響，重點是**兩輪
測試之間的相對差異與方法本身**，不是把這裡的絕對數字（例如「RPS 43」）當成
「這個系統在正式環境能扛多少人」的保證——正式環境的網路延遲、資料庫選型、
機器規格都完全不同，數字不能直接套用。

## 1. 測試環境

- 機器：MacBook（Apple M1 Pro，8 核心，16GB RAM），macOS（Darwin 25.5.0）
- Python 3.13.11、locust 2.46.1
- stage5（baseline，優化前）與 stage6（優化後）**在同一台機器上分別啟動**
  （不同時跑，避免互搶 CPU 資源影響數字），各自跑完一輪測試後才跑下一輪
- 兩輪測試前都先執行 `python scripts/init_db.py --reset`，確保商品庫存回到
  型錄的原始數字（否則上一輪測試消耗的庫存會影響下一輪的結果）
- 測試參數：50 併發使用者、spawn-rate 10（每秒新增 10 個模擬使用者）、
  跑 60 秒、headless 模式
- 指令：
  ```bash
  # stage5（baseline）
  cd stage5-platform/backend && source .venv/bin/activate && python scripts/init_db.py --reset
  uvicorn app.main:app --port 8005 &
  cd stage6-advanced/loadtest
  locust -f locustfile.py --host http://localhost:8005 \
      --users 50 --spawn-rate 10 --run-time 60s --headless --csv stage5_result

  # stage6（優化後）
  cd stage6-advanced/backend && source .venv/bin/activate && python scripts/init_db.py --reset
  uvicorn app.main:app --port 8006 &
  cd stage6-advanced/loadtest
  locust -f locustfile.py --host http://localhost:8006 \
      --users 50 --spawn-rate 10 --run-time 60s --headless --csv stage6_result
  ```

## 2. 意外發現：stage5 在真實併發下有 20.63% 的請求失敗（500）

這是本次壓測**最重要的發現**，不在原本規劃的「N+1／快取／索引」清單裡，
是跑壓測時才浮現的真實 bug——完整說明如下。

### 2.1 現象

stage5 baseline 測試（50 併發、60 秒）結束後，locust 報告：

```
Type,Name,Request Count,Failure Count,...,Requests/s,Failures/s,...
POST,/api/auth/login,13,6,...
POST,/api/auth/register,13,12,...
POST,/api/cart/items,383,29,...
GET,/api/products,1003,228,...
GET,/api/products/[id],706,162,...
,Aggregated,2118,437,...,35.75,7.38,...
```

**2118 個請求中有 437 個失敗（20.63%）**，`POST /api/auth/register` 甚至
高達 92.31%（13 次裡 12 次失敗）。錯誤報告全部都是 `HTTP 500`：

```
Error report
# occurrences      Error
------------------|---------------------------------------------------------------------------------------------------------------------------------------------
165                GET /api/products/[id]: 伺服器錯誤：HTTP 500
231                GET /api/products: 伺服器錯誤：HTTP 500
12                 POST /api/auth/register: 伺服器錯誤：HTTP 500
6                  POST /api/auth/login: 伺服器錯誤：HTTP 500
29                 POST /api/cart/items: 伺服器錯誤：HTTP 500
```

因為多數模擬顧客連註冊/登入都失敗（拿不到有效 token），連鎖導致
`POST /api/orders`／`POST /api/payments/mock` 這兩支端點在整場 60 秒測試裡
**完全沒有被成功呼叫過一次**（locust 統計表裡根本沒出現這兩行）。

### 2.2 根因（伺服器端 log 原文，非猜測）

stage5 uvicorn process 的 log（`/tmp/stage5_uvicorn.log`）出現大量這個
traceback：

```
File ".../stage5-platform/backend/app/routers/products.py", line 27, in list_products_route
    items = list_products(conn, category=category, search=search)
File ".../stage5-platform/backend/app/db/database.py", line 130, in list_products
    rows = conn.execute(sql, params).fetchall()
sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread. The object was created in thread id 6235942912 and this is thread id 6286422016.
```

**根因分析**：`app/deps.py` 的 `get_db` 是一個「非 async 的 generator
依賴」，FastAPI 對這種依賴的處理方式是透過 `anyio.to_thread.run_sync()`
丟進一個 worker 執行緒池執行。每一次 `run_sync()` 呼叫，anyio 都可能挑選
執行緒池裡「當下任何一條空閒的執行緒」來跑，**不保證同一個 request 的
「依賴解析」跟「路由函式本體」落在同一條 OS 執行緒上**——在流量低、
請求循序處理的情境下（例如 pytest 的 `TestClient`，或手動慢慢測試），執行緒
池閒置執行緒少、經常剛好被同一條執行緒接住，這個問題幾乎不會被觸發；
但在 50 併發同時發送請求的真實負載下，執行緒池裡有多條執行緒同時忙碌，
「依賴解析」與「路由函式本體」被分派到不同執行緒的機率大幅提高，
SQLite 的 `sqlite3.Connection` 物件預設不允許跨執行緒使用，因而大量拋出
`ProgrammingError`，FastAPI 把它轉成 HTTP 500 回應。

**為什麼 stage6 沒有這個問題**：stage6 為了讓
`POST /api/orders`／`POST /api/payments/mock`／
`PATCH /api/admin/orders/{id}/status` 這三支路由能夠
`await manager.broadcast_admin(...)` 推播 WebSocket 事件，把它們從 `def`
改成 `async def`，這個改動立刻讓開發階段的 `pytest -q` 自己先炸出同一個
`ProgrammingError`（測試環境用 `TestClient`，理論上流量低，但 async 路由
的執行方式本來就不同，見下方說明），逼著我們在開發階段就修好——修法是
`app/db/database.py` 的 `get_connection()` 加上
`sqlite3.connect(..., check_same_thread=False)`。這個修法對 sync/async
路由都成立，也剛好修掉了 stage5 這個「只有在真實高併發下才會大量重現」
的潛在 bug，即使 stage6 三支改成 async 的路由本身跟 `GET /api/products`
（維持 sync）並沒有直接關係——`check_same_thread=False` 是套用在
`get_connection()` 這個共用函式上，所有端點（不管 sync 還是 async）都受益。

### 2.3 stage6 實測結果（同樣的壓測腳本、同樣的參數）

```
Type,Name,Request Count,Failure Count,...,Requests/s,Failures/s,...
POST,/api/auth/login,13,0,...
POST,/api/auth/register,13,0,...
POST,/api/cart/items,368,0,...
POST,/api/orders,242,0,...
POST,/api/payments/mock,242,0,...
GET,/api/products,1042,0,...
GET,/api/products/[id],652,0,...
,Aggregated,2572,0,...,43.43,0.0,...
```

**2572 個請求，0 個失敗（0.00%）**。而且因為 register/login 不再失敗，
購買流程能夠一路走到 `/api/orders`／`/api/payments/mock`，這兩支端點在
stage5 完全沒有被測到，stage6 各自被呼叫了 242 次、全部成功。

**這個發現對教學的意義**：單元測試／整合測試（本課程 pytest 用
`TestClient` 循序執行）測不出這種「只有在真實併發下才會出現」的 bug；
壓力測試除了測「快不快」，更重要的價值是**測「在真實併發流量下，程式碼裡
潛藏的並發假設有沒有被打破」**——這正是 stage6 spec 一開始要求做壓力測試
的原因，這次意外印證了。

## 3. RPS／延遲對照表（兩輪完整聚合數字）

| 指標 | stage5（baseline） | stage6（優化後） | 差異 |
|---|---|---|---|
| 總請求數 | 2118 | 2572 | +21.4%（優化後同樣 60 秒內處理更多請求） |
| 總體 RPS | 35.75 | 43.43 | +21.5% |
| 錯誤率 | 20.63%（437/2118，見第 2 節） | 0.00%（0/2572） | 見第 2 節根因分析 |
| p50 延遲（聚合） | 4 ms | 4 ms | 持平 |
| p95 延遲（聚合） | 15 ms | 10 ms | -33% |
| p99 延遲（聚合） | 30 ms | 240 ms* | 見下方誠實說明 |

\* **p99 240ms 誠實說明**：這個數字不是效能變差，是統計上的干擾——
`POST /api/auth/register`（bcrypt 密碼雜湊，刻意的計算成本，安全設計，
兩輪測試都落在 250-270ms 這個量級，見下表）跟其他毫秒級的端點混在同一份
「聚合」統計裡，只要 register/login 這類請求佔比夠高，就會把聚合的 p99
拉到跟它們的延遲同一個量級。stage6 因為 register/login 100% 成功（stage5
大多數失敗、根本沒真正跑完整段流程），聚合統計裡「慢請求」的樣本反而變多，
造成聚合 p99 表面上「變差」——這是解讀壓測報告時常見的陷阱，**看聚合數字
before 誤判，一定要拆到端點層級才知道真相**，見下方逐端點表格。

## 4. 逐端點對照（不受 bcrypt 延遲干擾，只看真正的商品/訂單端點）

### `GET /api/products`（受 TTL 快取＋新索引影響最直接的端點）

| 指標 | stage5 | stage6 | 差異 |
|---|---|---|---|
| 請求數 | 1003 | 1042 | — |
| 失敗數 | 228（22.73%） | 0 | 見第 2 節 |
| RPS | 16.93 | 17.59 | +3.9% |
| p50 | 4 ms | 4 ms | 持平 |
| p95 | 16 ms | 8 ms | **-50%** |
| p99 | 25 ms | 16 ms | -36% |

### `GET /api/products/{id}`

| 指標 | stage5 | stage6 | 差異 |
|---|---|---|---|
| 請求數 | 706 | 652 | — |
| 失敗數 | 162（22.94%） | 0 | 見第 2 節 |
| RPS | 11.92 | 11.01 | -7.6%（見下方說明） |
| p50 | 4 ms | 4 ms | 持平 |
| p95 | 14 ms | 9 ms | -36% |
| p99 | 23 ms | 13 ms | -43% |

（這支端點的 RPS 看起來「變低」，不是變慢——是因為 stage6 因為
register/login/cart/orders 都不再失敗，整體流量被更均勻地分配到更多種
端點上（包含新出現的 `/api/orders`、`/api/payments/mock`），`/api/products/{id}`
分到的請求數比例自然下降，不是這支端點本身變慢，p50/p95/p99 都同步下降
才是它變快的證據。）

### `POST /api/cart/items`

| 指標 | stage5 | stage6 | 差異 |
|---|---|---|---|
| 請求數 | 383 | 368 | — |
| 失敗數 | 29（7.57%） | 0 | 見第 2 節 |
| p95 | 11 ms | 11 ms | 持平（這支端點沒有被本階段任何優化項目直接影響） |

### `POST /api/orders` ／ `POST /api/payments/mock`（stage5 幾乎測不到）

stage5 這兩支端點在整場測試裡合計被成功呼叫 **0 次**（第 2 節已說明原因）。
stage6 分別被呼叫 **242 次，0 個失敗**，p95 都在 7-8ms（見
`loadtest/` 產出的 CSV 原始檔）。這組數字本身就是「stage5 vs stage6」
最直觀的對比——不是「快多少」，是「stage5 在這個壓力等級下，購買流程幾乎
無法完整走完」。

## 5. 瓶頸分析（哪支端點最慢、為什麼、對應哪項優化）

| 端點 | 瓶頸 | 對應優化 | 證據 |
|---|---|---|---|
| `GET /api/products`（含分類篩選） | 優化前：全表掃描（無索引）＋每次都重新查 SQLite | `idx_products_category_active` 複合索引＋30 秒 TTL 快取 | `EXPLAIN QUERY PLAN` 從 `SCAN products` 變成 `SEARCH ... USING INDEX`（見 [`DATABASE.md`](DATABASE.md)）；p95 從 16ms 降到 8ms |
| `GET /api/admin/orders`（後台訂單列表） | 優化前：N+1 查詢，1+N 次 SQL（N=訂單筆數） | 改用單次 `LEFT JOIN` | 實測查詢次數從 8 次（7 筆訂單）降到 1 次，見 [`DATABASE.md`](DATABASE.md)「N+1 查詢修復」一節（這支端點本身沒有放進本次壓測場景，因為壓測場景鎖定「顧客流量」，後台端點的查詢次數對照走的是獨立的自動化測試，不是這份壓測報告） |
| 全站（幾乎所有端點） | 高併發下 SQLite 連線的跨執行緒存取被拒絕，直接 500 | `check_same_thread=False` | 見第 2 節，這是本次壓測最大的發現 |
| JSON 回應大小 | 沒有壓縮，傳輸位元組數較大 | `GZipMiddleware` | 實測 `GET /api/products` 回應帶 `content-encoding: gzip`，見 [`ARCHITECTURE.md`](ARCHITECTURE.md) 第 9 節（本項對本機 localhost 測試的延遲影響可忽略——GZip 主要在真實網路延遲/頻寬受限時才看得出差異，本機測試環境沒有這個限制，這裡誠實聲明「有做、有驗證存在，但本次壓測數字看不出它單獨的貢獻」） |

## 6. 誠實聲明總結

1. 本報告最大的發現（stage5 的 SQLite 跨執行緒 500 錯誤）不在原本規劃的
   優化清單裡，是跑壓測過程中意外發現的真實 bug，根因與修法都有實測證據
   （伺服器端 traceback、前後對照的錯誤率），不是憑空猜測。
2. 本機壓測數字受機器效能影響，`43.43 RPS` 這種數字不能直接當作「正式環境
   能扛多少人」的保證，重點是兩輪測試之間的**方法一致、相對差異**。
3. 聚合 p99 數字有 bcrypt 密碼雜湊延遲的干擾，解讀時要拆到端點層級（第 4
   節），不能只看聚合數字就下結論——這件事本身也是這份報告想教的方法論。
4. GZip 壓縮的存在與正確運作已驗證（見 [`ARCHITECTURE.md`](ARCHITECTURE.md)），
   但在本機 localhost（零網路延遲、零頻寬限制）測試環境下，壓測數字看不出
   它對延遲的直接貢獻——這是誠實的「有實作、有驗證，但這份報告的測試方法
   量不出它的效果」聲明，不是宣稱「GZip 讓 RPS 提升了 X%」這種沒有證據支持
   的說法。
5. 商品型錄庫存有限（master spec 規定不得增刪改），高併發購買流量下商品會
   在測試進行到一定時間後售罄，之後的加車請求會收到 409（正確的防呆行為，
   不是錯誤）——本報告把 409/400 這類「業務邏輯正常但這次操作不成立」的
   回應視為非系統錯誤（只有 5xx 或連線層級失敗才算「錯誤」），完整理由見
   `loadtest/locustfile.py` 開頭的誠實聲明。

## 7. 想自己重跑這份測試？

見 [`../loadtest/README.md`](../loadtest/README.md) 的完整步驟。
