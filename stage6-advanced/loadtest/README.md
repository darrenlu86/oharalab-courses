# 壓力測試——學員自己重跑的步驟

回上層：[stage6 README](../README.md)

本資料夾有兩支場景相同（匿名逛商品 3 : 登入完整下單流 1）的壓測腳本：

- `locustfile.py`：主要工具，用 [locust](https://locust.io/)，逐端點統計、
  支援網頁介面即時觀察。
- `asyncio_load_test.py`：不依賴 locust 的 fallback，純 asyncio + httpx，
  輸出一份整體摘要（RPS／p50／p95／錯誤率）。

`docs/PERFORMANCE_REPORT.md` 的對照數字是用 `locustfile.py` 產生的。

## 前置準備

需要先把要測試的那個階段的後端啟動起來（本資料夾放在 `stage6-advanced/`
底下，但可以拿去對 `stage5-platform/` 做 baseline 對照，兩邊的 API 形狀
完全相容）：

```bash
# 以 stage6 為例
cd stage6-advanced/backend
source .venv/bin/activate
python scripts/init_db.py --reset   # 確保庫存回到型錄原始數字，見下方說明
uvicorn app.main:app --port 8006
```

> **為什麼要 `--reset`**：商品型錄庫存有限（master spec 規定不得增刪改），
> 壓測會消耗庫存（下單→付款會真的扣庫存），如果不重置，第二次跑測試會因為
> 庫存已經被打光而看到失真的結果（大量 409）。`--reset` 會清空所有帳號與
> 訂單紀錄，只適合拿來測試，不要對你正在用的開發資料庫這樣做。

## 用 locust（推薦）

```bash
cd stage6-advanced/loadtest
pip install -r ../backend/requirements.txt   # locust 已經在需求清單裡

# 開網頁介面手動控制（開發時比較方便觀察）：
locust -f locustfile.py --host http://localhost:8006
# 打開 http://localhost:8089，網頁上設定併發數、spawn rate，按 Start

# headless 模式（適合寫進報告、可重現的固定參數）：
locust -f locustfile.py --host http://localhost:8006 \
    --users 50 --spawn-rate 10 --run-time 60s --headless --csv result_stage6
```

跑完會產生 `result_stage6_stats.csv`（每支端點的請求數／失敗數／RPS／
p50-p99 百分位數）與 `result_stage6_stats_history.csv`（時間序列，畫圖用）。

## 用 asyncio fallback（不依賴 locust）

```bash
cd stage6-advanced/loadtest
python asyncio_load_test.py --host http://localhost:8006 --concurrency 50 --duration 60
```

輸出範例（實際跑出來的格式，數字會依你的機器而不同）：

```
開始壓測：host=http://localhost:8006 concurrency=10 duration=15s

總請求數：11918
RPS：794.53
p50 延遲：6.6 ms
p95 延遲：36.3 ms
錯誤率：0.00%
```

## 做 stage5 vs stage6 對照

1. 分別在兩個終端機視窗啟動 stage5（port 8005）與 stage6（port 8006）的
   後端（不要同時打，兩邊都跑會互搶 CPU，數字會失真）。
2. 兩邊都先 `python scripts/init_db.py --reset`。
3. 用同一組 locust 參數分別對兩個 host 跑一輪，`--csv` 存到不同檔名（例如
   `stage5_result` / `stage6_result`），方便事後對照。
4. 對照兩份 `_stats.csv`，重點看：總 RPS、各端點的 p95、Failure Count。

## 已知限制（誠實聲明）

- 商品型錄小（12 筆，多數商品庫存在幾十件），高併發購買流量下商品很快售罄，
  售罄後的加車請求會收到 409（正確行為，不是 bug）。兩支腳本都把 4xx 視為
  「業務邏輯正常、非系統錯誤」，只有 5xx／連線失敗才算「錯誤」，完整理由見
  `locustfile.py` 開頭的說明。
- 本機壓測數字受機器效能、背景程式影響，重點是方法與相對差異，不是絕對值，
  完整聲明見 [`../docs/PERFORMANCE_REPORT.md`](../docs/PERFORMANCE_REPORT.md)。
- `asyncio_load_test.py` 只給整體摘要，沒有逐端點細分，教學規模夠用；要看
  逐端點數字請用 locust。
