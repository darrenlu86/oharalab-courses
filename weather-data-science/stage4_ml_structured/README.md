# stage4_ml_structured — 結構型資料分析（AI-10）

## 這一關在教什麼

拿乾淨的表格資料做兩個經典任務：分類（明天會不會下雨）、回歸（明天最高
溫幾度）。重點不是「把模型跑起來」——那三行 `sklearn` 就能做到——而是
**時間序列的特徵工程怎麼做才不會作弊**，以及**怎麼證明模型真的學到東西
而不是看起來厲害而已**（跟基準線比較）。

## 你會學到

- lag 特徵、rolling 均值特徵的設計方式，以及為什麼用「目標日期往回數」
  的命名比「往前數」更貼近推論情境。
- **為什麼時間序列不能隨機切分成訓練/測試集**——這是本階段最重要的
  概念，`features.py` 的 `split_train_test()` docstring 有完整解釋。
- 基準線的意義：如果模型贏不過「明天=今天」這種幾乎零智慧的規則，
  這個模型就沒有存在的必要。
- 分類指標（accuracy/precision/recall/F1/AUC）與回歸指標（MAE/RMSE）
  各自在講什麼，以及為什麼只看 accuracy 可能被騙。

## 完成後產出對照表

| 專案卡要求 | 本階段交付 |
|---|---|
| 完整的訓練與推論程式碼 | `features.py` + `train.py` + `predict.py` |
| 模型效能評估報告 | `report.md`（含基準線對照表、混淆矩陣、特徵重要度） |
| 含欄位定義與來源說明的應用情境 Demo 簡報 | `slides.md`（含資料字典） |

## 前置需求

- repo 根 `venv/` 已安裝 `requirements.txt`（含 `scikit-learn`、`joblib`）。
- `data/raw/*.csv` 已存在（不需要 stage3 的資料庫，這裡直接讀 CSV）。

## 快速開始

訓練並評估兩個任務：

```
venv/bin/python -m stage4_ml_structured.train
```

預期輸出（實測數字，完整見 `report.md`）：

```
=== 任務 A：明日降雨分類 ===
模型                      accuracy  precision   recall      f1  roc_auc
baseline_persistence       0.716      0.687    0.687   0.687    0.714
random_forest               0.724      0.697    0.695   0.696    0.803

=== 任務 B：明日高溫回歸 ===
模型                      MAE (°C)  RMSE (°C)
baseline_persistence        1.656      2.339
random_forest                1.575      2.153
```

單筆推論（載入剛剛訓練好的模型）：

```
venv/bin/python -m stage4_ml_structured.predict --city taipei --date 2025-06-15
```

預期輸出（實測）：

```
城市：taipei　基準日：2025-06-15（預測隔天）
降雨機率：39.7%（預測標籤：不下雨，門檻 precipitation_sum >= 1.0mm）
最高溫預測：33.6°C
實際降雨標籤：下雨
實際最高溫：33.9°C
```

（這筆剛好是模型判斷錯誤的案例——預測不下雨但實際下雨了，刻意留著沒有
換一個「模型答對」的例子，誠實比報喜不報憂重要。）

## 逐步教學

### 第一步：為什麼 lag_1 就是 persistence 基準線

打開 `features.py`，注意 `lag_1_temp_max` 的定義就是「今天」的溫度
（`shift(k - 1)`，`k=1` 時等於 `shift(0)`，也就是不位移）。這不是巧合——
persistence 基準線（「明天 = 今天」）用的正是這個值。這樣設計讓你能直接
問一個問題：「我的模型除了 `lag_1` 這一個特徵之外，其他特徵到底有沒有
在幫忙？」——看 `report.md` 的特徵重要度圖就有答案。

### 第二步：親手驗證「不能隨機切分」這件事有多嚴重

`split_train_test()` 的 docstring 解釋了原因，但更有說服力的做法是自己
動手改一次：把 `train.py` 裡的切分換成
`sklearn.model_selection.train_test_split(df, test_size=0.2,
shuffle=True)`，重新跑一次，你會看到 accuracy/AUC 看起來「進步」了不少
——但那是假象，因為測試集裡混進了訓練集鄰居那一天的資料，本課程不建議
你把這個版本拿去交作業（延伸挑戰有具體引導）。

### 第三步：讀懂基準線比較表，練習「誠實」

