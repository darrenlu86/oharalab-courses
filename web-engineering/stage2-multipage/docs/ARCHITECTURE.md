# 共用元件架構說明

BrewGo 官方網站有 10 個頁面，每個頁面都要有一模一樣的導覽列（header）和頁尾（footer）。
這份文件講三件事：(1) 共用元件有哪三條路可以做、(2) 本站選了哪一條、為什麼、(3) 這個選擇的限制在哪裡。

## 1. 共用元件的三條路

### (a) 每頁複製貼上

把 header、footer 的 HTML 原封不動貼進每一個 `.html` 檔案。

- **優點**：最簡單，零額外機制，開啟任何一個檔案都能單獨看懂。
- **缺點（教學重點）**：BrewGo 站有 10 個頁面。如果哪天要在導覽列多加一個「優惠活動」連結，
  就要打開 10 個檔案、改 10 次。只要漏改一個，那個頁面的導覽列就會跟其他頁不一致——
  這是本課程 stage1（一頁式網站）撐得住、但 stage2（多頁式網站）一開始就會踩到的維護痛點，
  也是「為什麼需要共用元件」這件事第一次變得重要的地方。

### (b) JS fetch include（本站採用）

把 header、footer 各自存成獨立檔案（`partials/header.html`、`partials/footer.html`），
每個頁面只放一個 `<div data-include="partials/header.html"></div>` 佔位，
由 `js/include.js` 在頁面載入時用 `fetch()` 把內容抓回來塞進頁面。

- **優點**：改導覽列只要改 `partials/header.html` 一個檔案，10 個頁面全部一起變。
  不需要任何建置工具，開發環境跟正式環境是同一份原始碼。
- **缺點（本站已知限制，見下面「限制」一節）**：`fetch()` 讀本機檔案時，
  瀏覽器要求頁面必須是透過 `http://` 或 `https://` 載入，不能用 `file://` 直接雙擊開啟；
  而且每個頁面在瀏覽器真正畫出內容之前，會有一個「先看到空白 header/footer，
  再瞬間補上內容」的短暫閃爍（本站頁面內容量小，實測幾乎感覺不到，但這是這個做法的已知代價）。

### (c) 建置工具／樣板引擎

用 Eleventy、Astro 這類靜態網站產生器，或至少一個樣板引擎，
在「寫程式的時候」就把 header/footer 組進每一頁，輸出成最終的純 HTML 檔案。

- **優點**：沒有前面兩條路的缺點——header 只寫一次、輸出的檔案又是完整的靜態 HTML，
  瀏覽器不需要額外發一次 fetch 請求，也不受 `file://` 限制。
  正式產品幾乎都會走這條路。
- **本站不採用的原因**：需要安裝 Node.js 套件、跑建置指令，才能把原始檔變成看得到的網站；
  這對「剛學會 HTML/CSS/JS 基礎」的學員來說是新的複雜度來源，而本階段的教學重點是
  「先看懂共用元件在解決什麼問題」，不是「先學會操作建置工具」。
  **這也是 stage3 一開始就要換成 Vite + React 的原因之一**——multipage 的網站規模一旦繼續變大
  （想像 30 個頁面、需要共用的不只 header/footer 還有整個商品卡片元件），
  做法 (b) 的效益會被它的缺點（閃爍、額外請求數、沒有真正的元件參數）追過去，
  做法 (c) 的建置工具就變成划算的投資。

## 2. 本站的實作方式

每個頁面的 `<body>` 開頭與結尾各放一個佔位 `<div>`：

```html
<div data-include="partials/header.html"></div>
...
<div data-include="partials/footer.html"></div>
```

`js/include.js` 的核心邏輯（`js/include.js:29-48`）：抓 `data-include` 屬性指定的檔案，
`fetch()` 成功就用回傳的 HTML 字串取代整個佔位 `<div>`（`el.outerHTML = html`）；
失敗（例如真的用 `file://` 打開）就在原地顯示一段清楚的中文錯誤說明，而不是留一片空白讓人猜。

所有佔位 `<div>` 都載入完成後（`js/include.js:50-56` 的 `Promise.all`），
才執行「目前頁面導覽列高亮」（`js/include.js:16-27` 的 `highlightCurrentNav`）：
比對 `location.pathname` 的檔名跟每個導覽連結的 `href`，相符的那個加上 `aria-current="page"`，
這也是 `partials/header.html` 裡導覽連結不需要每頁手動改 `aria-current` 的原因——
共用元件是同一份，「目前頁」的差異完全交給 JS 判斷，而不是塞進 12 份不同的 header 副本。

同時會 dispatch 一個 `partials:loaded` 自訂事件，`js/site.js` 的行動選單邏輯
（`initMobileNav`，`js/site.js:9-17`）監聽這個事件才綁定漢堡選單按鈕的點擊事件——
因為漢堡選單按鈕本身是 header partial 的一部分，在 fetch 完成前它根本不存在於 DOM 裡，
太早綁定事件會抓不到元素。

## 3. 限制：為什麼一定要用本地伺服器開啟

**用瀏覽器直接雙擊 `index.html`（網址列會顯示 `file:///...`）打開這個網站，header 和 footer 會顯示錯誤訊息，畫面看起來像壞掉了——這是預期行為，不是 bug。**

原因：瀏覽器的同源政策（same-origin policy）把 `file://` 視為一種特殊、限制更嚴格的來源，
大多數瀏覽器會直接擋掉這類頁面對本機其他檔案發出的 `fetch()` 請求（各瀏覽器擋法細節不完全相同，
但結論都是讀不到）。這不是本站程式碼的問題，而是「JS fetch include」這個做法天生的代價。

**正確開法**：在 `stage2-multipage/` 目錄下執行

```bash
python3 -m http.server 8082
```

再用瀏覽器打開 `http://localhost:8082/index.html`。這時頁面是透過 `http://` 載入，
`fetch()` 就能正常讀到 `partials/` 底下的檔案。

> 為什麼這個限制值得寫成教學重點：它精準示範了「開發依賴」這件事——
> 做法 (b) 表面上「不需要建置工具」，但其實偷偷依賴了「一台本地伺服器」，
> 只是把複雜度換了一個位置藏起來，並沒有真的消失。這也是為什麼 stage3 開始
> 導入 Vite 之後，`npm run dev` 本身就內建了一台開發伺服器——同一個問題，
> 換一種方式繼續存在。

## 4. 與現成 UI 套件（如 Bootstrap）的取捨

`css/ui-kit.css` 是本站自己刻的「輕量 UI 套件」：design tokens（CSS 變數）加上
`.btn`、`.card`、`.badge`、`.form-field`、`.tabs`、`.breadcrumb` 這些元件類別。

Bootstrap、Tailwind 這類現成 UI 套件解決的是同一個問題——「不要每個專案都重新設計一次按鈕長什麼樣子」，
只是它們的元件庫更完整（跳出視窗、下拉選單、輪播……）、經過更多瀏覽器與情境驗證，
也有現成的文件與社群支援。真實專案多半會直接採用現成套件，省下重新造輪子的時間。

**本課程刻意自己刻的原因**：這套元件只有十幾個 class、幾百行 CSS，
剛好可以讓學員看懂「`.btn-primary` 這個 class 到底做了什麼」，而不是把它當一個黑盒子背下來。
等你看懂了原理，之後要用 Bootstrap 或 Tailwind，也只是換一套已經幫你寫好的同類型系統，
學習曲線會平緩很多。
