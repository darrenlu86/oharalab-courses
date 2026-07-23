# Stage 2 — WEB-14 多頁式靜態網站

> 回上層課程總覽：[`../README.md`](../README.md)

BrewGo 沖沖咖啡開幕了，這一階段把 stage1 的一頁式活動頁，長成一個有網站地圖、共用導覽、商品型錄、聯絡表單的正式官方網站。

## 這一階段你會做出什麼

一個 10 頁的純靜態網站（零 build step、零 CDN），包含：

- 首頁、商品型錄（12 筆商品、分類篩選）、3 個商品詳情示範頁、品牌故事、門市資訊、常見問題、聯絡表單、404 頁
- 用 JS fetch 做出的共用導覽列／頁尾（改一次，10 頁一起變）
- 自建的輕量 UI 套件 `css/ui-kit.css`（design tokens ＋ 按鈕／卡片／徽章／表單／頁籤／麵包屑元件類別）
- 一份會前端驗證、顯示錯誤訊息的聯絡表單
- `sitemap.xml`、`robots.txt`，以及每頁獨立的 SEO meta

## 對應課綱與交付產出

課綱原文：「完成一個多頁式靜態網站，含網站地圖、導覽結構、表單、UI 套件應用與跨瀏覽器相容性。完成後產出：含 Sitemap 與共用元件的網站架構說明、可存取所有頁面的部署連結、含設計面與技術面的設計與技術文件。」

| 產出要求 | 對應檔案 |
|---|---|
| 網站地圖與導覽結構說明 | [`docs/SITEMAP.md`](docs/SITEMAP.md) |
| 共用元件的架構說明 | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| 部署連結（教學指引＋交付檢查表） | [`docs/DEPLOY.md`](docs/DEPLOY.md) |
| 設計面與技術面的設計與技術文件 | [`docs/DESIGN_TECH.md`](docs/DESIGN_TECH.md) |
| 表單 | [`contact.html`](contact.html)、[`js/site.js`](js/site.js) |
| UI 套件應用 | [`css/ui-kit.css`](css/ui-kit.css) |
| 跨瀏覽器相容性 | `docs/DESIGN_TECH.md` 第二節 |

## 與上一階段的差異

> 以下對照已實際讀過 `stage1-onepage/README.md` 核對，不是憑 master spec 的定義推測。

- **從「一個檔案」變成「10 個檔案」**：stage1 是單一 `index.html`，7 個 `<section>` 全部擠在同一頁，用 `<nav>` 錨點捲動導覽；stage2 每個主題都是獨立頁面、獨立網址，第一次需要真正的「網站地圖」與 URL 命名規則（見 `docs/SITEMAP.md`）。
- **共用元件從「不需要」變成「必要」**：stage1 的導覽列跟 footer 只存在檔案裡的一份，不會有「改一個地方、要記得改十個地方」的問題；10 頁的網站如果每頁都複製貼上 header/footer，維護成本會隨頁數線性增加。這是本階段第一次引入 `partials/` ＋ `js/include.js` 的 fetch include 機制（見 `docs/ARCHITECTURE.md`）。
- **`file://` 直接雙擊開啟從「可以」變成「不行」**：stage1 README 明寫「`file://` 直接雙擊開啟也能完整運作」；stage2 因為導入了 (b) 做法的 fetch include，`file://` 協定下瀏覽器會擋掉 `fetch()` 讀本機檔案，header/footer 會顯示錯誤訊息。**這不是退步，是為了解決共用元件的維護問題而主動接受的取捨**——多一道「要跑本地伺服器」的門檻，換來「改一次全站生效」的好處，詳見 `docs/ARCHITECTURE.md` 第 3 節。
- **第一次出現 `sitemap.xml`／`robots.txt`**：stage1 只有一個網址，不需要告訴搜尋引擎「還有哪些頁面」；stage2 有 9 個內容頁，才需要 sitemap 幫爬蟲找到所有頁面。
- **從「4 張商品卡純展示」變成「12 筆完整型錄＋分類篩選」**：stage1 首頁只有「招牌選品」4 張固定商品卡；stage2 的 `products.html` 是完整 12 筆商品型錄，且第一次做分類篩選互動（`js/site.js` 的 `initCategoryFilter`）與庫存徽章（現貨／僅剩 N 件／補貨中）。
- **第一次需要麵包屑**：stage1 只有一頁，不需要告訴使用者「現在在哪裡」；stage2 有階層（商品型錄 → 商品詳情），才需要麵包屑定位。
- **表單從「訂閱表單」變成「完整聯絡表單」**：stage1 的訂閱表單只有姓名＋email 兩個欄位；stage2 的 `contact.html` 多了主題下拉、訊息文字區、同意條款 checkbox 共五種欄位型態，錯誤訊息顯示模式也更完整（欄位級 `role="alert"`、聚焦第一個錯誤欄位）。

