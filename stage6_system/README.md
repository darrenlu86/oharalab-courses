# stage6_system — 天氣智慧儀表板（AI-12）

## 這一關在教什麼

前面五個階段各自產出了資料、模型、爬蟲——這一關把它們全部串成一個可以
實際打開瀏覽器操作的系統：資料流水線（補資料）→ 模型（stage4/5 訓練好
的）→ 介面（FastAPI + Chart.js）→ 監測（預測 vs 實際）→ 迭代（v1 vs v2
特徵比較）。這是本課程的收尾專案，示範「資料科學專案」跟「資料科學系統」
的差別：後者要處理資料新舊、模型缺失、錯誤降級這些前面五關不太需要面對
的問題。

## 你會學到

- 怎麼把多個獨立訓練出來的模型（stage4 兩個、stage5 一個）組進同一個
  服務裡，並且處理「模型還沒訓練好」這種初始化前狀態。
- FastAPI 的依賴注入（`Depends`）怎麼讓路由邏輯可以脫離真實資料庫/模型
  單獨測試（`app.dependency_overrides`）。
- 監測迴圈的完整生命週期：預測 → 寫入 → 等待時間過去 → 回填實際 → 計算
  準確率——這個迴圈本身需要時間才能跑完整,不是一次呼叫就有結果。
- Chart.js 怎麼在完全離線（vendored 進 repo）的情況下運作。
- 一個具體、可驗證的教訓：**串連多個模組時,「資料從哪裡來」這件事必須
  明確,不能預設「反正都是同一份資料」**——本階段開發時就踩到這個坑
  （見下方「注意」）。

## 完成後產出對照表

| 專案卡要求 | 本階段交付 |
|---|---|
| 完整訓練與推論程式碼 | 重用 stage4/5 的訓練程式碼；`pipeline/bootstrap.py` 負責「缺就重訓」 |
| 模型效能評估報告 | `report.md`（v1 vs v2 特徵迭代比較，含真實數字） |
| 應用情境 Demo 簡報 | `slides.md` |
| 可運行的完整系統（本地 Demo） | `app.py`（四個頁面）+ `pipeline/`（三支流水線腳本） |
| 模型落地後的效能評估與迭代優化報告 | `report.md`（監測機制說明＋下一步迭代方向） |

## 前置需求

- repo 根 `venv/` 已安裝 `requirements.txt`。
- stage3（資料庫 schema）、stage4（降雨/高溫模型）、stage5（文字情感
  模型）建議先跑過一次，但**不是必要**——`pipeline/bootstrap.py` 會自動
  補齊缺的部分（資料庫、資料、模型）。

## 快速開始

**第一步**——一鍵初始化（缺什麼補什麼）：

```
venv/bin/python -m stage6_system.pipeline.bootstrap
```

預期輸出（實測，若 stage3/4/5 都已經跑過會全部顯示「跳過」）：

```
stage6_system 一鍵初始化...
  - 資料庫已存在，跳過建立
  - daily_weather 已有 12054 列，跳過匯入
  - comments 已有 2400 列，跳過匯入
  - stage4 模型（降雨分類＋高溫回歸）已存在，跳過訓練
  - stage5 文字情感模型已存在，跳過訓練
初始化完成。啟動儀表板：venv/bin/python -m uvicorn stage6_system.app:app --port 8320
```

**第二步**——啟動儀表板：

```
venv/bin/python -m uvicorn stage6_system.app:app --port 8320
```

打開瀏覽器 `http://127.0.0.1:8320/` 看總覽頁；`/predict` 按「重新預測」；
`/sentiment` 看留言情感面板；`/monitoring` 看歷史預測與準確率。

**（可選）第三步**——補最新資料＋回填監測：

```
venv/bin/python -m stage6_system.pipeline.update_data          # 打 Open-Meteo archive API
venv/bin/python -m stage6_system.pipeline.backfill_actuals      # 回填已經過去的預測
```

## 逐步教學

### 第一步：先跑 bootstrap，觀察它做了什麼

`pipeline/bootstrap.py` 依序檢查五件事（資料庫、daily_weather、
comments、stage4 模型、stage5 模型），每件事都先問「已經存在嗎」再決定
要不要動手——這是冪等設計的具體示範,你可以放心重複執行,不會浪費時間
重新訓練已經訓練好的模型。

### 第二步：`/predict` 頁面按「重新預測」，觀察 predictions 表

打開 `/monitoring` 頁面，你會看到剛剛按下的預測被記錄下來，`actual_
label` 是「尚未回填」——這是正確的行為，因為「明天」這件事還沒發生。
這個時間差正是監測機制存在的理由：模型好不好，要等真實結果出來才能
驗證，不能只看訓練時的測試集分數。

### 第三步：讓監測迴圈真正跑完一次

跑 `pipeline/update_data.py` 補到最新資料，再跑
`pipeline/backfill_actuals.py`，回到 `/monitoring` 頁面——如果補到的
資料涵蓋了你先前預測的 `target_date`，這時候「實際」欄位與準確率就會
出現。本課程開發時實際跑過這個完整迴圈（見 `report.md`），三筆預測
（2026-01-01 台北/台中/高雄）全部回填後準確率 100%——這是三筆的結果，
樣本數很小，不能過度解讀成「模型很準」，只是示範迴圈真的能跑完整。

