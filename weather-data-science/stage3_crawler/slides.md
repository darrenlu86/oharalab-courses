## stage3_crawler — 爬取沙盒氣象站 → SQLite

AI-9 資料收集與資料庫 ｜ B 級 / 3 點

---

## 五支關卡爬蟲

1. `crawl_stations.py` —— 靜態 HTML 解析
2. `crawl_records.py` —— 翻頁（動態欄位）
3. `crawl_comments.py` —— 翻頁（固定欄位）
4. `crawl_announcements.py` —— 列表 → 詳情兩層
5. `crawl_latest_api.py` —— 直接打 JSON API

共用：`http_client.PoliteSession`（UA / 延遲 / 重試）+ `db.py`（upsert）

---

## 兩種冪等寫法

| 表 | 寫法 | 衝突時 |
|---|---|---|
| daily_weather | `ON CONFLICT DO UPDATE` | 覆寫新值 |
| comments/announcements/stations | `INSERT OR IGNORE` | 保留原值 |

---

## 實測：冪等性驗證

連跑兩次 `run_all.py`：

```
第一次爬取後：{'daily_weather': 12054, 'comments': 2400, 'announcements': 30}
第二次爬取後：{'daily_weather': 12054, 'comments': 2400, 'announcements': 30}
```

row 數完全相同 —— 不是理論宣稱，是實測結果

---

## 踩坑紀錄

`/api/latest` JSON 回應的數字其實是字串（`"25.4"`）

第一版靠 SQLite 型別親和性「剛好能動」，是隱性魔法不是正確程式碼

已修正為明確 `float()`/`int()` 轉型

---

## 耗時

單次 `run_all.py` ≈ 81 秒（300+ 次請求 × 0.2 秒禮貌延遲）

延遲是刻意設計，不是效能瑕疵——真實爬蟲不能省這一步

---

## 誠實結論

- 沙盒站與真實網站落差很大：無 CAPTCHA、無 rate limit、robots.txt 全開放
- 本課程教「爬蟲的基本模式」，不教「怎麼繞過反爬蟲機制」
- 測試（20 passed）全部用固定 HTML/JSON fixture，不連沙盒站