看 `report.md` 的分類任務表：`random_forest` 的 accuracy（0.724）只比
`baseline_persistence`（0.716）高不到一個百分點。如果你只看 accuracy 就
下結論「模型幾乎沒用」，那你漏看了 AUC（0.803 vs 0.714）——這代表模型的
機率排序能力其實有明顯進步，只是 0.5 這個門檻下二值化後差異被壓縮了。
這是本階段刻意留給你的閱讀練習：**不同指標會講出不同故事，要一起看**。

## 為什麼這樣設計

**為什麼分類基準線要用「氣候頻率」而不是「永遠猜多數類別」？** 因為
「氣候頻率」（依城市 x 月份分組的歷史下雨機率）本身已經是一個有意義的
天氣預報方法（氣象局的「氣候預測」概念的簡化版），拿它當基準線比「無腦
猜多數類別」更貼近真實情境——如果連这個都贏不了，代表模型真的沒有用到
比「知道現在幾月、在哪個城市」更多的資訊。

**為什麼回歸任務的模型（Ridge/RandomForest）只小贏 persistence？** 看
`report.md` 的特徵重要度圖（`fig03`）就知道：`lag_1_temp_max`（今天的
溫度）的重要度壓倒性地高於其他全部特徵加起來——這代表「明天的溫度主要
由今天的溫度決定」這件事本身就是天氣的物理特性（溫度有很強的日際
自相關），不是模型技巧不夠好。這也是為什麼 persistence 基準線在溫度
預測上表現得不錯：它抓到的正是這個最強的訊號。

## 注意（常見錯誤 / 踩坑紀錄）

- **NaN 比較運算子的陷阱**：`features.py` 的 `build_features()` 一開始
  用 `(next_day_precip >= RAIN_THRESHOLD_MM).astype("Int64")` 計算明天
  是否下雨的標籤，這裡有個真實踩過的坑——當 `next_day_precip` 是 NaN
  （每個城市最後一天沒有「明天」），`NaN >= 1.0` 這個比較運算子在 pandas
  裡回傳的是 `False`，**不是 NaN**！如果不處理，`predict.py` 對資料集
  最後一天做推論時，會印出一個假的「實際降雨標籤：不下雨」，但那一天
  根本没有隔天資料可以拿來比對。已修正為先用 `.mask(next_day_precip.
  isna())` 明確把缺值位置轉回 NaN，再轉型（見 `report.md` 完整踩坑
  說明）。這個坑值得記住：**NaN 參與比較運算不會傳播成 NaN，會變成
  False，寫涉及缺值的條件判斷時要特別小心**。
- **模型檔案很大**：`temp_random_forest_v1.joblib` 大約 27MB
  （`n_estimators=300`），這是為什麼 `.joblib` 要 gitignore、`train.py`
  要保持「一鍵可重新產生」的原因——不要把大型二進位模型檔案塞進 git。
- **`predict.py` 只能對 `data/raw` 範圍內的日期做推論**：這是教學版的
  限制——真實產品需要串接即時天氣 API 才能預測「未來」的隔天，本課程的
  `predict.py` 是對歷史資料做「事後驗證式」的推論，用來示範模型怎麼被
  載入使用，不是一個能預測明天真實天氣的服務。

## 驗收 checklist

- [x] `venv/bin/python -m pytest tests/test_stage4_ml_structured.py -v`
      全綠（15 個測試）。
- [x] `train.py` 實際執行，兩個任務的指標表與基準線對照表都印出，且
      模型全部贏過至少一個基準線。
- [x] `predict.py` 對至少一筆有隔天資料的日期執行，印出的預測值與實際
      值都存在（不管預測對或錯）。
- [x] 四張圖表都存在 `figures/` 且非空圖。
- [x] report.md 的數字與 `train.py` 實際輸出一致（逐項核對過）。

## 延伸挑戰

1. 把切分方式換成隨機切分（`shuffle=True`），比較指標「虛高」的幅度，
   寫一段說明你觀察到的具體數字落差。
2. 幫分類任務加一個 `lead_time=2`（預測「後天」而不是「明天」）的版本，
   觀察基準線與模型的差距是不是隨著預測距離拉遠而擴大。
3. 對回歸任務嘗試 `GradientBoostingRegressor`，跟 Ridge/RandomForest
   比較 MAE/RMSE，寫進你自己的一段報告。
