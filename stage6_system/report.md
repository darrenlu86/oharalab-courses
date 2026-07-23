# stage6_system 落地效能評估與迭代優化報告

以下數字全部取自 2026-07-24 實際執行輸出（`bootstrap.py`、真實 curl 呼叫
四個頁面/API、`update_data.py`／`backfill_actuals.py`、
`model_iteration_report.py`），不是估計值。

## 系統啟動與初始化（實測）

`pipeline/bootstrap.py` 在「stage3/4/5 都已跑過」的狀態下執行：

```
stage6_system 一鍵初始化...
  - 資料庫已存在，跳過建立
  - daily_weather 已有 12054 列，跳過匯入
  - comments 已有 2400 列，跳過匯入
  - stage4 模型（降雨分類＋高溫回歸）已存在，跳過訓練
  - stage5 文字情感模型已存在，跳過訓練
初始化完成。
```

另外手動測試「模型缺失」分支（暫時搬走 `stage4_ml_structured/models/`
與 `stage5_ml_unstructured/models/` 的內容再跑一次）：

```
  - 資料庫已存在，跳過建立
  - daily_weather 已有 12054 列，跳過匯入
  - comments 已有 2400 列，跳過匯入
  - stage4 模型缺失，已重新訓練：降雨分類 accuracy=0.724，高溫回歸 MAE=1.575
  - stage5 文字情感模型缺失，已重新訓練：accuracy=0.993
```

重訓出來的指標與 `stage4_ml_structured/report.md`、
`stage5_ml_unstructured/report.md` 記錄的數字完全一致——證明
`random_state=42` 固定後，bootstrap 重建的模型是可重現的，不是碰運氣。

## 四個頁面實測（curl，真實 HTTP 200）

```
GET  /               → 200（三城市近 30 天溫度/降雨圖，資料來自 daily_weather）
GET  /predict         → 200
POST /predict          → 200（寫入 predictions 表）
GET  /sentiment       → 200（2400 筆留言：predicted 正面 1903 / 79.3%、負面 497 / 20.7%）
GET  /monitoring      → 200
```

## 完整監測迴圈實測（預測 → 補資料 → 回填 → 準確率）

1. 資料庫初始只到 2025-12-31（committed CSV 的最後一天）。第一次
   `POST /predict` 得到基準日 2025-12-31、目標日 2026-01-01 的三城市
   預測。
2. 跑 `pipeline/update_data.py`（線上模式，真的打 Open-Meteo archive
   API）：

   ```
   線上模式：查詢 Open-Meteo archive API 補最新資料...
     taipei: 補了 204 天
     taichung: 補了 204 天
     kaohsiung: 補了 204 天
   ```

   （204 天 = 2026-01-01 ~ 2026-07-23，補齊了 CSV 結尾到「昨天」之間的
   缺口。）

3. 跑 `pipeline/backfill_actuals.py`：

   ```
   回填完成：3 筆預測已補上實際值
   ```

4. `/api/monitoring` 回應：

   ```json
   {
     "total": 3, "backfilled_count": 3, "accuracy": 1.0,
     "records": [
       {"city": "taipei", "target_date": "2026-01-01", "rain_prob": 0.666, "predicted_label": 1, "actual_precip_mm": 1.9, "actual_label": 1},
       {"city": "taichung", "target_date": "2026-01-01", "rain_prob": 0.159, "predicted_label": 0, "actual_precip_mm": 0.6, "actual_label": 0},
       {"city": "kaohsiung", "target_date": "2026-01-01", "rain_prob": 0.110, "predicted_label": 0, "actual_precip_mm": 0.2, "actual_label": 0}
     ]
   }
   ```

5. 資料庫更新後重跑 `POST /predict`：基準日變成 2026-07-23（資料庫裡的
   最新資料），目標日 2026-07-24，三城市預測（台北 62%、台中 69%、
   高雄 73%，皆預測「會下雨」）——**證明修正後的 `/predict` 真的會反映
   資料庫的最新狀態**（修正前的 bug 見下方「踩坑紀錄」）。

**誠實說明樣本數限制**：上面「準確率 100%」只基於 3 筆預測，樣本數
極小，不能解讀成「模型在真實使用中有 100% 準確率」——這只是驗證「監測
迴圈的機制本身能跑完整」，要累積數週到數月的每日預測才能得到有意義的
準確率估計。

## v1（僅 lag 特徵）vs v2（+rolling/月份）迭代比較

同一份訓練/測試切分（<=2023 訓練、2024-2025 測試）、同樣的
RandomForest 超參數，唯一變數是特徵集合：

