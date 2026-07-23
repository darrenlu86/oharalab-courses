## stage4_ml_structured — 結構型資料分析

AI-10 結構型資料的分析案例 ｜ B 級 / 4 點

---

## 兩個任務

- **任務 A（分類）**：明天會不會下雨（`precipitation_sum >= 1.0mm`）
- **任務 B（回歸）**：明天最高溫幾度

---

## 資料字典

| 欄位 | 定義 |
|---|---|
| `lag_1/2/3_temp_max`, `lag_1/2/3_precip` | 目標日期往回數第 1/2/3 天 |
| `rolling_7/30_temp_max`, `rolling_7/30_precip` | 過去 7/30 天均值 |
| `month`, `city_*` | 月份、城市 one-hot |
| `target_rain_tomorrow`, `target_temp_max_tomorrow` | 明天的標籤/數值 |

---

## 為什麼不能隨機切分

今天的天氣跟明天高度自相關

隨機切分 = 測試集混進訓練集鄰居那天的資料 → 分數虛高

訓練：≤2023-12-31（9774 列）／測試：2024~2025（2190 列）

---

## 任務 A 實測結果

| 模型 | accuracy | roc_auc |
|---|---|---|
| baseline_persistence | 0.716 | 0.714 |
| baseline_climatology | 0.673 | 0.732 |
| logistic_regression | 0.709 | 0.786 |
| **random_forest** | **0.724** | **0.803** |

只小勝 persistence（+0.008 accuracy），但 AUC 差距更明顯

---

## 任務 B 實測結果

| 模型 | MAE (°C) | RMSE (°C) |
|---|---|---|
| baseline_persistence | 1.656 | 2.339 |
| baseline_monthly_mean | 2.375 | 3.071 |
| **ridge** | **1.565** | **2.149** |
| random_forest | 1.575 | 2.153 |

Ridge 略贏 RandomForest —— 問題本質接近線性

---

## 特徵重要度

分類：`lag_1_precip`（今天下雨與否）主導，約 0.28

回歸：`lag_1_temp_max`（今天氣溫）壓倒性主導，約 0.87

→ 兩任務都印證「天氣有很強的日際自相關」

---

## 踩坑紀錄

`NaN >= 門檻` 在 pandas 回傳 False，不是 NaN

`predict.py` 對最後一天推論時曾印出假的「實際值」

已用 `.mask()` 修正，並補迴歸測試

---

## 誠實結論

- 兩任務都贏過基準線，但都不是壓倒性勝利
- accuracy 差距小，但 AUC 差距明顯 —— 不同指標講不同故事
- 模型檔案 gitignored，`train.py` 可用固定 random_state 完整重現
