# stage3_crawler 成果報告

## 系統架構

```mermaid
flowchart LR
    subgraph sandbox["sandbox_site (:8310)"]
        S1["/stations"]
        S2["/records?city=&page="]
        S3["/comments?page="]
        S4["/announcements, /announcements/{id}"]
        S5["/api/latest?city="]
    end

    subgraph crawler["stage3_crawler/crawler/"]
        HC["http_client.PoliteSession<br/>(UA, 禮貌延遲, 逾時重試)"]
        C1["crawl_stations.py"]
        C2["crawl_records.py<br/>(翻頁)"]
        C3["crawl_comments.py<br/>(翻頁)"]
        C4["crawl_announcements.py<br/>(列表→詳情)"]
        C5["crawl_latest_api.py<br/>(JSON)"]
        DB["db.py<br/>(upsert)"]
    end

    SQLITE[("data/weather_course.db")]

    S1 --> C1
    S2 --> C2
    S3 --> C3
    S4 --> C4
    S5 --> C5
    HC -.被全部 crawl_*.py 共用.-> C1
    HC -.-> C2
    HC -.-> C3
    HC -.-> C4
    HC -.-> C5
    C1 --> DB --> SQLITE
    C2 --> DB
    C3 --> DB
    C4 --> DB
    C5 --> DB
```

`run_all.py` 依序執行：連線檢查 → robots.txt 檢查 → 五支爬蟲 → 前後 row
數統計。`export_csv.py` 另外把 SQLite 四張表匯出成 CSV（gitignored）。

## 關鍵技術說明

1. **解析與爬取分離**：每支 `crawl_*.py` 都把「純解析函式」
   （`parse_*`，吃 HTML/JSON 字串）跟「爬取函式」（`crawl`/`crawl_city`，
   真的發請求）分開。這讓 `tests/test_stage3_crawler.py` 可以只測解析
   邏輯，用 `tests/fixtures/stage3_crawler/` 的固定樣本，不需要沙盒站在
   跑（SPEC §7 的硬性要求）。
2. **兩種冪等寫法**：`daily_weather` 用 `INSERT ... ON CONFLICT(city,
   date) DO UPDATE`（衝突時覆寫），`comments`/`announcements`/`stations`
   用 `INSERT OR IGNORE`（衝突時保留原值）。兩者都能達成「重跑不製造
   重複列」，差別只在「衝突時要不要更新」——實測見下方。
3. **翻頁終止條件**：不是「爬到空表格才發現爬過頭」，而是直接解析頁面
   本身印出的「第 X 頁 / 共 Y 頁」文字，一次算出總頁數再迴圈到底。
4. **同一張表、兩條資料入口**：`crawl_records.py`（HTML 翻頁）與
   `crawl_latest_api.py`（JSON API）都寫進 `daily_weather`，靠
   `UNIQUE(city, date)` 互不打架——示範「同一份底層資料可以有多種取得
   管道」。
5. **禮貌延遲的真實代價**：`PoliteSession` 預設每次請求後 sleep 0.2
   秒，`run_all.py` 一次要發 300+ 次請求（81 頁 records × 3 城市 = 243、
   comments 48 頁、announcements 1+30 = 31、latest API 3 次），實測總
   耗時 81~82 秒——這個數字幾乎全部來自禮貌延遲的累積，不是網路慢（沙盒
   站在本機）。

## 實測結果（2026-07-24 00:51:44 CST 起，完整輸出見下方）

### 第一次執行

```
沙盒站 http://127.0.0.1:8310 連線正常
robots.txt 檢查結果：{'/stations': True, '/records': True, '/comments': True, '/announcements': True, '/api/latest': True}
爬取前 row 數：{'stations': 3, 'daily_weather': 0, 'comments': 0, 'announcements': 0, 'predictions': 0}
[1/5] stations：3 筆
[2/5] daily_weather（HTML 翻頁）：{'taipei': 4018, 'taichung': 4018, 'kaohsiung': 4018}
[3/5] comments：2400 筆
[4/5] announcements：30 則
[5/5] daily_weather（JSON API，近 30 天）：{'taipei': 30, 'taichung': 30, 'kaohsiung': 30}
爬取後 row 數：{'stations': 3, 'daily_weather': 12054, 'comments': 2400, 'announcements': 30, 'predictions': 0}
總耗時：81.0 秒
```

### 第二次執行（冪等性驗證，緊接第一次之後立即重跑）

```
爬取前 row 數：{'stations': 3, 'daily_weather': 12054, 'comments': 2400, 'announcements': 30, 'predictions': 0}
[1/5] stations：3 筆
[2/5] daily_weather（HTML 翻頁）：{'taipei': 4018, 'taichung': 4018, 'kaohsiung': 4018}
[3/5] comments：2400 筆
[4/5] announcements：30 則
[5/5] daily_weather（JSON API，近 30 天）：{'taipei': 30, 'taichung': 30, 'kaohsiung': 30}
爬取後 row 數：{'stations': 3, 'daily_weather': 12054, 'comments': 2400, 'announcements': 30, 'predictions': 0}
總耗時：81.7 秒
```

**爬取前後 row 數完全相同（12054/2400/30/3）——冪等性得到實測驗證**，
不是理論宣稱。

### CSV 匯出結果

```
stations.csv：3 列
daily_weather.csv：12054 列
comments.csv：2400 列
announcements.csv：30 列
```

匯出後逐欄比對 `daily_weather.csv` 台北 2015-01-01 的數值，與
`data/raw/taipei.csv` 原始資料完全一致（`13.4,10.7,11.9,0.0,0.0,0.0,
18.3,47.5,57,8.91`），確認 HTML 表格解析與欄名對應（`API_TO_DB_COLUMN`）
沒有錯位。

## 測試結果

`venv/bin/python -m pytest tests/test_stage3_crawler.py -v`：**20 passed**
（2026-07-24 實測）。涵蓋：robots.txt 解析（允許/禁止兩種情境）、五支
`parse_*` 函式對真實 HTML/JSON fixture 的解析正確性（含首頁/末頁邊界）、
db.py 兩種 upsert 語意（覆寫 vs 保留)、`PoliteSession` 的重試/最終失敗
路徑。

## 踩坑紀錄（開發過程中真的抓到的 bug）

開發 `crawl_latest_api.py` 時發現：`sandbox_site` 的 `/api/latest` 端點
直接把 CSV 字串塞進 JSON（`sandbox_site/data.py` 的 `_load_weather` 沒有
轉型），所以 JSON 回應裡 `temperature_2m_max` 等欄位其實是字串 `"25.4"`
而不是數字。第一版 `parse_latest_json` 沒有處理這件事，直接把字串塞進
SQLite——實測發現**因為 SQLite 的欄位型別親和性（type affinity）會自動
把數字字串轉成 REAL/INTEGER，這樣寫「剛好能動」，但那是隱性魔法，不是
正確的程式碼**。已修正為明確轉型（`float(value)`/`int(float(value))`），
不依賴底層資料庫幫忙補洞——換成別的資料庫引擎，這種隱性轉換不一定存在。

## 誠實結論

- 冪等性是實測出來的（連跑兩次比對 row 數），不是憑 SQL 語法猜測。
- 禮貌延遲讓整個流程變慢（81+ 秒），這是刻意的教學設計，不是效能瑕疵。
- 沙盒站與真實網站的落差很大（無 CAPTCHA、無 rate limit、robots.txt
  完全開放）——本報告與 README 都明確標示這一點，不假裝這是「真實爬蟲
  環境的完整訓練」。
