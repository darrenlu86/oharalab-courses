# stage4_ml_structured 效能評估報告

資料：`data/raw/{taipei,taichung,kaohsiung}.csv`（Open-Meteo，2015~2025）。
特徵工程見 `features.py`；訓練/測試切分：<=2023-12-31 訓練（9774 列，
2015-01-30~2023-12-31）、>2023-12-31 測試（2190 列，2024-01-01~
2025-12-30）。以下數字全部取自 2026-07-24 `train.py` 的實際執行輸出，
不是估計值。

## 資料字典

| 欄位 | 定義 | 來源 |
|---|---|---|
| `lag_1_temp_max` / `lag_2_temp_max` / `lag_3_temp_max` | 目標日期（明天）往回數第 1/2/3 天的最高溫 | `data/raw` 的 `temperature_2m_max` |
| `lag_1_precip` / `lag_2_precip` / `lag_3_precip` | 目標日期往回數第 1/2/3 天的降雨量 | `data/raw` 的 `precipitation_sum` |
| `rolling_7_temp_max` / `rolling_30_temp_max` | 以今天為結尾的過去 7/30 天最高溫均值 | 衍生自 `temperature_2m_max` |
| `rolling_7_precip` / `rolling_30_precip` | 以今天為結尾的過去 7/30 天降雨量均值 | 衍生自 `precipitation_sum` |
| `month` | 今天的月份（1~12） | 衍生自 `date` |
| `city_taipei`/`city_taichung`/`city_kaohsiung` | 城市 one-hot | 衍生自 `city` |
| `target_rain_tomorrow` | 明天是否下雨（`precipitation_sum>=1.0mm`） | 衍生自明天的 `precipitation_sum` |
| `target_temp_max_tomorrow` | 明天的最高溫 | 明天的 `temperature_2m_max` |

雨天門檻 1.0mm 與 `docs/DATA_SOURCES.md`／`scripts/generate_synthetic.py`
一致，全課程統一定義。

## 任務 A：明日降雨分類（實測）

| 模型 | accuracy | precision | recall | f1 | roc_auc |
|---|---|---|---|---|---|
| baseline_persistence（明天=今天） | 0.716 | 0.687 | 0.687 | 0.687 | 0.714 |
| baseline_climatology（城市x月份歷史頻率） | 0.673 | 0.662 | 0.571 | 0.613 | 0.732 |
| logistic_regression | 0.709 | 0.691 | 0.650 | 0.670 | 0.786 |
| random_forest | **0.724** | 0.697 | 0.695 | 0.696 | **0.803** |

混淆矩陣（`fig01_confusion_matrix_rain.png`，RandomForest，測試集
2190 筆）：

```
              預測不下雨  預測下雨
實際不下雨       894        301
實際下雨         303        692
```

## 任務 B：明日高溫回歸（實測）

| 模型 | MAE (°C) | RMSE (°C) |
|---|---|---|
| baseline_persistence（明天=今天） | 1.656 | 2.339 |
| baseline_monthly_mean（城市x月份歷史均溫） | 2.375 | 3.071 |
| ridge | **1.565** | **2.149** |
| random_forest | 1.575 | 2.153 |

## 特徵重要度（`fig02`/`fig03`，RandomForest）

- **分類任務**：`lag_1_precip`（今天的降雨量）重要度最高（約 0.28），其次
  是 `rolling_7_precip`（約 0.12）與 `rolling_30_precip`（約 0.11）——
  「今天/近期有沒有下雨」是預測「明天會不會下雨」最強的訊號，符合天氣
  系統（鋒面、梅雨）持續數天的物理直覺。城市 one-hot 三欄重要度都很低
  （<0.02），代表模型主要靠天氣動態本身判斷，不是靠「這是哪個城市」的
  先驗。
- **回歸任務**：`lag_1_temp_max`（今天的最高溫）重要度壓倒性地高（約
  0.87），其他 13 個特徵加起來不到 0.13——這解釋了為什麼 persistence
  基準線在溫度預測上表現不錯（MAE 1.656），模型能小贏的空間有限。

## 誠實結論

1. **分類任務：RandomForest 只小勝 persistence（accuracy 0.724 vs
   0.716，差距 0.008）**，如果只看 accuracy，很難說模型有實質進步。但
   AUC 差距更明顯（0.803 vs 0.714），代表模型的機率排序能力確實比
   persistence 好，只是 0.5 門檻二值化後差異被壓縮——這裡不誇大 accuracy
   的小差距，也不忽略 AUC 的較大差距，兩者都如實寫出。
2. **分類任務：climatology 基準線 AUC（0.732）比 persistence（0.714）
   高，但 accuracy（0.673）比 persistence（0.716）低**——這是因為
   climatology 給出的是連續機率（AUC 看的是排序能力），而 accuracy 用
   0.5 門檻二值化後，气候頻率法在很多城市/月份組合下機率接近但不過
   0.5，二值化後反而不如「直接抄今天」準。這是一個具體示範「不同基準線
   在不同指標上表現不同」的案例。
3. **回歸任務：Ridge（MAE 1.565）比 RandomForest（MAE 1.575）略好**——
   線性模型在這個任務上並沒有輸給樹模型，特徵重要度顯示問題本質接近
   線性（`lag_1_temp_max` 主導），複雜模型沒有額外優勢。
4. **兩個任務都贏過各自的基準線，但都不是壓倒性勝利**——這符合天氣
   預測的物理現實：短期天氣有很強的自相關（今天很像明天），簡單的
   persistence 本來就是一個難以大幅超越的基準線，不是模型訓練失敗。
5. 模型檔案（`*.joblib`）gitignored，`train.py` 可完整重新產生，不依賴
   任何未提交的隨機狀態（`random_state=42` 全部固定）。

## 踩坑紀錄

開發 `predict.py` 手動測試「對資料集最後一天做推論」時發現：
`build_features()` 計算 `target_rain_tomorrow` 用
`(next_day_precip >= RAIN_THRESHOLD_MM).astype("Int64")`，但每個城市
最後一天的 `next_day_precip`（明天的降雨量）是 NaN（沒有明天）。pandas
裡 `NaN >= 1.0` 這個比較運算子回傳的是 **False**，不是 NaN——導致
`predict.py` 對高雄 2025-12-31 做推論時，一開始印出一個假的「實際降雨
標籤：不下雨」，但那天根本沒有隔天資料可以驗證。已修正為先用
`.mask(next_day_precip.isna())` 明確把缺值位置轉回 NaN 再轉型，並補上
迴歸測試（`test_require_target_false_leaves_last_day_target_as_na_not_
fabricated_false`）防止此問題再次發生。這是本階段開發過程中真的抓到的
bug，不是預先設計的教學案例。
