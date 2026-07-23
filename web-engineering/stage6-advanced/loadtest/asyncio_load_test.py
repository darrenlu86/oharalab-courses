"""
壓力測試 fallback 腳本——不依賴 locust，純用 asyncio + httpx 自己寫的最小可用
壓測工具。stage6 spec 要求「優先 locust，若裝不起來 fallback 自寫腳本」；
本專案實測環境（Python 3.13.11）locust 其實裝得起來（見 requirements.txt 的
說明），這支腳本主要是教學備援與「不依賴額外套件也能壓測」的示範，兩支腳本
場景刻意設計成一致（匿名逛商品 3 : 登入完整下單流 1 的比例），方便對照。

用法：

```bash
# 對 stage6（優化後）打 50 併發、跑 60 秒：
python asyncio_load_test.py --host http://localhost:8006 --concurrency 50 --duration 60

# 對 stage5（優化前 baseline）打同一組參數：
python asyncio_load_test.py --host http://localhost:8005 --concurrency 50 --duration 60
```

輸出：總請求數、RPS（requests per second）、p50／p95 延遲（毫秒）、錯誤率，
一次印出，不用另外處理 CSV。

**跟 locust 的差異（誠實聲明）**：locust 有網頁介面、即時圖表、每個端點各自的
統計、更完整的分散式壓測能力；這支腳本只給「一個混合場景的整體數字」，沒有
逐端點細分，教學規模夠用，正式壓測建議用 locust 或更專業的工具（k6、Gatling）。
"""

import argparse
import asyncio
import random
import time
import uuid

import httpx

SUCCESS_CARD = "4242424242424242"
PRODUCT_IDS = list(range(1, 13))
# 排除 id=6（種子庫存 3 件）與 id=11（種子庫存 0 件）——理由跟 locustfile.py
# 的 `PURCHASE_SAFE_PRODUCT_IDS` 完全一樣，這兩個 id 是刻意設計的低庫存/缺貨
# 教學展示商品，不適合當壓測下單目標，見該檔開頭的誠實聲明。
PURCHASE_SAFE_PRODUCT_IDS = [pid for pid in PRODUCT_IDS if pid not in (6, 11)]
CATEGORIES = ["beans", "drip", "gear", "cups", "gift", None]


class Metrics:
    def __init__(self):
        self.latencies_ms: list[float] = []
        self.errors = 0
        self.lock = asyncio.Lock()

    async def record(self, latency_ms: float, ok: bool) -> None:
        async with self.lock:
            self.latencies_ms.append(latency_ms)
            if not ok:
                self.errors += 1

    def summary(self, duration_s: float) -> dict:
        total = len(self.latencies_ms)
        if total == 0:
            return {"total": 0, "rps": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "error_rate": 0.0}
        sorted_latencies = sorted(self.latencies_ms)
        p50 = sorted_latencies[int(total * 0.50) - 1]
        p95 = sorted_latencies[min(int(total * 0.95), total - 1)]
        return {
            "total": total,
            "rps": total / duration_s,
            "p50_ms": p50,
            "p95_ms": p95,
            "error_rate": self.errors / total,
        }


async def _timed_request(client: httpx.AsyncClient, metrics: Metrics, method: str, url: str, **kwargs) -> httpx.Response | None:
    start = time.perf_counter()
    try:
        resp = await client.request(method, url, **kwargs)
        elapsed_ms = (time.perf_counter() - start) * 1000
        ok = resp.status_code < 500  # 4xx 視為「業務邏輯正常運作但這次請求不成立」，不算系統錯誤
        await metrics.record(elapsed_ms, ok)
        return resp
    except httpx.HTTPError:
        elapsed_ms = (time.perf_counter() - start) * 1000
        await metrics.record(elapsed_ms, False)
        return None


async def _anonymous_browsing_iteration(client: httpx.AsyncClient, metrics: Metrics) -> None:
    category = random.choice(CATEGORIES)
    params = {"category": category} if category else {}
    await _timed_request(client, metrics, "GET", "/api/products", params=params)
    product_id = random.choice(PRODUCT_IDS)
    await _timed_request(client, metrics, "GET", f"/api/products/{product_id}")


async def _purchasing_worker(client: httpx.AsyncClient, metrics: Metrics, deadline: float) -> None:
    email = f"loadtest-{uuid.uuid4().hex[:12]}@example.com"
    await _timed_request(
        client, metrics, "POST", "/api/auth/register",
        json={"email": email, "password": "LoadTest12345", "name": "壓測用戶"},
    )
    login_resp = await _timed_request(
        client, metrics, "POST", "/api/auth/login",
        json={"email": email, "password": "LoadTest12345"},
    )
    if login_resp is None or login_resp.status_code != 200:
        return
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    while time.monotonic() < deadline:
        product_id = random.choice(PURCHASE_SAFE_PRODUCT_IDS)
        await _timed_request(
            client, metrics, "POST", "/api/cart/items",
            json={"product_id": product_id, "quantity": 1}, headers=headers,
        )
        order_resp = await _timed_request(
            client, metrics, "POST", "/api/orders",
            json={"recipient_name": "壓測用戶", "recipient_address": "台北市信義區某路 1 號"},
            headers=headers,
        )
        if order_resp is None or order_resp.status_code != 201:
            continue
        order_id = order_resp.json()["id"]
        await _timed_request(
            client, metrics, "POST", "/api/payments/mock",
            json={"order_id": order_id, "card_number": SUCCESS_CARD, "card_holder": "壓測用戶"},
            headers=headers,
        )


async def _browsing_worker(client: httpx.AsyncClient, metrics: Metrics, deadline: float) -> None:
    while time.monotonic() < deadline:
        await _anonymous_browsing_iteration(client, metrics)


async def run(host: str, concurrency: int, duration: int) -> dict:
    metrics = Metrics()
    deadline = time.monotonic() + duration

    # 3:1 的瀏覽:購買比例跟 locustfile.py 的 weight 設計一致，理由見該檔說明。
    browsing_workers = max(1, round(concurrency * 0.75))
    purchasing_workers = max(1, concurrency - browsing_workers)

    async with httpx.AsyncClient(base_url=host, timeout=30.0) as client:
        tasks = [asyncio.create_task(_browsing_worker(client, metrics, deadline)) for _ in range(browsing_workers)]
        tasks += [
            asyncio.create_task(_purchasing_worker(client, metrics, deadline)) for _ in range(purchasing_workers)
        ]
        await asyncio.gather(*tasks)

    return metrics.summary(duration)


def main() -> None:
    parser = argparse.ArgumentParser(description="BrewGo 壓力測試 fallback 腳本（asyncio + httpx）")
    parser.add_argument("--host", required=True, help="例如 http://localhost:8006")
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--duration", type=int, default=60, help="秒")
    args = parser.parse_args()

    print(f"開始壓測：host={args.host} concurrency={args.concurrency} duration={args.duration}s")
    result = asyncio.run(run(args.host, args.concurrency, args.duration))

    print()
    print(f"總請求數：{result['total']}")
    print(f"RPS：{result['rps']:.2f}")
    print(f"p50 延遲：{result['p50_ms']:.1f} ms")
    print(f"p95 延遲：{result['p95_ms']:.1f} ms")
    print(f"錯誤率：{result['error_rate'] * 100:.2f}%")


if __name__ == "__main__":
    main()
