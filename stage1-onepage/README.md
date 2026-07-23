# Stage 1 — 一頁式靜態網頁（WEB-13）

回上層：[網站工程六階段課程總覽](../README.md)

沖沖咖啡 BrewGo 開幕倒數活動頁：一個檔案結構最簡單、零依賴、零 build step 的一頁式網頁，用 HTML 語意化、CSS 響應式排版與 JS 基礎互動，做出一個「可以實際上線」的品牌開幕頁。

> 本專案是教學範例。頁面上的訂閱表單是純前端展示，**填了不會有任何資料真的送出去**（見「教學簡化聲明」與頁面上的誠實標示）；門市地址、優惠內容為虛構教學情境。

## 這一階段你會做出什麼

一個單頁網頁（`index.html`），由上而下依序是：

- 導覽列：logo＋錨點連結，行動版收合成漢堡選單
- Hero：品牌名、tagline、開幕倒數計時器（天/時/分/秒），過期會自動切換成「已盛大開幕」
- 品牌故事：文案＋SVG 插圖
- 招牌選品：4 張商品卡（純展示，無購買功能）
- 開幕優惠：3 張固定優惠卡
- FAQ：5 題手風琴（accordion），鍵盤可操作
- 門市資訊：地址、營業時間、SVG 手繪示意地圖
- 訂閱表單：email＋姓名，前端驗證，純前端 mock
- Footer：品牌資訊＋課程範例聲明

全部功能都是純 HTML/CSS/JS，沒有任何框架、函式庫、CDN 或後端，`file://` 直接開啟也能完整運作。

## 對應課綱與交付產出

課綱原文（WEB-13）：「從 HTML 語意化、CSS 響應式排版、JS 基礎功能到靜態部署，完成一個可實際上線的一頁式靜態網頁。完成後產出：含關鍵程式片段的程式碼結構說明、可存取的線上部署連結、含桌機/平板/手機呈現的設計說明文件。」

| 產出要求 | 對應本 repo 位置 |
|---|---|
| 一頁式靜態網頁本身 | `index.html`、`css/style.css`、`js/main.js`、`images/` |
| 產出 1：含關鍵程式片段的程式碼結構說明 | [`docs/CODE_GUIDE.md`](docs/CODE_GUIDE.md) |
| 產出 2：可存取的線上部署連結 | 課程本身不代學員部署 → [`docs/DEPLOY.md`](docs/DEPLOY.md) 提供本地驗證（已實測）＋主流平台部署教學＋學員交付檢查表，由學員部署後自行填上連結 |
| 產出 3：含桌機/平板/手機呈現的設計說明文件 | [`docs/DESIGN.md`](docs/DESIGN.md) |

## 與上一階段的差異

從零開始。Stage 1 是本課程六個階段的第一個階段，沒有「上一階段」可以比較——這裡直接建立整個課程共用的品牌視覺語言（色彩／字體 tokens）與商品型錄資料，後面五個階段都會沿用同一套視覺語言與商品資料，只是網站的複雜度逐階段疊加（多頁面 → 前端互動 → 後端 API → 完整前後台 → 即時通訊/效能）。

## 課綱單元表

| 單元 | 學什麼 | 對應檔案 |
|---|---|---|
| 1. HTML 語意化 | `header`/`nav`/`main`/`section`/`footer`、標題階層、`img alt`、`label` 對應 `input` | `index.html` 全檔，逐段說明見 [`CODE_GUIDE.md` 第 3 節](docs/CODE_GUIDE.md) |
| 2. CSS 響應式 | mobile-first、三斷點、flexbox 與 grid 分工、相對單位、平滑捲動（`scroll-behavior`） | `css/style.css`（平滑捲動見約 47 行），說明見 [`CODE_GUIDE.md` 2.5 節](docs/CODE_GUIDE.md)、[`DESIGN.md`](docs/DESIGN.md) |
| 3. JS 基礎 | DOM 選取與事件、倒數計時邊界處理、accordion、表單驗證 | `js/main.js`，逐段說明見 [`CODE_GUIDE.md` 第 2 節](docs/CODE_GUIDE.md) |
| 4. 靜態部署概念 | 什麼是靜態網頁、為什麼不需要伺服器程式、本地預覽 | [`docs/DEPLOY.md`](docs/DEPLOY.md) |

