# 資料來源與授權

本檔記錄課程用到的兩類資料：真實天氣資料（本階段完成）與合成語料（下一階段補）。
你在任何 stage 引用資料前，先回來這裡確認來源與授權，不要憑印象假設資料是怎麼來的。

## 真實資料：Open-Meteo Historical Weather API

### 來源

- API 名稱：Open-Meteo Historical Weather API（ERA5 再分析歷史天氣資料）
- 端點：`https://archive-api.open-meteo.com/v1/archive`
- 官方文件：https://open-meteo.com/en/docs/historical-weather-api
- 抓取腳本：`scripts/fetch_weather_data.py`（可重跑，`--help` 看參數）

### 完整請求 URL 範例（台北，2015-01-01 ~ 2025-12-31）

```
https://archive-api.open-meteo.com/v1/archive?latitude=25.0330&longitude=121.5654&start_date=2015-01-01&end_date=2025-12-31&daily=temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,rain_sum,precipitation_hours,windspeed_10m_max,windgusts_10m_max,winddirection_10m_dominant,shortwave_radiation_sum&timezone=Asia/Taipei
```

台中與高雄只是把 `latitude`/`longitude` 換成 §「三城市座標」表中對應的值，其餘參數相同。

### 三城市座標與抓取結果

| 城市 slug | 請求座標（lat, lon） | API 回傳網格座標（lat, lon） | CSV 列數（含 header） |
|---|---|---|---|
| taipei | 25.0330, 121.5654 | 25.06151, 121.5194 | 4019（4018 筆資料 + 1 列 header） |
| taichung | 24.1477, 120.6736 | 24.147627, 120.70138 | 4019（4018 筆資料 + 1 列 header） |
| kaohsiung | 22.6273, 120.3014 | 22.671352, 120.31185 | 4019（4018 筆資料 + 1 列 header） |

### daily 變數清單（本次全數支援，未刪減）

SPEC 列出的十個變數：`temperature_2m_max, temperature_2m_min, temperature_2m_mean, precipitation_sum, rain_sum, precipitation_hours, windspeed_10m_max, windgusts_10m_max, winddirection_10m_dominant, shortwave_radiation_sum`。

抓取前先用一段短區間（台北 2025-06-01~03）對 API 實測過，十個欄位全部回傳有效數值，沒有任何一欄回 400 或空陣列，所以正式抓取沒有刪減任何欄位。如果你之後重跑腳本時 API 改版導致某欄消失，腳本會在該次請求收到 400，需要手動從 `DAILY_VARS` 移除該欄，並回來這裡補記錄——目前這份文件不需要這一段，因為沒有發生。

### 擷取時間戳

實際執行 `scripts/fetch_weather_data.py` 完成三城市抓取的時間：

```
2026-07-24 00:01:02 CST (UTC+0800)
```

（用 `date "+%Y-%m-%d %H:%M:%S %Z (UTC%z)"` 指令取得，非估計值。）

### 授權：CC BY 4.0

Open-Meteo API 資料的授權條款，逐字引用自官方頁面 https://open-meteo.com/en/licence：

> API data are offered under Attribution 4.0 International (CC BY 4.0)
>
> You are free to share: copy and redistribute the material in any medium or format and adapt: remix, transform, and build upon the material.
>
> Attribution: You must give appropriate credit, provide a link to the licence, and indicate if changes were made. You may do so in any reasonable manner, but not in any way that suggests the licensor endorses you or your use.
>
> You must include a link next to any location Open-Meteo data are displayed, for example:
> `<a href="https://open-meteo.com/">Weather data by Open-Meteo.com</a>`

官方建議的引用格式（同一頁面，Citation 區塊）：

> Zippenfenig, P. (2023). Open-Meteo.com Weather API [Computer software]. Zenodo. https://doi.org/10.5281/ZENODO.7970649

本課程所有顯示天氣資料的頁面（沙盒站、stage6 儀表板）都要照官方寫法附上 `Weather data by Open-Meteo.com` 連結，這是 CC BY 4.0 的硬性要求，不是可選裝飾。

### 教學點：ERA5 再分析網格點 ≠ 氣象站觀測點

