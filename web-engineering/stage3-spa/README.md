# Stage 3 — 互動式動態網頁·純前端（WEB-15）

回上層：[網站工程六階段課程總覽](../README.md)

BrewGo 沖沖咖啡「線上選購」純前端 SPA：用 React + Vite 打造含元件、跨頁共享狀態管理與第三方 API 串接的互動式商店 demo，資料全部存在使用者自己瀏覽器裡，還沒有後端。

> 本專案是教學範例。**沒有金流、沒有後端、沒有真實訂單**：結帳「送出訂單」只是把資料存進你目前這台裝置瀏覽器的 `localStorage`，不會有任何商品真的出貨、也不會有任何金錢往來。換一台裝置或清除瀏覽器資料，購物車與訂單紀錄就會全部消失——這個限制正是下一階段（stage4，含後端）要解決的問題，詳見下方「與上一階段的差異」。

## 這一階段你會做出什麼

一個可以完整操作的線上選購 SPA（單頁應用程式），包含：

- **商品列表**：分類 tab（咖啡豆／掛耳包／沖煮器具／杯具／禮盒）＋關鍵字搜尋同時生效，庫存徽章（現貨供應／僅剩 N 件／補貨中），補貨中的商品無法加入購物車
- **商品詳情頁**：完整規格說明、數量選擇器（上限＝庫存）、加入購物車
- **購物車**：改數量／移除／即時重算小計與總計、空車狀態、header 徽章即時顯示總數量——全站共享同一份狀態
- **結帳**：收件人表單（姓名／手機／地址驗證）→ 產生 `BG-XXXXXXXX` 格式訂單編號 → 存進 localStorage → 訂購完成頁
- **我的訂單**：查詢本機曾經下過的所有訂單
- **外幣參考價**：串接免金鑰的公開匯率 API，商品價格旁可切換顯示 USD／JPY 參考價，API 失敗時自動退回內建的離線參考匯率，網站其他功能完全不受影響
- 響應式版面（手機／平板／桌機）

## 對應課綱與交付產出

課綱原文（WEB-15）：「使用前端框架完成一個含元件、狀態管理與第三方 API 串接的互動式動態網頁。完成後產出：含框架/分層/狀態管理的前端專案架構說明、可實際操作互動功能的部署連結、含 API 串接流程與錯誤處理的技術文件。」

| 產出要求 | 對應本 repo 位置 |
|---|---|
| 互動式動態網頁本身（元件／狀態管理／第三方 API） | `src/` 全目錄，見下方「逐步教學導覽」 |
| 產出 1：含框架/分層/狀態管理的前端專案架構說明 | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| 產出 2：可實際操作互動功能的部署連結 | 課程本身不代學員部署 → [`docs/DEPLOY.md`](docs/DEPLOY.md) 提供本地驗證（已實測）＋主流平台部署教學＋學員交付檢查表，由學員部署後自行填上連結 |
| 產出 3：含 API 串接流程與錯誤處理的技術文件 | [`docs/API_INTEGRATION.md`](docs/API_INTEGRATION.md) |

## 與上一階段的差異

Stage2（多頁式靜態網站）用純 HTML/CSS/JS 做出了可以逛的多頁商店，但完全沒有「購物車」這種需要跨頁共享、且會頻繁變化的狀態；當時的每一頁都是獨立的 HTML 檔案，換頁等於瀏覽器重新載入一份全新的 document，前一頁 JS 裡的變數全部歸零。

Stage3 引入前端框架來解決三個 stage2 撐不住的地方：

1. **跨頁共享狀態**：購物車數量在 Header、Cart 頁、ProductDetail 頁必須即時一致。做法是用 React Context（`CartContext`）搭配 `useReducer` 集中管理，所有元件讀寫的都是同一份記憶體內的狀態，不再需要手動同步好幾份 DOM。
2. **元件化與可複用性**：商品卡、庫存徽章、數量選擇器等 UI 片段在好幾個頁面重複出現，寫成 React 元件後只需要維護一份，不再是複製貼上 HTML 片段。
3. **第三方 API 串接與狀態管理的結合**：新增了「呼叫外部匯率 API」這件事，需要處理 loading／成功／失敗三種狀態並反映在畫面上——這在純 JS 手動操作 DOM 的世界裡會寫得很凌亂，用 React 的 state／hook 處理起來乾淨很多。

**代價（誠實聲明，也是下一階段的入口）**：本階段仍然沒有後端，商品資料是打包進前端的靜態 JSON、購物車與訂單都存在使用者自己瀏覽器的 `localStorage`。這代表：換一台裝置看不到自己的購物車與訂單、沒有真正的庫存管理（兩個人「同時」搶購同一件僅剩 3 件的商品，兩邊都會各自以為自己買得到，因為彼此的瀏覽器互相看不到對方的操作）、也沒有真正的付款。這些問題都需要一個真正的後端與資料庫才能解決——這正是 stage4（互動式動態網頁·含後端）要處理的範圍。

## 課綱單元表

