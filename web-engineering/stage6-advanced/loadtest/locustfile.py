"""
壓力測試腳本（locust）——混合場景：匿名逛商品 ＋ 登入用戶完整下單流。

用法（在這個資料夾底下執行，需要先 `pip install -r ../backend/requirements.txt`，
locust 在白名單內、已包含在需求檔案裡）：

```bash
# 對 stage6（優化後）打 50 併發、跑 60 秒、headless（不開網頁介面）：
locust -f locustfile.py --host http://localhost:8006 \
    --users 50 --spawn-rate 10 --run-time 60s --headless --csv stage6_result

# 對 stage5（優化前 baseline）打同一組參數，只換 host：
locust -f locustfile.py --host http://localhost:8005 \
    --users 50 --spawn-rate 10 --run-time 60s --headless --csv stage5_result
```

跑完會產生 `<prefix>_stats.csv`（每支端點的 RPS／平均延遲／百分位數）與
`<prefix>_stats_history.csv`（時間序列），docs/PERFORMANCE_REPORT.md 的對照表
就是從這兩個檔案讀出來的實跑數字整理而成，完整步驟見 loadtest/README.md。

## 場景設計（對照 stage6 spec 的要求）

- `AnonymousBrowsingUser`（weight 3）：只打不需要登入的商品瀏覽端點——
  `GET /api/products`（含分類篩選）與 `GET /api/products/{id}`，模擬「大部分
  訪客只是逛逛」的真實流量比例。
- `PurchasingCustomerUser`（weight 1）：模擬登入 → 加購物車 → 建立訂單 → 付款
  的完整流程，每個模擬使用者一開始（`on_start`）先各自註冊一個獨一無二的帳號
  （用 locust 內建的 `self.environment.runner` 搭配隨機字串產生 email，避免
  併發跑的時候大家撞同一個 email 收到 409），再重複跑「加車→建單→付款」這個
  循環當作任務。

weight 3:1 是刻意營造「瀏覽遠多於購買」的真實電商流量特徵，不是隨便選的數字；
如果你想測試「結帳尖峰」這種特殊情境，可以自己調整 weight 或另外寫一個腳本。

## 誠實聲明——商品型錄庫存有限，高併發下單流一定會出現大量 409

master 型錄（見 ../docs/DATABASE.md 附錄）規定商品庫存是固定值，本課程不准
增刪改，商品 id=1 到 12 的庫存總和是個位數到幾十件不等的小數字。50 併發同時
狂發「加車→建單→付款」，庫存在幾秒內就會被打光，之後每一次加車請求都會收到
`409`（庫存不足，這是 app/routers/cart.py 的正確防呆行為，不是 bug），連帶
讓後續建單收到 `400`（購物車是空的）。

如果照 locust 預設行為（任何非 2xx 都算「失敗」），這份壓測報告的「錯誤率」
會被「商品正確地防止超賣」這個業務邏輯洗到很高，完全掩蓋掉我們真正想測的
「系統在高併發下有沒有變慢／有沒有真的當機（5xx／連線失敗）」這個問題。
所以這裡用 `catch_response=True` 手動判定：**只有 5xx 或連線層級的錯誤才算
「失敗」**，4xx（庫存不足、驗證錯誤這類「請求本身有問題」）一律標記成功——
這跟 loadtest/asyncio_load_test.py 的 `_timed_request()`（`status_code < 500`
才算 ok）是同一套判斷標準，兩支腳本的「錯誤率」定義一致，互相可以比較。
"""

import random
import uuid

from locust import HttpUser, task, between

SUCCESS_CARD = "4242424242424242"
PRODUCT_IDS = list(range(1, 13))
# 排除 id=6（種子庫存只有 3 件）與 id=11（種子庫存 0 件，master 型錄刻意設計的
# 「補貨中」示範商品）——這兩個 id 的庫存本來就設計成教學展示用，不適合拿來
# 當壓測的下單目標，會在測試一開始沒幾秒就把庫存榨乾，讓後續整段測試時間
# 都在測「商品已售罄」這個情境而不是「系統扛不扛得住流量」。
PURCHASE_SAFE_PRODUCT_IDS = [pid for pid in PRODUCT_IDS if pid not in (6, 11)]
CATEGORIES = ["beans", "drip", "gear", "cups", "gift"]


def _mark_success_unless_server_error(response) -> None:
    """4xx 視為「業務邏輯正常運作、這次操作不成立」，只有 5xx 才算系統錯誤——
    完整理由見檔案開頭的誠實聲明。"""
    if response.status_code >= 500:
        response.failure(f"伺服器錯誤：HTTP {response.status_code}")
    else:
        response.success()


class AnonymousBrowsingUser(HttpUser):
    weight = 3
    wait_time = between(0.5, 2.0)

    @task(3)
    def list_products(self):
        category = random.choice(CATEGORIES + [None])
        params = {"category": category} if category else {}
        with self.client.get(
            "/api/products", params=params, name="/api/products", catch_response=True
        ) as response:
            _mark_success_unless_server_error(response)

    @task(2)
    def get_product_detail(self):
        product_id = random.choice(PRODUCT_IDS)
        with self.client.get(
            f"/api/products/{product_id}", name="/api/products/[id]", catch_response=True
        ) as response:
            _mark_success_unless_server_error(response)


class PurchasingCustomerUser(HttpUser):
    weight = 1
    wait_time = between(1.0, 3.0)

    def on_start(self):
        email = f"loadtest-{uuid.uuid4().hex[:12]}@example.com"
        with self.client.post(
            "/api/auth/register",
            json={"email": email, "password": "LoadTest12345", "name": "壓測用戶"},
            name="/api/auth/register",
            catch_response=True,
        ) as response:
            _mark_success_unless_server_error(response)

        with self.client.post(
            "/api/auth/login",
            json={"email": email, "password": "LoadTest12345"},
            name="/api/auth/login",
            catch_response=True,
        ) as response:
            _mark_success_unless_server_error(response)
            self.token = response.json().get("access_token", "") if response.status_code == 200 else ""
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task
    def full_checkout_flow(self):
        product_id = random.choice(PURCHASE_SAFE_PRODUCT_IDS)
        with self.client.post(
            "/api/cart/items",
            json={"product_id": product_id, "quantity": 1},
            headers=self.headers,
            name="/api/cart/items",
            catch_response=True,
        ) as response:
            _mark_success_unless_server_error(response)
            if response.status_code != 200:
                return  # 庫存不足或其他併發衝突，這次流程提早結束，不硬要建單

        with self.client.post(
            "/api/orders",
            json={"recipient_name": "壓測用戶", "recipient_address": "台北市信義區某路 1 號"},
            headers=self.headers,
            name="/api/orders",
            catch_response=True,
        ) as order_response:
            _mark_success_unless_server_error(order_response)
            if order_response.status_code != 201:
                return
            order_id = order_response.json().get("id")

        with self.client.post(
            "/api/payments/mock",
            json={"order_id": order_id, "card_number": SUCCESS_CARD, "card_holder": "壓測用戶"},
            headers=self.headers,
            name="/api/payments/mock",
            catch_response=True,
        ) as payment_response:
            _mark_success_unless_server_error(payment_response)