你送出請求座標，API 不會照原樣回傳——它回傳的是離你最近的 ERA5 再分析網格點座標。上面那張表就是實測證據：你請求台北 (25.0330, 121.5654)，API 回傳的卻是 (25.06151, 121.5194)，經緯度都變了。

這不是誤差或 bug，是資料本質的差異：

- **氣象站觀測**：固定地點的實體儀器（溫度計、雨量筒）實測值，例如中央氣象署在台北測站的觀測值，代表「那一個點」的實況。
- **ERA5 再分析網格**：歐洲中期天氣預報中心（ECMWF）用數值模型把全球大氣同化成規則網格（約 0.25 度、實務上約 25~31 公里見方），每個網格點的值是模型算出來的估計值，代表「這個網格範圍」的平均狀態，不是任何單一測站的實測值。

對三個城市來說，這代表你分析的其實是「台北市周邊一塊網格區域的估計天氣」，不是「台北測站當天量到的天氣」。兩者在多數日子會很接近，但在局部強對流（例如午後雷陣雨只下在半個台北市)這種情境下可能有明顯落差——網格模型抓不到這麼小尺度的局部現象。這件事在 stage2 EDA 也要提一次，讓你在解讀降雨資料時保留這個保留。

商用如果要用氣象站實測資料，通常需要付費方案或改接中央氣象署開放資料；本課程用途在 Open-Meteo 免費條款範圍內（非商用、教學用途）。

### Sanity check 紀錄

以下比對用主對話先前已用同一支 API 實測過的台北數值，逐筆對照本次抓取結果，確認沒有捏造或跑錯參數：

```
2025-06-01,31.1,21.8,26.6,0.2,0.2,1.0,12.1,29.2,241,17.27
2025-06-02,33.2,24.6,28.7,0.0,0.0,0.0,18.3,43.2,267,25.0
2025-06-03,30.3,22.8,25.4,38.4,38.4,11.0,10.0,29.9,44,6.0
```

比對結果：

- 2025-06-01 temperature_2m_max = 31.1、temperature_2m_min = 21.8、precipitation_sum = 0.2 —— 與先前實測值完全吻合。
- 2025-06-02 temperature_2m_max = 33.2 —— 與先前實測值完全吻合。
- 2025-06-03 precipitation_sum = 38.4 —— 與先前實測值完全吻合。

另外抽 3 筆與常識比對：

1. **夏冬溫差**（台北）：2025-01-15 溫度 15.5/11.9 度（最高/最低），2025-07-15 溫度 34.2/25.7 度——冬夏溫差約 19 度，符合台灣亞熱帶氣候常識。
2. **高雄冬天比台北暖**：同一天 2025-01-15，台北最高溫 15.5 度、最低 11.9 度；高雄最高溫 18.3 度、最低 14.1 度——高雄兩個數字都比台北高，符合高雄緯度較低、冬季較暖的常識。
3. **無負降雨**：對三城市全部 4018 列的 `precipitation_sum` 欄位逐列檢查，負值筆數皆為 0（`awk` 實測輸出：`negative precip rows: 0` × 3 檔），符合降雨量不可能為負的物理常識。

### 缺值處理原則

CSV 保留 API 回傳原樣，缺值（API 回傳 `null`）以空字串寫入，不做任何填補或估算。本次三城市完整區間抓取結果：三個檔案的十個 daily 欄位皆無缺值（`fetch_weather_data.py` 執行時印出「缺值統計：無缺值」，並經獨立 `awk` 掃描空欄位再次確認為 0）。往後如果重跑腳本抓到有缺值的區間，缺值統計會印在執行輸出裡，處理方式留給下游 stage（例如 stage2 EDA）決定，這裡不先幫你填。

---

## 合成資料

**此語料為程式生成的合成資料（`scripts/generate_synthetic.py`，seed 20260723），非真實網友留言。** 本節記錄實際生成方式與實測數字，不是規劃草稿。

### 生成方式