| 單元 | 學什麼 | 對應檔案 |
|---|---|---|
| 1. 前端框架基礎 | Vite 專案結構、元件、JSX、props | `src/components/`、`src/pages/`，說明見 [`ARCHITECTURE.md` 第 2-3 節](docs/ARCHITECTURE.md) |
| 2. 路由 | `react-router-dom`：多頁路由、動態參數（`:id`）、query string、404 | `src/App.jsx`、`src/pages/Products.jsx`，說明見 [`ARCHITECTURE.md` 第 6 節](docs/ARCHITECTURE.md) |
| 3. 狀態管理 | Context + useReducer、集中式 reducer、purity 與可測試性 | `src/context/`，說明見 [`ARCHITECTURE.md` 第 4 節](docs/ARCHITECTURE.md) |
| 4. 資料持久化 | localStorage 讀寫、跟 React state 同步 | `src/context/CartContext.jsx`、`src/utils/ordersStorage.js` |
| 5. 第三方 API 串接 | fetch、loading/成功/失敗三態、fallback 策略 | `src/hooks/useExchangeRate.js`，完整說明見 [`API_INTEGRATION.md`](docs/API_INTEGRATION.md) |
| 6. 表單與驗證 | controlled input、送出前驗證、錯誤訊息呈現 | `src/pages/Checkout.jsx` |
| 7. 元件測試 | Vitest + Testing Library：純函式測試、元件渲染測試、互動測試、mock fetch | `src/**/*.test.{js,jsx}` |
| 8. SPA 部署概念 | build 產物、SPA fallback routing、build-time 環境變數 | [`DEPLOY.md`](docs/DEPLOY.md) |

## 環境需求

- Node.js **20 以上**（本次建置實測環境為 **v24.11.1**，npm **11.6.2**）
- 一個現代瀏覽器

## 快速開始

以下每一步都附上實際執行的預期輸出，指令假設你已經 `cd stage3-spa`。

**1. 安裝套件**

```bash
npm install
```

預期輸出（節錄，實測於乾淨重裝環境）：

```
added 117 packages, and audited 118 packages in 3s
...
found 0 vulnerabilities
```

套件數與秒數會隨相依套件版本與網路環境浮動，以你實際看到的為準。

**2. 跑測試**

```bash
npm test -- --run
```

預期輸出：

```
 Test Files  8 passed (8)
      Tests  35 passed (35)
```

**3. 啟動開發伺服器**

```bash
npm run dev
```

預期看到終端機印出本地網址（通常是 `http://localhost:5173/`），瀏覽器打開應該會看到 BrewGo 首頁（hero 區塊＋分類快速入口＋精選商品）。

**4. 打包成正式版靜態檔案**

```bash
npm run build
```

預期輸出（節錄，實測記錄於 [`docs/DEPLOY.md`](docs/DEPLOY.md)）：

```
dist/index.html                   0.65 kB │ gzip:  0.45 kB
dist/assets/index-iia0sqIS.css    9.97 kB │ gzip:  2.33 kB
dist/assets/index-DM2FPoAx.js   255.49 kB │ gzip: 81.21 kB

✓ built in 104ms
```

## 逐步教學導覽