### 第四步：讀 v1 vs v2 特徵迭代比較

跑 `venv/bin/python -m stage6_system.model_iteration_report`，比較
「只用 lag 特徵」（v1）跟「加上 rolling 均值與月份」（v2）的差異——這是
「模型落地後怎麼迭代優化」的具體示範，不是憑感覺加特徵，而是同一份
切分、同一種模型，只變動特徵集合，量化比較差異。

## 為什麼這樣設計

**為什麼 `/predict` 用 POST 觸發計算、GET 只顯示？** 因為「預測」這個
動作有副作用（寫入 predictions 表），符合 REST 語意的話不該掛在 GET
上（GET 理論上應該是無副作用的）。GET `/predict` 顯示「最新一筆」，
POST 才會真的重新計算——這個切分本身就是一個值得記住的 API 設計原則。

**為什麼儀表板要能在模型缺失時回 503 而不是 500？** 503（Service
Unavailable）明確傳達「服務暫時不可用，等我準備好」的語意，跟 500
（未知錯誤，可能是程式壞了）給使用者的訊息完全不同——`get_models_or_
503()` 這個依賴函式把 `FileNotFoundError` 轉成 503，並在錯誤訊息裡
直接告訴你該跑哪個指令修好它。

**為什麼 v1/v2 特徵比較要獨立寫一支腳本，不直接改 `stage4_ml_
structured/train.py`？** 因為 stage4 的 `train.py` 目的是產出「正式
使用的模型」（v2,已經是最好的版本),v1 只是為了寫這份報告而存在的
「刻意退化版」,混在正式訓練腳本裡會讓 `train.py` 的用途變得不單純。
獨立成 `model_iteration_report.py`，語意上更清楚：這是分析報告用的
腳本，不是產品程式碼。

## 注意（常見錯誤 / 踩坑紀錄）

- **`/predict` 一開始完全沒有反應資料庫的更新**：第一版
  `compute_predictions()` 直接呼叫 `stage4_ml_structured.features.
  build_features()`，這個函式預設從 `data/raw/*.csv`（`stage2_eda.
  weather_eda.load_all_cities()`）讀資料，跟 `pipeline/update_data.py`
  寫入的 `daily_weather` 表完全是兩份不同的資料來源！手動測試「先跑
  `update_data.py` 補到昨天，再重新預測」時，發現預測基準日永遠停在
  2025-12-31（CSV 的最後一天），完全沒有反映資料庫裡新補的資料。已修正
  為新增 `load_daily_weather_df()`，讓 `/predict` 改吃資料庫內容——這是
  一個很實際的教訓：**串連多個模組時,搞清楚「這個函式的資料到底從哪裡
  來」是最容易被忽略、但出錯後最難察覺的一類 bug**（因為程式不會報錯,
  只是安靜地用了舊資料)。
- **FastAPI TestClient 的執行緒陷阱**：sync def 路由在 TestClient 底下
  是丟進 worker thread 執行，如果測試裡的假資料庫連線是在 pytest 主
  執行緒建立、再透過 `dependency_overrides` 傳進去，會撞到 SQLite的
  `check_same_thread` 保護（`SQLite objects created in a thread can
  only be used in that same thread`）。修正方式：測試用的連線建立時
  加 `check_same_thread=False`（詳見 `tests/test_stage6_system.py` 的
  `db_conn` fixture 註解）。這只是測試層的問題，正式運行（uvicorn）沒
  有出現這個錯誤，因為 `get_db()` 是在請求處理當下才建立新連線，不會
  跨執行緒傳遞既有連線物件。
- **Chart.js 是 vendored 檔案，不是本課程程式碼**：`static/vendor/
  chart.umd.min.js`（v4.4.4，MIT 授權，見同目錄 `NOTICE.md`）是唯一一份
  直接複製第三方原始碼進 repo 的檔案，其餘全部程式碼都是本課程原創。

## 驗收 checklist

- [x] `venv/bin/python -m pytest tests/test_stage6_system.py
      tests/test_stage6_pipeline.py -v` 全綠（29 個測試）。
- [x] `pipeline/bootstrap.py` 在「全部缺失」與「全部已存在」兩種狀態下
      都手動跑過，行為符合預期（見 `report.md`）。
- [x] 儀表板四個頁面都手動用 `curl` 打過，回應 200，內容含真實資料。
- [x] 完整監測迴圈（預測→`update_data`→`backfill_actuals`→準確率出現）
      實際跑過一次，見 `report.md`。
- [x] v1/v2 特徵迭代比較實際執行過，數字寫進 `report.md`，不是估計值。

## 延伸挑戰

1. 幫 `/monitoring` 加上「按城市分開看準確率」的功能（目前是全部城市
   合併計算一個準確率）。
2. 把 `pipeline/update_data.py` 包成排程（例如用 `cron`）,每天自動跑一
   次補資料＋回填,體會「自動化資料流水線」跟「手動執行腳本」的差別
   （提醒：本課程刻意不示範真的排程設定,見 `oharalab-skill` 這類外部
   工具鏈的排程最佳實務,不在本課程範圍內）。
3. 把 `/sentiment` 頁面的即時計算（每次請求都重新跑 TF-IDF+MLP）改成
   預先計算並快取，比較回應時間的差異，並討論「即時計算 vs 預先快取」
   的取捨。
