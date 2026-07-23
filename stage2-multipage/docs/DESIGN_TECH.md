# 設計與技術文件

本文件分兩塊：設計面（色彩、字體、版型、元件庫）與技術面（跨瀏覽器相容性、SEO 基礎）。

## 一、設計面

### 1.1 色彩與對比（WCAG AA 實測）

品牌色彩定義在 `css/ui-kit.css:16-25`（design tokens），沿用課程共用視覺語言（見 master spec 第 3 節）：

| token | 色碼 | 用途 |
|---|---|---|
| `--color-bg` | `#faf6f0` | 頁面底色 |
| `--color-surface` | `#ffffff` | 卡片、輸入框底色 |
| `--color-text` | `#2b211a` | 內文文字 |
| `--color-text-muted` | `#6b5c4f` | 次要文字（說明、時間戳、badge 文字） |
| `--color-primary` | `#4b3324` | 標題、主按鈕 |
| `--color-primary-light` | `#6b4a33` | 主按鈕 hover |
| `--color-accent` | `#9c5b2b` | 連結、強調 |
| `--color-success` | `#2e6b40` | 成功狀態 |
| `--color-error` | `#a13333` | 錯誤狀態 |

**實測方式**：用 WCAG 2.1 的相對亮度公式寫一段 Python 腳本，逐一計算本站實際用到的文字/背景配色組合對比值（見下表），標準是一般文字需要 ≥ 4.5:1（AA）。這是實際跑出來的數字，不是估計：

```
text           on bg        : 14.61  AA-normal=True
text           on surface   : 15.73  AA-normal=True
white          on primary   : 11.68  AA-normal=True
white          on primary-light: 7.92  AA-normal=True
white          on accent    : 5.32  AA-normal=True
white          on success   : 6.38  AA-normal=True
white          on error     : 6.92  AA-normal=True
accent         on bg        : 4.94  AA-normal=True
accent         on surface   : 5.32  AA-normal=True
primary        on bg        : 10.85  AA-normal=True
primary        on surface   : 11.68  AA-normal=True
success        on bg        : 5.92  AA-normal=True
success        on surface   : 6.38  AA-normal=True
error          on bg        : 6.42  AA-normal=True
error          on surface   : 6.92  AA-normal=True
text-muted     on bg        : 5.97  AA-normal=True
text-muted     on surface   : 6.42  AA-normal=True
```

全部 17 組實際用到的組合都達到 4.5:1 以上，本站沒有需要另外加深色階的組合。
（`accent on bg` 是最接近門檻的一組，實測 4.94:1，仍高於 4.5:1 標準。）

### 1.2 字體

`css/ui-kit.css:29-30` 用的是 system font stack：

```css
--font-sans: -apple-system, BlinkMacSystemFont, "Noto Sans TC", "PingFang TC",
  "Microsoft JhengHei", sans-serif;
```

不引入 Google Fonts 這類 webfont 服務。理由：(1) 零額外網路請求，離線也能正確顯示中文字型；
(2) 不同作業系統的預設中文字型（macOS 的 PingFang TC、Windows 的 Microsoft JhengHei）
其實已經是各平台最佳化過的顯示效果，不一定輸給網頁字型；(3) 真實專案若要品牌字體，
才需要權衡「載入時間」與「品牌一致性」，本課程階段選擇先把這個成本歸零。

### 1.3 版型與元件庫

版面用 CSS Grid 排版（`.grid`、`.grid-2/3/4`，`css/ui-kit.css` 第 9 節），清單型內容
（商品卡片、分類入口、門市資訊）一律用 grid 對齊呈現，不做左右交錯的版型——
這是課程規則，也是實務上更容易維護的排版方式（交錯排版通常需要針對每一項手動調整 margin，
grid 只要定義好欄數跟間距，內容增減都不用重排）。

