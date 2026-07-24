# AI 與網站工程教案合集

呂紹民（Darren Lu）給學員的教學課程範例合集。四份教案各自獨立、完整、可在本機跑通，不需要付費雲端服務；可以只挑一份做，也可以整套照順序學。

每份教案原本是獨立的 GitHub repo，2026-07 以 `git subtree` 併入本 repo 的子資料夾，全部 commit 歷史完整保留。教案之間沒有共用程式碼或依賴，虛擬環境與套件各自安裝。

## 教案地圖

| 資料夾 | 教案 | 主題 | 主要技術 | 對應課綱 |
|---|---|---|---|---|
| [`weather-data-science/`](weather-data-science/) | 台灣天氣資料科學課程 | 一份資料域、六個階段：API 串接 → EDA → 爬蟲入庫 → 結構化/非結構化建模 → 儀表板系統 | Python、pandas、scikit-learn、SQLite、Open-Meteo API | AI-7 ~ AI-12 |
| [`web-engineering/`](web-engineering/) | 網站工程六階段實戰（沖沖咖啡 BrewGo） | 同一個電商品牌從一頁式靜態頁做到含即時推播與壓測的完整平台 | HTML/CSS/JS、React + Vite、FastAPI + SQLite、WebSocket/SSE、locust | WEB-13 ~ WEB-18 |
| [`tsmc-stock-analysis/`](tsmc-stock-analysis/) | 台積電股票分析教學專案 | 資料庫設計與網路爬蟲：三支爬蟲入庫，唯讀 Dashboard 視覺化 | Python 爬蟲、SQLite（可切 Supabase）、Repository Pattern | — |
| [`meowshop/`](meowshop/) | MeowShop 喵喵商店 | 全端電商完整流程：註冊 → 逛商品 → 購物車 → 下單 → 模擬付款 | 原生 JS 前端、FastAPI、SQLite（可切 Supabase） | — |

## 使用方式

```bash
git clone https://github.com/darrenlu86/ai-web-courses.git
cd ai-web-courses/<教案資料夾>
```

之後照各教案自己的 README 走。每份教案（以及 `web-engineering/` 底下的每個 stage）都是獨立專案，安裝與啟動方式在各自的 README 裡。

## 共同注意事項

- 四份教案都是**教學範例，不是可直接營運的產品**。程式碼優先考慮好理解、好教學；刻意簡化之處各教案 README 都有說明。
- `web-engineering/` 與 `meowshop/` 的付款功能是**自建模擬金流**，沒有串接任何真實金流服務，不會有真實金錢往來，請勿原樣拿去對外收費。
- `tsmc-stock-analysis/` 的資料僅供教學與研究用途，爬蟲倫理與免責聲明見該教案 README 文末。

## 作者與聯絡資訊

如果對教案內容有任何問題，或有課程教學、顧問諮詢、專案導入需求，歡迎與我聯絡。

- 作者：呂紹民（Darren Lu）
- Email：kevin868686@gmail.com
- LinkedIn：https://www.linkedin.com/in/shaominglu
- Facebook：https://www.facebook.com/darrenlu86

## 授權

`weather-data-science/`、`web-engineering/`、`meowshop/` 為 MIT License（各資料夾內附 LICENSE）；`tsmc-stock-analysis/` 未附授權條款，使用範圍依其 README 的免責聲明（僅供教學與研究用途）。
