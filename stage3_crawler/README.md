# stage3_crawler — 爬取沙盒氣象站 → SQLite（AI-9）

## 這一關在教什麼

怎麼把一個網站的資料，用程式自動化地搬進自己的資料庫：解析靜態 HTML、
處理翻頁、處理「列表→詳情」兩層結構、直接呼叫 JSON API，以及最容易被
忽略但最重要的一件事——**爬蟲倫理**（表明身分、遵守 robots.txt、禮貌延遲、
讓重跑不會製造重複資料）。

## 你會學到

- BeautifulSoup 解析 HTML 表格、清單、`<article>` 內文的基本用法。
- 翻頁爬蟲的兩種寫法（`/records`：欄位動態、`/comments`：欄位固定），
  以及怎麼判斷「爬完了該停」（讀頁面本身印出的總頁數，不是土法煉鋼爬到
  空表格才發現爬過頭）。
- 「列表→詳情」兩層爬取模式（`/announcements` → `/announcements/{id}`）。
- SQLite 的 `UNIQUE` 約束 + `INSERT OR IGNORE` / `ON CONFLICT DO UPDATE`
  兩種冪等寫法的差異與適用時機。
- 為什麼要有 `robots.txt` 檢查、禮貌延遲、表明身分的 User-Agent——即使
  練習對象是自己人架的沙盒站，也要練成習慣。

## 完成後產出對照表

| 專案卡要求 | 本階段交付 |
|---|---|
| 可重複執行的爬蟲程式 | `crawler/crawl_*.py`（五支）+ `run_all.py`（一鍵跑全部,idempotent 已實測） |
| 資料集產出（CSV 或資料庫檔） | `data/weather_course.db`（SQLite,gitignored）+ `export_csv.py` 匯出 `output/*.csv`（gitignored） |
| 含系統架構與關鍵技術說明的成果報告 | `report.md`（含 mermaid 架構圖與實測 row 數） |

## 前置需求

- repo 根 `venv/` 已安裝 `requirements.txt`（含 `beautifulsoup4`）。
- `data/raw/*.csv`、`data/synthetic/*.csv` 已存在（沙盒站要讀這些檔案）。
- **需要兩個終端機**：一個跑沙盒站，一個跑爬蟲。

## 快速開始

**終端機 1**——啟動沙盒站：

```
venv/bin/python -m uvicorn sandbox_site.app:app --port 8310
```

等到看見 `Uvicorn running on http://127.0.0.1:8310` 再進行下一步。

**終端機 2**——一鍵跑全部爬蟲：

```
venv/bin/python -m stage3_crawler.run_all
```

預期輸出結構（實測數字，完整輸出見 `report.md`）：

```
沙盒站 http://127.0.0.1:8310 連線正常，UA：weather-course-crawler/1.0 (...)
robots.txt 檢查結果：{'/stations': True, '/records': True, ...}
爬取前 row 數：{'stations': 3, 'daily_weather': 0, ...}
[1/5] stations：3 筆
[2/5] daily_weather（HTML 翻頁）：{'taipei': 4018, 'taichung': 4018, 'kaohsiung': 4018}
[3/5] comments：2400 筆
[4/5] announcements：30 則
[5/5] daily_weather（JSON API，近 30 天）：{'taipei': 30, 'taichung': 30, 'kaohsiung': 30}
爬取後 row 數：{'stations': 3, 'daily_weather': 12054, ...}
```

整個流程約 80 秒（大部分時間花在禮貌延遲上，不是網路慢——沙盒站在本機,
延遲是程式刻意加的)。

匯出成 CSV（gitignored，方便你另外用 Excel/pandas 檢視）：

```
venv/bin/python -m stage3_crawler.export_csv
```

## 逐步教學

### 第一步：看懂 `http_client.py` 的禮貌設計

`PoliteSession` 每次 GET 都帶固定的 User-Agent（表明自己是誰、留聯絡
方式）,成功後 sleep 一段延遲（預設 0.2 秒）,失敗會重試最多兩次。
`check_robots_allowed()` 在正式爬取前檢查 robots.txt——`run_all.py`
第一件事就是做這個檢查,如果 robots.txt 不允許就直接中止,不會硬爬。

### 第二步：五支關卡爬蟲，各自的解析邏輯

依序打開 `crawler/crawl_stations.py`（最簡單：一個請求一張表）、
`crawl_records.py`（翻頁：讀 caption 裡的「第 X 頁 / 共 Y 頁」文字決定
迴圈次數）、`crawl_comments.py`（翻頁的第二個例子，欄位固定，跟 records
的「欄位動態讀 thead」不同，兩種寫法都要認得）、`crawl_announcements.py`
（列表→詳情：先解析 `<ul class="plain-list">` 拿連結，再逐一進入詳情頁）、
`crawl_latest_api.py`（不用 BeautifulSoup，直接 `resp.json()`)。