## 課綱單元表

| 單元 | 學什麼 | 對應檔案 |
|---|---|---|
| 1. 資訊架構與網站地圖 | 頁面怎麼切、URL 命名、麵包屑、sitemap.xml／robots.txt 是給誰看的 | `docs/SITEMAP.md`、`sitemap.xml`、`robots.txt` |
| 2. 共用元件的三條路 | 複製貼上／JS fetch include／建置工具，三者的取捨 | `docs/ARCHITECTURE.md`、`partials/`、`js/include.js` |
| 3. 自建 UI 套件 | design tokens、元件類別，與現成 UI 套件的取捨 | `css/ui-kit.css` |
| 4. 表單設計 | 前端驗證、錯誤訊息顯示模式 | `contact.html`、`js/site.js` |
| 5. 跨瀏覽器相容性 | caniuse 查法、graceful degradation | `docs/DESIGN_TECH.md` 第二節 |
| 6. SEO 基礎 | 獨立 title/description/OG、標題階層、404 頁 | 各頁 `<head>`、`404.html` |

## 環境需求

- 任何有 Python 3（內建 `http.server` 模組）的作業系統，或任一款支援 `fetch()` 的現代瀏覽器
- 不需要 Node.js、不需要安裝任何套件——這是零依賴的靜態網站；本文件用到的 `node --check` 只是拿 Node 內建的語法檢查器順手驗證一下 JS 語法，並非執行網站的必要條件
- 實測環境：Python 3.13.11（文件寫最低需求 Python 3.10+，`http.server` 模組從 Python 3 就內建，理論上 3.x 都可以跑）

## 快速開始

**1. 進入專案目錄，啟動本地伺服器**

```bash
cd stage2-multipage
python3 -m http.server 8082
```

預期輸出：

```
Serving HTTP on :: port 8082 (http://[::]:8082/) ...
```

> **為什麼一定要用 `http.server`，不能直接雙擊 `index.html`**：本站的共用導覽列／頁尾是用 `fetch()` 動態載入的（見下方單元 2），瀏覽器在 `file://` 協定下會擋掉這類本機檔案讀取，直接雙擊打開會看到 header/footer 顯示錯誤訊息。完整原因見 `docs/ARCHITECTURE.md` 第 3 節。

**2. 打開網站**