1. **入口與全域 Provider**：[`src/main.jsx`](src/main.jsx) 把 `App` 包在 `BrowserRouter` → `ExchangeRateProvider` → `CartProvider` 三層裡；順序有意義——`ExchangeRateProvider` 跟 `CartProvider` 都要在 `App` 之外才能讓所有頁面共用同一份狀態。
2. **路由表**：[`src/App.jsx:19-26`](src/App.jsx#L19) 用 `<Routes>`／`<Route>` 定義 8 個路徑，對照到 `src/pages/` 底下的 8 個頁面元件。
3. **購物車的核心邏輯**：[`src/context/cartReducer.js:16`](src/context/cartReducer.js#L16) 的 `ADD_ITEM` 分支——重複加入同一件商品會累加數量、但用 `Math.min(existing.quantity + quantity, product.stock)` 卡住庫存上限，這是「防呆設計」的具體實作，對應測試在 [`cartReducer.test.js`](src/context/cartReducer.test.js)。
4. **狀態如何變成全站共享＋持久化**：[`src/context/CartContext.jsx:30`](src/context/CartContext.jsx#L30) 用 `useReducer` 的第三個參數（lazy init）從 `localStorage` 讀回上次的購物車內容；[`CartContext.jsx:36`](src/context/CartContext.jsx#L36) 的 `useEffect` 則是每次 `state.items` 變化就寫回 `localStorage`。
5. **第三方 API 三態處理**：[`src/hooks/useExchangeRate.js:28`](src/hooks/useExchangeRate.js#L28) 發出請求，[`useExchangeRate.js:41`](src/hooks/useExchangeRate.js#L41) 的 `catch` 統一處理三種失敗情境（斷網／非 2xx／格式跑掉），全部退回內建的 `FALLBACK_RATES` 並標記 `isFallback = true`。完整流程圖與錯誤處理策略表在 [`docs/API_INTEGRATION.md`](docs/API_INTEGRATION.md)。
6. **分類篩選用 URL 記錄狀態**：[`src/pages/Products.jsx:12`](src/pages/Products.jsx#L12) 用 `useSearchParams` 而不是單純的元件內部 state，讓「分類快速入口」的連結可以分享／加書籤。
7. **表單驗證**：[`src/pages/Checkout.jsx:15`](src/pages/Checkout.jsx#L15) 的 `validate(form)` 是一支獨立的純函式，送出前先跑驗證、有錯誤就整批塞進 `errors` state 顯示在對應欄位下方，不送出訂單。
8. **mock 訂單如何產生**：[`src/pages/Checkout.jsx:61`](src/pages/Checkout.jsx#L61) 組出訂單物件（含 `generateOrderId()` 產生的 `BG-XXXXXXXX` 編號），存進 `localStorage` 後清空購物車、導向訂單完成頁。

## 驗收清單

- [x] 商品列表：分類 tab＋關鍵字搜尋同時生效，庫存徽章三態，補貨中無法加入購物車
- [x] 商品詳情：規格、數量選擇（上限＝庫存）、加入購物車
- [x] 購物車：改數量／移除／小計總計、空車狀態、header 徽章跨頁即時同步
- [x] 結帳：表單驗證、訂單編號 `BG-<8碼>`、存 localStorage、完成頁、mock 聲明清楚標示
- [x] 訂單查詢頁：列出本機 localStorage 訂單
- [x] 第三方 API：匯率顯示三態（loading／成功／離線 fallback），fallback 有清楚標示
- [x] 響應式版面（手機／平板／桌機）
- [x] 測試 ≥15 個且全綠（實測 35 個，見上方「快速開始」）
- [x] 測試不打真網路（`vi.stubGlobal` 模擬 fetch）
- [ ] 部署到你選擇的靜態平台（見 [`docs/DEPLOY.md`](docs/DEPLOY.md) 學員交付檢查表，由學員自行完成）

## 延伸挑戰

1. 幫 `Products` 頁的關鍵字搜尋也加進 URL query string（例如 `?category=beans&search=耶加`），讓搜尋條件也能被分享連結還原——需要處理「使用者打字時不要每個字都立刻改網址」的 debounce 問題。
2. 目前 `PriceTag` 的外幣切換是每個元件自己的 `useState`（互不影響）；試著改成「全站只有一個目前選定幣別」的共用狀態，切一次全站商品卡都跟著換。
3. 幫購物車加上「數量輸入框可以直接打字」的功能（現在只能點 +/− 按鈕），並處理使用者打非數字或超過庫存時的防呆。
4. 目前庫存徽章的「低庫存」門檻寫死在 `StockBadge.jsx` 是 5，試著把它改成可以依商品分類設定不同門檻（例如禮盒類商品門檻設 3）。

## 教學簡化聲明

- **沒有後端、沒有真實金流**：結帳「送出訂單」只是把資料存進使用者自己瀏覽器的 `localStorage`，不會扣款、不會出貨。真實電商至少需要後端驗證庫存與價格（不能只信任前端傳來的金額）、真正的金流串接與 webhook 回呼確認付款狀態。
- **庫存快照，不是即時查詢**：加入購物車當下的商品庫存數字會被存進購物車項目裡當作該項目的數量上限（見 `cartReducer.js` 開頭註解）。這在「商品資料是本地固定 JSON、不會被其他人同時改動」的前提下是安全的；一旦有真正的後端與多人同時操作，庫存上限就必須即時向後端查詢，不能再用加入當下的快照。
- **匯率 fallback 是某個時間點的快照，不是即時匯率**：離線參考匯率是 2026-07-23 實際呼叫 API 記錄下來的一組數字，寫死在程式碼裡；匯率會隨時間變動，畫面上用「離線參考匯率」字樣明確標示，避免使用者誤以為那是即時匯率。
- **訂單編號用 `Math.random()` 產生，不保證全域唯一**：這在「每個人的訂單都只存在自己瀏覽器裡」的前提下夠用（不同人的瀏覽器不會互相比對編號），但不是真正資料庫等級的唯一性保證；真實後端會用資料庫的自增 ID 或 UUID。
- **`useExchangeRate` 沒有做 `AbortController` 取消請求**：這是為了讓教學程式碼盡量單純；真實產品在元件卸載後如果請求還沒完成，理想上應該取消請求，避免對已經卸載的元件呼叫 state 更新（這個警告從 React 18 起就已經移除，React 19 沿用同樣行為，但取消未完成的請求仍然是比較嚴謹的做法）。

## 作者與聯絡資訊

本專案為呂紹民（Darren Lu）製作的教學範例，供學員學習前端框架開發使用。如果對本文件或專案有任何問題，或有課程教學、顧問諮詢、專案導入需求，歡迎與我聯絡。

- Email：kevin868686@gmail.com
- LinkedIn：https://www.linkedin.com/in/shaominglu
- Facebook：https://www.facebook.com/darrenlu86