元件庫（`.btn`、`.card`、`.badge`、`.form-field`、`.tabs`、`.breadcrumb`）的完整設計理由，
以及跟 Bootstrap 這類現成 UI 套件的比較，見 `docs/ARCHITECTURE.md` 第 4 節，這裡不重複。

### 1.4 響應式斷點

`css/site.css` 用了三個斷點：

| 斷點 | 變化 |
|---|---|
| `max-width: 900px` | 商品卡片 grid 從 4 欄收成 2 欄 |
| `max-width: 820px` | 導覽列切換成漢堡選單；hero、詳情頁、聯絡頁的兩欄版型收成單欄 |
| `max-width: 600px` | 所有 grid 收成單欄 |

斷點數字對應常見的桌機/平板/手機三段式尺寸，不是精確對應特定機型，
這是刻意簡化——正式產品通常會依照實際流量的裝置寬度分佈調整斷點，
本課程用經驗值即可，教學重點是「知道要分斷點」而不是「背哪個數字」。

## 二、技術面：跨瀏覽器相容性

### 2.1 caniuse 查法示範

本站用到三個「不是所有瀏覽器都一定支援」的 CSS 特性：CSS Grid、`:focus-visible`、`scroll-behavior`。
以下是 2026-07-24 實際查詢 [caniuse.com](https://caniuse.com/) 當下頁面得到的支援度資料：

| 特性 | 全球支援度 | Chrome | Firefox | Safari | Edge |
|---|---|---|---|---|---|
| [CSS Grid](https://caniuse.com/css-grid) | 95.36% | 57+ | 52+ | 10.1+ | 16+（12-15 部分支援） |
| [`:focus-visible`](https://caniuse.com/css-focus-visible) | 93.45% | 86+ | 見下方註記 | 15.4+ | 86+ |
| [`scroll-behavior`](https://caniuse.com/css-scroll-behavior) | 94.22% | 61+（41-60 預設關閉） | 36+ | 15.4+（14-15.3 預設關閉） | 79+ |

> **查證過程的誠實記錄**：查 `:focus-visible` 的 Firefox 支援版本時，caniuse 頁面顯示的數字是「第 4 版」，
> 但 `:focus-visible` 這個標準選擇器實際定稿與各家瀏覽器陸續跟進的時間遠晚於 Firefox 4
> （Firefox 很早就有一個效果類似、但語法不同的非標準版本 `:-moz-focusring`）。
> 這個數字很可能是 caniuse 資料庫把「相近的舊版非標準實作」與「新標準」合併記錄造成的落差。
> 這正是「caniuse 查法」真正要教的事——**看到數字不要照單全收，要弄清楚它對應的是哪一版規格**，
> 有疑慮時交叉比對 [MDN 瀏覽器相容性表](https://developer.mozilla.org/)會更保險。
> 因此上表 Firefox 欄位刻意不寫死一個可能誤導的版本號。

**怎麼查（示範步驟）**：(1) 打開 caniuse.com，搜尋特性名稱（例如 `focus-visible`）；
(2) 看頂端「全球支援度」百分比，快速判斷這個特性夠不夠成熟；
(3) 展開下方各瀏覽器版本表格，逐一確認自己要支援到多舊的版本；
(4) 捲到頁面下方的「Notes」區塊，通常會寫清楚「部分支援」代表什麼限制。

### 2.2 Graceful degradation：本站三個實例

**autoprefix 的概念**：正式專案常用 Autoprefixer（PostCSS 套件）自動幫 CSS 屬性加上
`-webkit-`、`-moz-` 這類瀏覽器前綴，確保實驗性 CSS 特性在較舊瀏覽器也能生效。
本站因為「零 build step」的教學限制（見 master spec 第 5 節），沒有引入 PostCSS，
選用的三個特性也都已經是無前綴、廣泛支援的標準寫法，暫時不需要 autoprefix；
真的需要 vendor prefix 的情境會等到 stage3 引入建置工具後才處理。

1. **CSS Grid**（`css/ui-kit.css` 第 9 節）：用 `@supports not (display: grid)` 偵測，
   不支援 grid 的瀏覽器會退回 `display: block` 加上每個項目的 `margin-bottom`——
   內容還是看得到、還是能捲動閱讀，只是排版從「多欄」變回「單欄直向」，
   功能沒有壞掉，只是版面比較不精美。

2. **`:focus-visible`**（`css/ui-kit.css` 第 2 節）：寫法是先用一般 `:focus` 選取器套用外框樣式，
   再用 `:focus-visible` 覆蓋、`:focus:not(:focus-visible)` 取消——不支援 `:focus-visible` 的瀏覽器
   會停在「所有 focus 都顯示外框」，支援的瀏覽器則是「只有鍵盤操作時才顯示外框、滑鼠點擊不顯示」。
   兩種結果都不影響鍵盤可及性，差異只在滑鼠使用者會不會看到額外的外框，是安全的漸進增強。

3. **`scroll-behavior: smooth`**（`css/ui-kit.css:61`，只用在 `<html>` 上，
   目前站內用來讓「跳到主內容」這類錨點連結捲動時有平滑過場）：
   不支援的瀏覽器會直接跳到目標位置，沒有平滑動畫效果——這是純粹的視覺體驗差異，
   使用者仍然能到達正確的位置，不影響任何功能。

### 2.3 實測瀏覽器清單（誠實聲明）

本次建置環境是無圖形介面的 sandbox：曾嘗試透過瀏覽器自動化工具做實機視覺驗證，
但該環境的瀏覽器擴充功能未連線（工具回傳 `Browser extension is not connected`），因此**沒有
任何一個瀏覽器做過真正的畫面渲染或互動實測**。已經實際驗證過的，僅限於：

- HTTP 層：`python3 -m http.server` 起站後，10 個頁面 curl 皆回應 200（見 `README.md` 快速開始一節與本 repo 的自動化 smoke 驗證輸出）。
- 連結完整性：自寫的 Python 腳本掃描全部 12 個 html 檔案（含 partials）的 `href`/`src`，119 條連結、0 死鏈。
- JS 語法：`node --check js/include.js`、`node --check js/site.js` 皆通過（只驗證語法能被解析執行，不代表瀏覽器行為已實測）。

換句話說，**上面 2.1、2.2 節提到的瀏覽器版本支援與 degradation 行為，全部是「依 caniuse 資料與程式碼審閱推斷」，不是本次建置過程中的實機測試結果**。
如果你在實際的 Chrome / Firefox / Safari / Edge 或行動裝置瀏覽器打開這個網站時發現任何跟本文件描述不一致的地方，
這份文件的描述以你的實機測試結果為準，也歡迎回報（見 `README.md` 作者聯絡資訊）讓後續學員受惠。

## 三、SEO 基礎

- 每個內容頁都有獨立的 `<title>`（格式：`頁面名稱｜BrewGo 沖沖咖啡`）與 `<meta name="description">`，
  沒有兩個頁面共用同一段描述。
- 每頁都有對應的 Open Graph 標籤（`og:title`、`og:description`、`og:image`、`og:url`）；
  `og:image` 目前指向本站自繪的 SVG（`images/og-image.svg`），**誠實聲明**：多數社群平台
  （例如 Facebook、LINE）對 `og:image` 是否穩定支援 SVG 格式尚不一致，正式上線建議改用
  1200×630 的 PNG/JPG（可以把同一張 SVG 用瀏覽器截圖或 `rsvg-convert`/Figma 匯出）。
- 語意化標題階層：每頁固定一個 `<h1>`，子區塊依序用 `<h2>`、`<h3>`，沒有跳級（例如不會 `<h1>` 後面直接接 `<h3>`）。
- `404.html` 加上 `<meta name="robots" content="noindex">`，避免錯誤頁被搜尋引擎索引到。
- 語言標籤 `<html lang="zh-Hant">` 全站一致（協助螢幕閱讀器與搜尋引擎判斷語系）。
