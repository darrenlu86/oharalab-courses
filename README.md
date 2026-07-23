# 台灣天氣資料科學課程

一份資料域、六個階段、貫穿資料科學專案的完整生命週期。

## 定位

這是呂紹民（Darren Lu）給學員的資料科學教學課程範例。用「台灣天氣
資料」當作單一主題,貫穿六個專案階段（對應教學單位的 AI-7 ~ AI-12
專案卡),示範同一份資料域怎麼從 API 串接一路走到端到端系統——階段 1
串接天氣預報 API,階段 2 用同一份歷史資料做探索性分析,階段 3 教你怎麼
自己把資料生產出來（爬蟲）,階段 4/5 用結構化/非結構化資料建模,階段 6
把前面全部串成一個可運行的儀表板系統。

**全本地端**：不需要任何帳號或付費服務。唯一外部資源是 Open-Meteo 免費
天氣 API（無帳號、無金鑰、CC BY 4.0）,所有網路呼叫都有離線備援。

課程設計細節（評分規準、建議時數、前置關係）在
[`docs/CURRICULUM.md`](docs/CURRICULUM.md)；系統架構細節（資料契約、
DB schema、循序圖）在 [`docs/PRD.md`](docs/PRD.md)；資料來源與授權在
[`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md)。

## 六階段地圖

| 階段 | 專案卡 | 主題 | 目錄 |
|---|---|---|---|
| 1 | AI-7 Data/AI 應用案例 | 天氣速報小幫手（API 串接） | [`stage1_api_app/`](stage1_api_app/) |
| 2 | AI-8 資料分析 | 台灣三城市 11 年天氣 EDA | [`stage2_eda/`](stage2_eda/) |
| 3 | AI-9 資料收集與資料庫 | 爬取沙盒氣象站→SQLite | [`stage3_crawler/`](stage3_crawler/) |
| 4 | AI-10 結構型資料分析 | 明日降雨預測＋隔日高溫回歸 | [`stage4_ml_structured/`](stage4_ml_structured/) |
| 5 | AI-11 非結構型資料分析 | 留言情感分類＋手寫數字辨識 | [`stage5_ml_unstructured/`](stage5_ml_unstructured/) |
| 6 | AI-12 真實世界應用系統 | 天氣智慧儀表板（收尾整合） | [`stage6_system/`](stage6_system/) |

每個階段目錄都含：`README.md`（教案本體,含快速開始/逐步教學/為什麼
這樣設計/常見錯誤/驗收 checklist/延伸挑戰）、程式碼、`report.md`
（成果報告,真實跑出來的數字）、`slides.md`（簡報稿）。

建議照 1→2→3→4→5→6 順序做,前置關係細節見
[`docs/CURRICULUM.md`](docs/CURRICULUM.md)。

## 快速開始

```bash
# 1. 建立虛擬環境、安裝套件
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# 2. 建資料庫（三個預設測站）
venv/bin/python scripts/init_db.py

# 3. 跑全部測試，確認環境正常
venv/bin/python -m pytest -q
```

預期輸出：

```
163 passed, 4 warnings in ~20s
```

**注意**：上面的 `~20s` 是 matplotlib 字型快取與 jieba 字典快取都已經建立好之後的
速度。全新環境第一次跑（這些快取都還沒建立）會明顯慢很多——實測從全新 venv
（`pip install` 完、跑完 `init_db.py`）直接執行 `pytest -q`，落在 70~110 秒
（曾實測 72.10s 與 103.49s 兩次，機器負載不同會有差），之後每次重跑同一台機器
才會回到 ~20s。第一次跑久一點是正常現象，不是卡住,不用中斷重跑。

接著可以照六階段順序逐一進入，每個階段的 `README.md` 都有該階段獨立的
快速開始指令。想直接體驗收尾的完整系統：

```bash
venv/bin/python -m stage6_system.pipeline.bootstrap
venv/bin/python -m uvicorn stage6_system.app:app --port 8320
# 打開 http://127.0.0.1:8320/
```

## 專案結構

```
weather-data-science-course/
├── README.md                  # 本檔
├── DEVELOPMENT.md              # 開發者視角：架構、資料流、測試、如何擴充
├── LICENSE                     # MIT
├── requirements.txt
├── docs/                       # 課程設計、系統設計、資料來源
├── data/                       # 真實天氣 CSV + 合成語料 CSV（committed）
├── scripts/                    # 抓資料/生成合成語料/建資料庫
├── common/                     # 路徑與字型 helpers（全課程共用）
├── sandbox_site/                # 教學沙盒網站「福爾摩沙氣象站」（stage3 爬蟲標的）
├── stage1_api_app/ ~ stage6_system/   # 六階段
└── tests/                      # 全 repo 單一 pytest 入口（163 個測試）
```

## 技術棧

Python 3.13（3.11+ 相容）、FastAPI、pandas、scikit-learn、jieba、
matplotlib、SQLite、Chart.js（vendored）。完整版本清單見
`requirements.txt`（每行附行內註解，版本以 `pip show` 實查為準）。

## 已知界線

Open-Meteo 為 ERA5 再分析網格資料，非氣象站觀測；合成留言語料的模型
效能不可外推到真實社群文本；沙盒網站僅供爬蟲教學，與真實網站的反爬蟲
環境有落差；本課程無雲端部署實測。完整清單見各階段 README 的「注意」
小節與 SPEC 原始文件 §9。

## 作者與聯絡資訊

本專案為呂紹民（Darren Lu）製作的教學範例，供學員學習資料科學專案開發使用。如果對本文件或專案有任何問題，或有課程教學、顧問諮詢、專案導入需求，歡迎與我聯絡。

- Email：kevin868686@gmail.com
- LinkedIn：https://www.linkedin.com/in/shaominglu
- Facebook：https://www.facebook.com/darrenlu86

## 授權

MIT License，詳見 [`LICENSE`](LICENSE)。