每支模組都把「解析函式」（`parse_*`，吃 HTML/JSON 字串，不連網路）跟
「爬取函式」（`crawl`/`crawl_city`，真的發請求)分開——這是為了讓
`tests/test_stage3_crawler.py` 可以只測解析邏輯,用 `tests/fixtures/
stage3_crawler/` 裡的固定樣本,不需要沙盒站在跑。

### 第三步：兩種冪等寫法的差異

打開 `crawler/db.py`。`upsert_daily_weather` 用
`INSERT ... ON CONFLICT(city, date) DO UPDATE`——同一天的資料重複爬,
新值會覆寫舊值（適合「未來可能被來源修正」的資料)。`upsert_comment`/
`upsert_announcement`/`upsert_station` 用 `INSERT OR IGNORE`——衝突時
保留原本的值,不覆寫（適合「這筆資料本質上不會變」的情境)。兩種都能達成
「重跑不會製造重複列」,差別在「衝突時要不要更新」,值得你動手驗證
（`run_all.py` 連跑兩次,比對前後 row 數——這件事本課程已經實測過,見
`report.md`)。

### 第四步：親手體驗爬蟲的錯誤處理

把終端機 1 的沙盒站按 Ctrl+C 關掉,再跑一次 `run_all.py`——你會看到程式
印出「連不到沙盒站」的說明並中止（exit code 1),而不是丟一堆連線錯誤的
例外堆疊。這是 `run_all.py` 一開始就檢查沙盒站是否可連線的設計。

## 為什麼這樣設計

**為什麼 `crawl_records.py` 跟 `crawl_latest_api.py` 都寫進同一張
`daily_weather` 表？** 因為它們本質上是同一份資料的兩種取得管道
（HTML 表格 vs JSON API），教學重點是「同一份底層資料,介面可以不同,
但落地的資料模型應該一致」。`UNIQUE(city, date)` 讓兩條路徑不會打架——
先跑 HTML 翻頁把 11 年資料全部寫進去,再跑 JSON API 補近 30 天,後者只是
把已經存在的資料「重新確認一次」（`ON CONFLICT DO UPDATE`，值不變的話
等於沒事發生)。

**為什麼 `run_all.py` 要先檢查沙盒站連線與 robots.txt，而不是直接開始
爬？** 因為這是任何正式爬蟲上線前都該做的兩件事——本課程刻意把它們做成
`run_all.py` 的前兩步而不是事後才想到,養成「先檢查再動手」的順序感。

## 注意（常見錯誤 / 教學提醒）

- **忘記先啟動沙盒站**：`run_all.py` 會印出清楚的錯誤訊息與啟動指令,
  不會卡住等待或丟一堆連線錯誤堆疊。
- **沙盒站 vs 真實網站的落差**：沙盒站的 robots.txt 完全開放
  （`Allow: /`）、沒有 CAPTCHA、沒有 rate limit、沒有反爬蟲偵測——這些
  都是真實網站常見的障礙,本課程刻意不模擬,因為教學重點是「爬蟲的基本
  模式」而不是「怎麼繞過反爬蟲機制」（後者涉及灰色地帶,不在本課程範圍
  內)。爬真實網站前,務必先讀對方的服務條款,robots.txt 只是最低限度的
  禮儀,不是法律授權。
- **禮貌延遲讓整個流程變慢**：`run_all.py` 跑一次約 80 秒,大部分是
  `PoliteSession` 的 0.2 秒延遲乘上超過 300 次請求（81 頁 records × 3
  城市 + 48 頁 comments + 31 次 announcements 列表/詳情 + 3 次 latest
  API）累積出來的,這是刻意的,不要為了「跑快一點」把延遲設成 0——真實
  爬蟲這樣做會被對方封鎖 IP。

## 驗收 checklist

- [x] `venv/bin/python -m pytest tests/test_stage3_crawler.py -v` 全綠。
- [x] 沙盒站啟動後,`run_all.py` 實際執行成功,row 數與預期相符
      （見 `report.md` 實測輸出)。
- [x] 連跑兩次 `run_all.py`,確認 row 數不變（冪等性實測)。
- [x] `export_csv.py` 產出四份 CSV,列數與資料庫一致。
- [x] 關掉沙盒站後跑 `run_all.py`,確認優雅失敗（清楚錯誤訊息,不是
      未捕捉例外堆疊)。

## 延伸挑戰

1. 幫 `crawl_records.py` 加上「續傳」能力：如果程式中途被中斷,重跑時
   跳過已經爬過的頁面（提示：可以先查 `daily_weather` 表裡該城市已有
   幾筆,反推該從第幾頁開始)。
2. 把 `PoliteSession` 的延遲改成隨機範圍（例如 0.1~0.3 秒之間隨機),
   體會「固定延遲」與「隨機延遲」在真實網站眼中的差異。
3. 幫 `run_all.py` 加上 `--only` 參數,只跑指定的關卡（例如
   `--only comments`），不用每次都跑全部五支。
