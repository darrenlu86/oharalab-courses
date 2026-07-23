# stage1_api_app — 天氣速報小幫手（AI-7）

## 這一關在教什麼

怎麼把兩個外部服務串成一個能用的小工具：一個真的 Data API（Open-Meteo
天氣預報，免帳號免金鑰）、一個模仿 OpenAI 格式的本地 mock AI 服務。這是
多數「Data/AI 應用案例」的最小骨架——抓資料、餵給模型、整理輸出——先在
最簡單的規模上把這個骨架搭穩，後面五個階段都是在這個骨架上加東西。

## 你會學到

- `requests` 怎麼設逾時（timeout）、失敗重試（retry），以及為什麼不能
  無限重試。
- OpenAI Chat Completions API 的請求/回應格式長什麼樣子（`messages`
  陣列、`Authorization: Bearer`、`choices[0].message.content`），即使你
  沒有 OpenAI 帳號也能練到格式本身。
- 為什麼程式要把「取得資料」「呼叫模型」「格式化輸出」三個步驟拆開寫成
  獨立函式（提示：全部混在一起沒辦法測試,也沒辦法在服務掛掉時優雅降級）。
- API 金鑰要放環境變數,不要寫死進程式碼——即使是完全不值錢的 mock 金鑰
  也要養成這個習慣,因為習慣是在低風險情境練出來的。

## 完成後產出對照表

專案卡 AI-7 要求的產出,對照本階段實際交付：

| 專案卡要求 | 本階段交付 |
|---|---|
| 可運作的 Python 程式碼 | `weather_brief.py`（CLI）+ `mock_ai_server.py`（FastAPI 服務） |
| 成果示範影片或截圖 | 以「實測輸出原文」替代：`samples/demo_output.txt`（真實執行輸出）+ 下方「快速開始」的終端機截圖指引 |
| 應用情境說明與成果報告簡報 | `report.md` + `slides.md` |

## 前置需求

- 已建好 repo 根的 `venv/`，已 `pip install -r requirements.txt`。
- 需要兩個終端機視窗（一個跑 mock AI 服務、一個跑 CLI）。
- `--offline` 模式不需要網路,但仍然需要 mock AI 服務在跑（`--offline`
  只影響天氣資料來源,不影響 AI 服務,這是刻意設計,見下方「為什麼這樣
  設計」）。

## 快速開始

**終端機 1**——啟動 mock AI 服務：

```
venv/bin/python -m uvicorn stage1_api_app.mock_ai_server:app --port 8331
```

**終端機 2**——執行 CLI：

```
venv/bin/python -m stage1_api_app.weather_brief --city taipei --offline
```

預期輸出（實測，見 `samples/demo_output.txt` 完整存檔）：

```
============================================
  天氣速報小幫手｜台北
============================================
（資料來源：stage1_api_app/samples/（離線樣本，非本次即時抓取））

【今天】2026-07-24
  天氣狀況：雷雨
  溫度：25.2 ~ 34.1 度
  降雨機率：29%（預估降雨量 1.8 mm）
  最大風速：20.9 km/h

【明天】2026-07-25
  天氣狀況：毛毛雨（弱）
  溫度：26.3 ~ 31.3 度
  降雨機率：49%（預估降雨量 0.6 mm）
  最大風速：25.8 km/h

【AI 建議】（本地 mock 服務規則式生成，非真實 LLM）
  降雨機率偏低（29%），基本上不需要特別準備雨具。 最高溫達 34.1 度，天氣炎熱，建議穿著透氣輕便衣物，注意防曬與補充水分。

============================================
```

去掉 `--offline` 就會即時打 Open-Meteo forecast API,拿到「今天」的真實
日期與數字（會跟上面不一樣,因為是不同時間點抓的）。

## 逐步教學

### 第一步：看懂 mock AI 服務在幹嘛

打開 `mock_ai_server.py`。這不是真的語言模型——它用正規表示式
（`TODAY_PATTERN`/`TOMORROW_PATTERN`）從固定格式的文字裡把溫度、降雨機率、
風速抽出來,套進一組 if/else 規則（`_rain_advice`/`_clothing_advice`/
`_wind_advice`）產生建議。之所以包成一個 FastAPI 服務、模仿 OpenAI 的
`POST /v1/chat/completions` 格式,是因為你要練的是「呼叫一個 OpenAI 相容
API」這件事本身——請求要帶 `Authorization: Bearer <key>`,回應要從
`choices[0].message.content` 拿文字,這套介面換成真正的 OpenAI 或任何
相容服務都通用。

### 第二步：看懂 CLI 怎麼串起兩邊

`weather_brief.py` 分成三段函式：

1. `get_forecast(city, offline)` —— `offline=False` 呼叫真實 API
   （`fetch_forecast`,有逾時與重試）；`offline=True` 讀
   `samples/forecast_{city}.json`（`load_offline_forecast`）。