- 生成腳本：`scripts/generate_synthetic.py`，可重複執行：`venv/bin/python scripts/generate_synthetic.py`。
- 決定性：留言用 `random.Random(SEED)`（`SEED = 20260723`），公告用獨立的 `random.Random(SEED + 1)`；兩者皆是獨立的 `Random` 實例，不吃 Python 全域 `random` 模組狀態。已實測連續執行兩次，`comments.csv` 與 `announcements.csv` 的 MD5 完全相同（`f9c30774785edcf1a657c53279ab51f4` / `8ce582a64b001952e3f61893adf8790d`），確認輸出逐 byte 一致。
- 留言的 `city`/`date` 一律從 `data/raw/*.csv` 裡 2023-01-01~2025-12-31 區間的真實觀測值取樣（3 城市 × 1096 天 = 3288 筆候選池），依當天實際天氣分類決定留言語氣的抽樣權重：
  - 雨天（`precipitation_sum >= 1.0mm`，與 stage4 雨天定義一致）→ 提高負面 rating（1、2）的抽樣權重，模板多為潮濕/積水抱怨。
  - 高溫日（`temperature_2m_max >= 33.0°C`）→ 提高負面 rating 的抽樣權重，模板多為悶熱/曬傷抱怨。
  - 舒適日（`temperature_2m_max` 落在 22~29°C 且非雨天）→ 提高正面 rating（4、5）的抽樣權重，模板多為涼爽/舒服的正面描述。
  - 其餘天氣歸為「一般」類，四種 rating 權重較平均。
  - 這是權重而非硬規則：同一天氣類型底下仍保留全部 5 種 rating 的模板，屬「鬆散相關」而非強制對應。
- 內容組成：`開場語助詞（10 種，含空字串）+ 模板（依「天氣類型 × rating」分 20 組、每組 2~5 種寫法）+ 語尾標點/語助詞（10 種，含空字串）`，部分模板另外內嵌當天實際最高溫數值（如「氣溫飆破 33.2 度」），增加內容與真實天氣的連結與文字多樣性。
- 逐字重複檢查：生成時用 `Counter` 追蹤每則內容出現次數，超過 3 次會強制重新抽開場/模板/語尾組合；腳本執行時會印出「單一內容最大重複次數」供人工核對。

### 規模與實測分布（2026-07-24 實際執行輸出）

- `comments.csv`：2400 筆（含 header 共 2401 行）。
- rating 分布（實測 = 目標，因 2400 × 8/12/15/35/30% 皆為整數）：

  | rating | 筆數 | 實測百分比 | 目標百分比 |
  |---|---|---|---|
  | 1 | 192 | 8.00% | 8% |
  | 2 | 288 | 12.00% | 12% |
  | 3 | 360 | 15.00% | 15% |
  | 4 | 840 | 35.00% | 35% |
  | 5 | 720 | 30.00% | 30% |

- city 分布（實測）：`taipei` 732 筆、`taichung` 820 筆、`kaohsiung` 848 筆（差異來自各城市雨天/高溫日/舒適日在真實資料裡的天數本來就不均：例如高雄的高溫日只有 12 天，遠少於台北的 116 天）。
- 內容長度範圍：13~26 字（要求 8~60 字，實測沒有觸到上下限；模板＋語助詞組合出的內容天生偏短，不影響教學用途，但這是模板設計的實際侷限，如實記錄不誇大）。
- 不重複內容數：1824（總筆數 2400），單一內容最大重複次數：3（上限 3，符合 SPEC §3.2）。
- `announcements.csv`：30 筆（含 header 共 31 行），`ann_id` 為 `a01`~`a30`，`published_at` 落在 2024-01-01~2025-12-31 之間，內文長度實測範圍 100~300 字內（本次執行 112~294 字）。

### 用途

- `data/synthetic/comments.csv` 是 stage3_crawler 的 `/comments` 分頁爬蟲教學標的（透過 sandbox_site），也是 stage5_ml_unstructured 案例 A（天氣留言情感二元分類，排除 rating=3）的訓練語料。
- `data/synthetic/announcements.csv` 是 stage3_crawler 的「列表→詳情」兩層爬取教學標的（`/announcements` 與 `/announcements/{ann_id}`）。

### 明確標示：非真實資料

以上兩份 CSV 全部欄位（包含留言文字、rating、公告標題與內文）都是 `generate_synthetic.py` 用固定 seed 跑模板生成，**不是任何真人撰寫的內容**，不能當作真實社群意見或真實公告使用。stage5 教案會再強調一次：用合成語料訓練出來的情感分類模型，效能數字必然偏樂觀（模型學到的是生成模板的規律，不是真實語言的複雜度），不可外推到真實社群文本上的表現。