## 環境需求

- 一個現代瀏覽器（Chrome／Firefox／Safari／Edge 皆可）
- 想用本地伺服器預覽（非必要）：Python 3.10 以上（本次建置實測環境為 Python 3.13.11，用內建的 `http.server` 模組，不需要額外安裝任何套件）
- 不需要 Node.js／npm 才能「看」這個頁面；本文件用 `node --check` 只是輔助驗證 JS 語法沒有寫錯，不是執行網頁的必要條件

## 快速開始

以下每一步都附上實際執行的預期輸出。

**1. 進入資料夾**

```bash
cd stage1-onepage
```

**2a. 方式一：直接雙擊 `index.html`**

用瀏覽器打開即可，不需要任何指令。

**2b. 方式二：啟動本地伺服器**

```bash
python3 -m http.server 8081
```

預期輸出：

```
Serving HTTP on :: port 8081 (http://[::]:8081/) ...
```

打開瀏覽器 [http://localhost:8081](http://localhost:8081)，應該會看到 Hero 區塊（品牌名「沖沖咖啡 BrewGo」＋倒數計時），往下捲動能看到品牌故事、招牌選品、開幕優惠、FAQ、門市資訊、訂閱表單、Footer 共 7 個區塊。

**3. 驗證頁面正常回應（實測輸出）**

```bash
$ curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/
200
```

## 逐步教學導覽

建議按下面順序讀程式碼，每個單元都會用到前一個單元的知識：

1. **先看 `index.html` 的整體骨架**：`<header>`（17 行起）→ `<main>` 裡 7 個 `<section>`（49 行起）→ `<footer>`（364 行起）。留意每個 `<section>` 都用 `aria-labelledby` 指向自己的標題 id，這是「語意區塊」與「無障礙可辨識的章節」兩件事一起做到的寫法。

2. **再看 `css/style.css` 的 tokens 區塊**（1-37 行）：所有顏色、字體、間距都先定義成 CSS 自訂屬性（`--color-primary` 這種），後面的規則全部引用這些變數，不直接寫死色碼——換色只要改這裡一處。

3. **看響應式排版怎麼疊加**：先看 `.product-grid`（318-322 行，手機版 2 欄），再看 `@media (min-width: 768px)`（614-616 行，平板 3 欄）與 `@media (min-width: 1024px)`（629-631 行，桌機 4 欄）。這是 mobile-first 疊加的具體範例，詳細講解見 [`docs/CODE_GUIDE.md` 2.4 節](docs/CODE_GUIDE.md)。

4. **最後看 `js/main.js` 的四個函式**：`initNavToggle`（15-34 行）→ `initCountdown`（46-82 行，重點看 60-66 行怎麼處理「已過開幕時間」的邊界）→ `initAccordion`（91-110 行）→ `initSubscribeForm`（120-187 行）。每個函式開頭都會先檢查自己需要的 DOM 元素存不存在（`if (!wrapper) return;` 這種寫法），這樣就算某個區塊被拿掉，其他功能也不會跟著壞掉。

完整的程式碼片段與逐段講解在 [`docs/CODE_GUIDE.md`](docs/CODE_GUIDE.md)；三裝置版面差異與色彩對比實測數據在 [`docs/DESIGN.md`](docs/DESIGN.md)。

## 驗收清單

- [ ] `index.html` 語意化標籤齊全（`header`/`nav`/`main`/`section`×7/`footer`），`lang="zh-Hant"`
- [ ] 手機（<768px）、平板（768-1023px）、桌機（≥1024px）三種寬度下版面都正常，商品卡欄數依序是 2/3/4 欄
- [ ] 開幕倒數計時每秒跳動，倒數歸零後改顯示「已盛大開幕」（已用 node 腳本驗證邊界換算邏輯，見 [`CODE_GUIDE.md` 2.1 節](docs/CODE_GUIDE.md)）
- [ ] FAQ 手風琴可以用滑鼠點擊、也可以用鍵盤（Tab 移到按鈕、Enter/Space 觸發）展開與收合
- [ ] 訂閱表單：姓名或 email 留空、email 格式錯誤都會顯示對應錯誤訊息；兩者都填對後顯示成功訊息
- [ ] 對比、focus 樣式、`aria-expanded` 等 a11y 項目已落實（詳見 [`docs/DESIGN.md`](docs/DESIGN.md) 第 5 節）
- [ ] 零依賴、零 CDN，`file://` 直接開啟可正常運作
- [ ] `docs/CODE_GUIDE.md`、`docs/DESIGN.md`、`docs/DEPLOY.md` 三份文件齊全

## 延伸挑戰

不提供解答，留給學員自己練習：

1. 幫導覽選單的展開/收合加上平滑的高度過渡動畫（提示：純 CSS `max-height` 過場或 CSS `transition` 搭配 `grid-template-rows` 都是可行方向，各有取捨）。
2. 幫倒數計時器加上「小於 24 小時時字體變色提醒」的效果，練習用 JS 依條件動態切換 class。
3. 把 FAQ 題目改成可以透過網址錨點（例如 `#faq-panel-3`）直接連到並自動展開對應那一題，練習讀取 `location.hash`。
4. 幫訂閱表單的 email 欄位加上「打字過程即時檢查格式」（目前是欄位失焦 `blur` 才驗證一次），要留意「使用者還沒打完就一直跳錯誤訊息」這種體驗上的取捨。

## 教學簡化聲明

- **訂閱表單是純前端 mock**：填寫送出後資料不會被儲存、也不會寄出任何信件，純粹展示前端表單驗證的寫法。真的能收到通知的訂閱功能需要一支後端 API，這是 stage4 起才會做的事。頁面上（`index.html` 訂閱區塊）與 FAQ 都有重複標示這件事，避免學員誤以為畫面顯示成功就等於資料真的送出去了。
- **招牌選品純展示，沒有購買功能**：本階段的商品卡只顯示名稱/價格/描述，沒有「加入購物車」按鈕。購物車與下單流程要等到有前端框架與狀態管理（stage3 起）、以及後端庫存/訂單 API（stage4 起）才有意義，太早加會變成沒有實際邏輯的假按鈕，對學員理解反而是誤導。
- **email 格式驗證是簡化版規則**：只檢查「有 @、@ 前後都有字元、結尾有網域」，不是完整的 RFC 5322 規格（連很多正式產品都做不到 100% 正確）。教學上這樣已經足夠擋掉最常見的手誤。
- **手風琴與導覽選單刻意不做展開動畫**：直接用 `hidden` 屬性／`display: none`/`block` 切換，沒有過場效果。這是刻意的取捨——本階段的教學重點是「邏輯要對」（`aria-expanded` 與實際顯示狀態一致），動畫效果留給延伸挑戰讓學員自己加，避免第一版程式碼疊加太多複雜度。
- **門市地圖是手繪 SVG 示意圖，不是真實地圖**：正式產品通常會嵌入 Google Maps 等地圖服務的 iframe，但本課程堅持零外部服務、零 CDN 的原則（`file://` 也要能完整運作），因此改用手繪示意圖，並在頁面與圖片 `alt`／`title` 中明確標示這是示意圖。
- **a11y 檢查已用工具與邏輯檢查，未經螢幕閱讀器實機測試**：對比比率是程式精確計算的實測數據；`aria-expanded`／鍵盤操作是依照 WAI-ARIA 慣用模式撰寫並人工檢查程式邏輯，但沒有實際用 VoiceOver/NVDA 朗讀測試過，詳見 [`docs/DESIGN.md`](docs/DESIGN.md) 第 5 節的誠實聲明。

## 作者與聯絡資訊

本專案為呂紹民（Darren Lu）製作的教學範例，供學員學習網站工程使用。如果對本文件或專案有任何問題，或有課程教學、顧問諮詢、專案導入需求，歡迎與我聯絡。

- Email：kevin868686@gmail.com
- LinkedIn：https://www.linkedin.com/in/shaominglu
- Facebook：https://www.facebook.com/darrenlu86