瀏覽器打開 [http://localhost:8082/index.html](http://localhost:8082/index.html)，預期看到 BrewGo 首頁：hero 區塊、分類入口、精選商品。

**3.（可選）驗證所有頁面都能正常存取**

```bash
for p in index.html products.html product-yirgacheffe.html product-dripbag.html \
         product-giftbox.html about.html stores.html faq.html contact.html 404.html; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8082/$p")
  printf '%s -> %s\n' "$p" "$code"
done
```

實測輸出（本次建置實際跑出來的結果）：

```
index.html -> 200
products.html -> 200
product-yirgacheffe.html -> 200
product-dripbag.html -> 200
product-giftbox.html -> 200
about.html -> 200
stores.html -> 200
faq.html -> 200
contact.html -> 200
404.html -> 200
```

**4.（可選）跑連結完整性檢查**

```bash
python3 check-links.py
```

實測輸出：

```
掃描的 html 檔案（12 個）：404.html, about.html, contact.html, faq.html, index.html,
partials/footer.html, partials/header.html, product-dripbag.html, product-giftbox.html,
product-yirgacheffe.html, products.html, stores.html
檢查 119 條連結、0 死鏈
全部連結都指向存在的檔案。
```

**5. 驗證完記得關閉伺服器**：回到步驟 1 的終端機視窗按 `Ctrl+C`。

> **誠實聲明**：`python3 -m http.server` 不會自動套用自訂 `404.html`——打一個不存在的網址（例如 `http://localhost:8082/not-a-real-page`）看到的是 Python 內建的英文錯誤頁，不是這個專案做的 `404.html`。這個行為要部署到正式的靜態主機（GitHub Pages、Cloudflare Pages 等）才會生效，完整說明見 `docs/DEPLOY.md`。

## 逐步教學導覽

### 單元 1：資訊架構與網站地圖

打開 `docs/SITEMAP.md` 看完整的頁面清單、mermaid 網站地圖與導覽層級說明。重點程式碼：

- 麵包屑元件：`css/ui-kit.css` 的 `.breadcrumb` 類別（第 8 節），配合每頁 `<ol class="breadcrumb">` 標記，例如 `product-yirgacheffe.html` 裡「首頁 > 商品型錄 > 耶加雪菲 淺焙單品豆 250g」三層。
- `sitemap.xml`：9 個內容頁，`404.html` 刻意不列入（理由見 `docs/SITEMAP.md` 第 4 節）。

### 單元 2：共用元件（JS fetch include）

每一頁的 `<body>` 只放兩個佔位 `<div data-include="...">`（例如 `index.html` 開頭的
`<div data-include="partials/header.html"></div>`），實際內容由 `js/include.js` 動態塞入：

```js
// js/include.js:29-40
function loadInclude(el) {
  var file = el.getAttribute("data-include");
  return fetch(file)
    .then(function (res) { ... })
    .then(function (html) {
      el.outerHTML = html;
    })
    ...
}
```

所有佔位都載入完成後，`js/include.js:50-56` 才會執行「目前頁面導覽列高亮」，
比對 `location.pathname` 和 `partials/header.html:10` 的 `<nav id="main-nav">` 裡每個連結的 `href`，
相符的加上 `aria-current="page"`。三種做法的完整比較、以及為什麼選這條路，見 `docs/ARCHITECTURE.md`。

### 單元 3：自建 UI 套件

`css/ui-kit.css:15` 開始是全站共用的 design tokens（CSS 變數），例如：

```css
:root {
  --color-bg: #faf6f0;
  ...
}
```

之後的 `.btn`、`.card`、`.badge`、`.form-field`、`.tabs`、`.breadcrumb` 都是直接組合這些變數的元件類別。
例如 `products.html:136` 的「僅剩 3 件」徽章就是 `<span class="badge badge-warning">`，
`products.html:216` 的「補貨中」是 `<span class="badge badge-error">`——同一組 `.badge` 類別，
只是換一個修飾類別（modifier class）就能表達不同的庫存狀態，這正是「UI 套件」的核心價值：
先把顏色、間距這些設計決策集中定義一次，頁面只需要組合語意化的 class 名稱。

### 單元 4：表單設計

`contact.html:41` 的表單用了 `novalidate` 屬性，刻意關掉瀏覽器原生的驗證彈出視窗，
全部驗證邏輯交給 `js/site.js` 的 `initContactForm`（`js/site.js:67-` 起）處理，
理由是不同瀏覽器原生驗證訊息的用字、樣式都不一樣，用自己的 JS 驗證可以保證跨瀏覽器一致的錯誤訊息呈現。
每個欄位的錯誤透過 `setFieldError`（`js/site.js:73`）切換 `.form-field.has-error` 這個 class，
`css/ui-kit.css` 的 `.form-field.has-error .error-message` 規則負責讓錯誤訊息文字顯示出來——
這是「用 CSS class 控制狀態、JS 只負責切換 class」的常見模式，而不是用 JS 直接操作樣式。

### 單元 5：跨瀏覽器相容性

`docs/DESIGN_TECH.md` 第二節完整說明 caniuse 查法與本站三個 graceful degradation 實例
（CSS Grid、`:focus-visible`、`scroll-behavior`），包含一段查證過程中發現的資料落差誠實記錄。

### 單元 6：SEO 基礎

打開任一頁面的 `<head>`，都能看到獨立的 `<title>`、`<meta name="description">`、`og:*` 標籤與
`<link rel="canonical">`；`404.html:8` 額外加了 `<meta name="robots" content="noindex">`，
避免錯誤頁被搜尋引擎索引。

## 驗收清單

- [x] 10 個頁面（含 404）本地伺服器 curl 皆回應 200
- [x] 全站連結（含 partials 內的導覽連結）掃描 0 死鏈
- [x] `sitemap.xml` 含全部 9 個內容頁 URL，不含 404
- [x] `js/include.js`、`js/site.js` 皆通過 `node --check` 語法檢查
- [x] 12 筆商品資料與 master 型錄完全一致（id、名稱、分類、價格、庫存皆比對）
- [x] products.html 分類頁籤可篩選；id=6「僅剩 3 件」、id=11「補貨中」徽章正確呈現
- [x] 3 個商品詳情頁都有麵包屑、大圖、價格、描述、規格表、庫存徽章
- [x] 每頁掛載共用 header/footer，導覽列有 `aria-current="page"` 高亮機制
- [x] 聯絡表單有前端驗證與錯誤訊息顯示
- [x] 零 CDN、零 build step（全站沒有任何 `<script src="https://...">` 或外部 `<link>`）
- [ ] 實際部署到公開網址並填寫 `docs/DEPLOY.md` 的學員交付檢查表（需要學員自行完成）
- [ ] 三個以上真實瀏覽器手動走查（本次建置環境無可用瀏覽器 GUI，未實機測試，見 `docs/DESIGN_TECH.md` 第 2.3 節誠實聲明）

## 延伸挑戰

1. 幫另外 9 筆商品也各自做一個詳情頁，你會遇到什麼維護上的困難？試著用這個困難重新體會 `docs/ARCHITECTURE.md` 提到的「做法 (b) 的效益會被缺點追過去」是什麼意思。
2. `contact.html` 的表單目前送出後只在頁面內顯示成功訊息，資料不會被保存。如果要讓「送出的內容真的存下來」，你會需要哪些額外的東西？（不用真的做，先寫下你的規劃）
3. 目前分類篩選（`js/site.js` 的 `initCategoryFilter`）是把 12 張卡片一次全部載入、再用 CSS 隱藏。如果商品數量變成 1000 筆，這個做法會遇到什麼問題？有沒有更好的做法？
4. 幫 `stores.html` 加上第三間門市，需要改到哪些檔案？跟「幫商品型錄加第 13 筆商品」比起來，哪個改動的檔案數量比較多？為什麼？

## 教學簡化聲明

- **BrewGo 是虛構品牌**，商品資料、門市地址電話、品牌故事時間軸都是為了教學設計的示範內容，不是真實商業實體。
- **聯絡表單是 mock**：`contact.html` 前端驗證通過後只會顯示成功訊息，沒有任何後端接收或儲存資料；真正能寄出/儲存的表單要等 stage4 接後端 API 之後才有。
- **商品詳情頁只做 3 個示範**：其餘 9 筆商品目前只在型錄呈現基本資訊，理由與後續規劃見 `faq.html` 的對應問答與 `docs/ARCHITECTURE.md`。
- **`sitemap.xml`／`robots.txt`／canonical／`og:url` 用的是佔位網域** `https://www.brewgo-demo.example`（RFC 2606 保留的範例網域），部署上線前必須換成實際網域，步驟見 `docs/DEPLOY.md`。
- **跨瀏覽器相容性描述未經實機測試**：本次建置環境沒有可用的瀏覽器 GUI，`docs/DESIGN_TECH.md` 第二節的瀏覽器支援度全部是「依 caniuse 資料與程式碼審閱推斷」，不是實機測試結果，詳見該節誠實聲明。

## 作者與聯絡資訊

本專案為呂紹民（Darren Lu）製作的教學範例，供學員學習網站工程使用。如果對本文件或專案有任何問題，或有課程教學、顧問諮詢、專案導入需求，歡迎與我聯絡。

- Email：kevin868686@gmail.com
- LinkedIn：https://www.linkedin.com/in/shaominglu
- Facebook：https://www.facebook.com/darrenlu86