- v1（9 個特徵）：`lag_1/2/3_temp_max`、`lag_1/2/3_precip`、城市 one-hot。
- v2（14 個特徵）：v1 + `rolling_7/30_temp_max`、`rolling_7/30_precip`、
  `month`。

### 分類任務（明日降雨）

| 版本 | accuracy | precision | recall | f1 | roc_auc |
|---|---|---|---|---|---|
| v1_lag_only | 0.730 | 0.701 | 0.707 | 0.704 | 0.801 |
| v2_plus_rolling_month | 0.730 | 0.704 | 0.701 | 0.702 | 0.804 |

### 回歸任務（明日高溫）

| 版本 | MAE (°C) | RMSE (°C) |
|---|---|---|
| v1_lag_only | 1.617 | 2.219 |
| v2_plus_rolling_month | 1.576 | 2.154 |

### 誠實結論：加 rolling/月份到底有沒有幫助？

**分類任務：幾乎沒有差別**（accuracy 完全相同 0.730，roc_auc 只差
0.003）。降雨這個目標本身高度由「昨天/前天有沒有下雨」主導（見
`stage4_ml_structured/report.md` 的特徵重要度圖，`lag_1_precip`
重要度約 0.28，遠高於其他特徵），rolling 均值提供的「近期趨勢」資訊
對這個任務邊際貢獻很小。

**回歸任務：有小幅但一致的改善**（MAE 1.617→1.576，改善約 2.5%；
RMSE 2.219→2.154，改善約 2.9%）。溫度是連續變數，rolling 均值捕捉到的
「近期基準水平」（例如熱浪期間的持續偏高)確實比單看 1-3 天前的溫度更
穩定，這個小改善符合直覺。

**迭代建議**：如果之後要繼續優化，分類任務的重點不該放在加更多 lag/
rolling 衍生特徵（邊際效益已經很低），而應該考慮加入本課程資料集
沒有的外部訊號（例如鄰近測站的即時觀測、氣象局的短期預報數據)；回歸
任務則可以嘗試更長的 rolling 窗口（例如 60/90 天)驗證是否還有改善
空間，但預期邊際效益會持續遞減。

## 監測機制說明

`predictions` 表的 `UNIQUE(city, target_date, model_version)` 讓同一天
重複預測不會累積重複列（`ON CONFLICT DO UPDATE`，覆寫成最新一次的
預測）。`backfill_actuals.py` 只處理 `actual_label IS NULL` 的列，已經
回填過的不會被重複處理或覆寫（見 `tests/test_stage6_pipeline.py` 的
`test_backfill_does_not_reprocess_already_backfilled_rows`）。這個設計
讓監測歷史可以長期累積，不用擔心重跑腳本會弄亂已有的紀錄。

## 已知界線與下一步

- 監測樣本數目前只有 3 筆（本次開發過程產生的），需要長期實際使用
  （每天跑一次 `/predict` + 定期 `update_data`/`backfill_actuals`）才能
  累積出有統計意義的準確率趨勢。
- `/sentiment` 頁面對全部留言即時跑 TF-IDF+MLP（約 0.5 秒/2400 筆），
  沒有快取——教學規模可以接受，正式規模需要考慮預先計算或非同步處理。
- 本系統是本地 Demo，無雲端部署（見 SPEC §9 已知界線），`pipeline/
  update_data.py` 目前需要手動執行，沒有排程自動化。

## 踩坑紀錄

開發 `/predict` 功能時，第一版 `compute_predictions()` 直接呼叫
`stage4_ml_structured.features.build_features()`，這個函式預設從
`data/raw/*.csv` 讀資料（`stage2_eda.weather_eda.load_all_cities()`），
跟 `pipeline/update_data.py` 寫入的 `daily_weather` 表是兩份完全不同的
資料。手動測試「先跑 `update_data.py` 補到昨天，再重新預測」這個完整
流程時，發現預測基準日仍然停在 2025-12-31（CSV 結尾），完全沒有反映
剛補進資料庫的 204 天新資料——資料流水線形同虛設。已修正為新增
`load_daily_weather_df()`，讓 `compute_predictions()` 改吃資料庫內容
（`build_features(df=load_daily_weather_df(conn), ...)`）。修正後重測，
基準日正確變成資料庫裡的最新日期（2026-07-23），確認修好。這是一個
值得記住的教訓：組合多個模組時，每個函式的資料來源必須明確追蹤，
「反正都是同一份資料」的假設在有多個資料入口（CSV vs 資料庫）時很容易
悄悄出錯，而且不會報錯——只是安靜地用了舊資料。
