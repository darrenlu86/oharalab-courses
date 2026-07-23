## stage6_system — 天氣智慧儀表板

AI-12 資料科學在真實世界的應用系統 ｜ C 級 / 5 點

---

## 系統組成

資料流（update_data.py）→ 模型（stage4/5）→ 介面（FastAPI+Chart.js）
→ 監測（predictions 表）→ 迭代（v1 vs v2 特徵比較）

四頁：`/` `/predict` `/sentiment` `/monitoring`

---

## 一鍵初始化

```
venv/bin/python -m stage6_system.pipeline.bootstrap
```

缺資料庫就建、缺資料就從 CSV/合成語料匯入、缺模型就呼叫 stage4/5 訓練邏輯重建

已存在的部分全部跳過 —— 冪等，可放心重複執行

---

## 監測迴圈實測

1. `/predict` 寫入 3 筆預測（2026-01-01）
2. `update_data.py` 補 204 天真實資料（Open-Meteo API）
3. `backfill_actuals.py` 回填實際值
4. 準確率：**3/3 = 100%**（樣本數極小，僅證明機制跑得通）

---

## 踩坑：預測沒反映資料庫更新

`compute_predictions()` 原本呼叫 `build_features()` → 讀 CSV

`update_data.py` 更新的是 SQLite → 兩者對不上！

補資料後重新預測，基準日仍卡在 2025-12-31

修正：新增 `load_daily_weather_df()`，改吃資料庫內容

---

## v1（僅 lag）vs v2（+rolling/月份）

| 任務 | v1 | v2 | 差異 |
|---|---|---|---|
| 分類 accuracy | 0.730 | 0.730 | 幾乎無差 |
| 回歸 MAE | 1.617 | 1.576 | -2.5% |

分類任務加 rolling/月份邊際效益低；回歸任務有小幅穩定改善

---

## 為什麼 /predict 用 POST 不用 GET

預測有副作用（寫入 predictions 表）

GET 應該無副作用 —— REST 語意上不該用 GET 觸發

GET 只顯示最新一筆，POST 才真的重新計算

---

## 誠實結論

- 3 筆樣本的「100% 準確率」不代表模型準，只證明監測迴圈跑得通
- v1/v2 比較顯示特徵工程的邊際效益因任務而異，不是加越多越好
- Chart.js vendored 進 repo（MIT 授權），全程可離線執行
- 本系統為本地 Demo，無雲端部署、無排程自動化