2. `build_ai_prompt(...)` 把預報 dict 轉成固定格式文字,`call_mock_ai(...)`
   把這段文字 POST 給 mock 服務,拿回建議文字。
3. `build_briefing_text(...)` 把預報數字與 AI 建議排版成最終輸出。

拆成三段的好處：`build_ai_prompt`/`build_briefing_text` 是純函式（沒有
I/O),`tests/test_stage1_api_app.py` 可以直接測,不用真的連網路或啟動
服務;`fetch_forecast`/`call_mock_ai` 則設計成可以注入假的 `session`/
`client`,測試時换成假物件或 `TestClient`。

### 第三步：親手體驗錯誤處理

把終端機 1 的 mock AI 服務按 Ctrl+C 關掉,再跑一次終端機 2 的指令——你會
看到 CLI 沒有整個炸掉,而是照樣印出天氣預報,只是「AI 建議」那一段變成
一段說明「無法連線」的文字。這是 `main()` 裡 `except
requests.RequestException` 接住的優雅降級,刻意示範「外部服務掛掉不代表
整個功能都要掛掉」。

## 為什麼這樣設計

**為什麼 `--offline` 不順便讓 AI 服務也離線？** 因為 mock AI 服務本來就是
本地服務,不是外部依賴——它不需要「離線模式」,它本身就是離線的。
`--offline` 這個旗標只解決「不想每次測試都打真的 Open-Meteo API」這個
問題,跟 AI 服務要不要跑是兩件事。這個切分方式也讓你在寫測試時,清楚看到
兩種外部依賴（真的雲端服務 vs 本地服務）需要不同的因應策略。

**為什麼要把 prompt 格式設計得這麼死板（正規表示式看得懂的固定格式）？**
因為 mock 服務是規則式的,不是真的語言模型,沒辦法理解任意格式的自然語言。
這件事故意做得很明顯,不是缺陷——如果你把 `mock_ai_server.py` 換成真正的
OpenAI API,格式要求會鬆很多（真的 LLM 看得懂自由格式的描述),但呼叫端
(`call_mock_ai` 的介面設計:傳 `messages`,收 `choices[0].message.content`)
完全不用改。

**為什麼 `fetch_forecast`/`call_mock_ai` 都設計成可以注入 `session`/
`client`？** 這是讓網路呼叫可測試的標準做法（SPEC §7 的硬性要求）：
生產環境用預設的 `requests`/`http://127.0.0.1:8331`,測試環境注入假物件
或 FastAPI `TestClient`,同一份程式碼、同一組斷言邏輯,不用為了測試另外
寫一套 mock 框架。

## 注意（常見錯誤）

- **忘記先啟動 mock AI 服務**：直接跑 CLI 會在「AI 建議」那一段看到連線
  失敗訊息,天氣預報那半段仍然正常——這是設計行為,不是 bug,但常有人以為
  程式壞了。
- **`--offline` 樣本的日期是擷取當下,不會更新**：見
  `samples/README.md` 的完整說明,不要拿樣本日期去對現在的真實天氣。
- **mock 服務認不得非固定格式的文字**：如果你手動改了 `build_ai_prompt`
  的輸出格式而沒有同步改 `mock_ai_server.py` 的正規表示式,`generate_advice`
  會回傳「看不懂格式」的誠實訊息,而不是報錯或亂猜——這是刻意的邊界可見性
  設計,不要「修好」成看起來更聰明但其實在猜的行為。

## 驗收 checklist

- [x] `venv/bin/python -m pytest tests/test_stage1_api_app.py -v` 全綠
      （20 個測試,2026-07-24 實測通過)。
- [x] 依「快速開始」兩個終端機指令實際跑一次,拿到跟 `samples/demo_output.txt`
      一致的輸出結構（今天/明天預報 + AI 建議段落)。
- [x] 關掉 mock AI 服務後重跑,確認優雅降級（印出說明文字而非例外堆疊)。
- [x] 三個城市（taipei/taichung/kaohsiung）分別跑過 `--offline`,確認都有
      對應的離線樣本可讀。

## 延伸挑戰

1. 把 `mock_ai_server.py` 換成真正呼叫 OpenAI API（需要自己申請帳號與
   金鑰,本課程不提供,也不會替你付費）——體會兩者在呼叫端程式碼幾乎不用
   改,只是回覆品質天差地遠。
2. 幫 `generate_advice` 多加一條規則：根據 `weathercode` 判斷是否為雷雨
   （code 95/96/99）,額外提醒「避免在雷雨時段從事戶外活動」。
3. 把逾時秒數、重試次數改成可以從命令列參數調整（`--timeout`、
   `--retries`),並補上對應的 pytest 測試案例。
