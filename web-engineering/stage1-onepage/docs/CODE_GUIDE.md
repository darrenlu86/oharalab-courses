# Stage 1 程式碼結構說明

回上層：[Stage 1 README](../README.md)｜課程總覽：[../../README.md](../../README.md)

本文件對應課綱產出要求 1「含關鍵程式片段的程式碼結構說明」。

## 1. 檔案結構

```
stage1-onepage/
├── README.md            教案主文件
├── index.html           整頁內容（唯一一個 HTML 檔）
├── css/style.css         全站樣式（含 RWD 斷點）
├── js/main.js            全站互動邏輯（漢堡選單／倒數／accordion／表單驗證）
├── images/               本地 SVG 插圖與商品圖
│   ├── logo.svg
│   ├── hero-coffee.svg
│   ├── p1.svg / p4.svg / p5.svg / p12.svg   對應型錄 id 1/4/5/12
│   └── store-map.svg
└── docs/
    ├── CODE_GUIDE.md     本文件
    ├── DESIGN.md         三裝置設計說明
    └── DEPLOY.md         靜態部署教學＋交付檢查表
```

| 檔案 | 職責 | 大約行數 |
|---|---|---|
| `index.html` | 頁面結構與內容，7 個 `<section>`（hero/story/products/promo/faq/store/subscribe） | 374 |
| `css/style.css` | Design tokens、reset、各區塊樣式、3 段 media query | 640 |
| `js/main.js` | 4 個獨立初始化函式：導覽列、倒數計時、accordion、表單驗證 | 198 |

為什麼只有一個 HTML 檔：這是「一頁式」網頁的定義——所有內容都在同一個 `index.html`，靠錨點（`#story`、`#products`…）在頁面內跳轉，不是靠換頁。多頁式的做法（多個 HTML 檔、共用導覽列）留到 stage2。

## 2. 關鍵程式片段

### 2.1 倒數計時與邊界處理（`js/main.js:44-82`）

```js
var OPENING_DATE = new Date("2026-09-01T10:00:00+08:00");

function tick() {
  var now = new Date();
  var diffMs = OPENING_DATE.getTime() - now.getTime();

  if (diffMs <= 0) {
    // 已過開幕時間：隱藏倒數格子，顯示「已盛大開幕」，並停止計時器。
    wrapper.classList.add("hidden");
    if (doneEl) doneEl.classList.remove("hidden");
    clearInterval(timerId);
    return;
  }

  var totalSeconds = Math.floor(diffMs / 1000);
  var days = Math.floor(totalSeconds / 86400);
  var hours = Math.floor((totalSeconds % 86400) / 3600);
  var minutes = Math.floor((totalSeconds % 3600) / 60);
  var seconds = totalSeconds % 60;
  // ...寫進對應的 <span> 裡
}
```

**為什麼這樣寫**：`diffMs`（毫秒差）算出來如果是負的，代表現在時間已經超過開幕時間。很多倒數計時的教學範例會忽略這個分支，直接顯示負數（「-3 天」），這對使用者沒有任何意義。這裡刻意先判斷 `diffMs <= 0`，切到「已盛大開幕」的訊息並呼叫 `clearInterval` 停止計時器——**停掉計時器**這件事同樣容易被忽略：如果不停掉，`setInterval` 會每秋持續執行、持續改一個已經不會再變化的 DOM，是不必要的效能浪費。

**實測結果**（`node -e` 直接跑同一段換算邏輯，不含 DOM 操作）：

```
測試1 現在(2026-07-23)： 40天 10時 0分 0秒
測試2 開幕前一秒： 0天 0時 0分 1秒
測試3 開幕當下： 已盛大開幕
測試4 開幕後一天： 已盛大開幕
```

### 2.2 FAQ Accordion（`js/main.js:91-110`）

```js
triggers.forEach(function (trigger) {
  var panel = document.getElementById(trigger.getAttribute("aria-controls"));
  if (!panel) return;

  trigger.addEventListener("click", function () {
    var isExpanded = trigger.getAttribute("aria-expanded") === "true";
    var nextState = !isExpanded;

    trigger.setAttribute("aria-expanded", String(nextState));
    panel.hidden = !nextState;
  });
});
```

**為什麼用 `aria-controls` + `getElementById` 找面板，而不是找「按鈕的下一個兄弟元素」**：HTML 結構之後如果調整（例如面板外面多包一層 `<div>`），用 `nextElementSibling` 這種寫法就會抓錯元素；用 `id` 對應是明確的關聯，結構怎麼調整都不受影響。

**為什麼 `aria-expanded` 和 `panel.hidden`要同時改，而不是只用其中一個**：`aria-expanded` 是說給螢幕閱讀器聽的「狀態」，`panel.hidden` 是「畫面上看不看得到」——這是兩件事，各自服務不同的使用者。只改其中一個會出現「螢幕閱讀器說已展開，畫面卻是收合的」這種不一致，對用鍵盤／螢幕閱讀器的使用者非常困擾。`css/style.css:429-433` 另外用 `[aria-expanded="true"]` 屬性選擇器控制 `+` 圖示轉 45 度變成 `×`，同一個屬性同時驅動兩件事，好處是不用另外維護一個重複的 class。

### 2.3 表單驗證（`js/main.js:120-187`）

```js
var EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validateEmail() {
  var value = emailInput.value.trim();
  if (!value) {
    emailError.textContent = "請填寫 email。";
    return false;
  }
  if (!EMAIL_PATTERN.test(value)) {
    emailError.textContent = "email 格式看起來不對，請確認有沒有打錯（例如缺少 @ 或網域）。";
    return false;
  }
  emailError.textContent = "";
  return true;
}

form.addEventListener("submit", function (event) {
  event.preventDefault();
  // ...驗證兩個欄位，都過了才顯示成功訊息
});
```

**教學簡化聲明**：`EMAIL_PATTERN` 只檢查「有 @、@ 前後都有字元、結尾有網域」，不是完整的 RFC 5322 email 格式規則（那份規格連很多正式產品的驗證都做不到 100% 正確，例如允許帶引號的怪異合法格式）。教學上這樣的寬鬆規則已經足夠擋掉「忘記打 @」這類最常見的手誤。

**為什麼 `event.preventDefault()` 一定要呼叫**：`<form>` 標籤預設「送出」的行為是把頁面導向 `action` 屬性指定的網址（本頁沒有寫 `action`，預設值是「送到目前這個網址」，等同重新整理頁面）。呼叫 `preventDefault()` 阻止這個預設行為，改成用 JS 自己接手處理——這是純前端 mock 一定要做的一步，不然按下送出鍵頁面就會重新整理，剛剛顯示的錯誤訊息或成功訊息會立刻消失。

**誠實聲明**：這裡的「送出」只是把 `<form>` 隱藏、換成成功訊息的 `<p>`，資料完全沒有被存到任何地方、也沒有離開瀏覽器。真的要收集訂閱名單，需要一支後端 API 接住這筆資料寫進資料庫，這是 stage4 起才會做的事——本頁與 README 都刻意重複提醒這件事，避免學員誤以為「畫面上顯示成功」等於「資料真的送出去了」。

### 2.4 RWD 斷點（mobile-first，`css/style.css:317-322` 對照 `:614-616` 與 `:629-631`）

```css
/* 預設（<768px）：手機，2 欄 */
.product-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3);
}

/* 768px 以上：平板，3 欄 */
@media (min-width: 768px) {
  .product-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

/* 1024px 以上：桌機，4 欄 */
@media (min-width: 1024px) {
  .product-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}
```

**為什麼先寫手機版樣式、再用 `min-width` 疊加桌機版**（mobile-first）：`.product-grid` 的基礎規則（沒有包在任何 media query 裡）就是手機版的 2 欄；瀏覽器視窗變寬、符合 `min-width: 768px` 時，才「疊加」3 欄的規則覆蓋掉 2 欄。這樣寫的好處是：任何還沒被想到、沒被明確斷點覆蓋到的極端窄螢幕（例如舊型手機），都能拿到堪用的基礎樣式，而不是「桌機樣式，硬擠進小螢幕」的慘況（desktop-first 常見的反效果）。

**為什麼商品卡、優惠卡用 CSS Grid 而不是 Flexbox**：Grid 天生就是「固定幾欄、欄寬平均分配」的排版，`grid-template-columns: repeat(N, 1fr)` 一行就能做到「N 欄等寬」，換斷點只要改這一個數字；Flexbox 要做到等寬換行需要額外設定 `flex-basis` 和 `flex-wrap`，對初學者來說更難一次理解對。導覽列（`.navbar`）用 Flexbox 則是因為那裡是「一行內幾個元素兩端對齊」，不需要換行也不需要多欄，是 Flexbox 最擅長的場景——這也是本頁刻意示範「Grid 用在網格排版、Flexbox 用在單軸排列」兩種場景分工的地方。

### 2.5 平滑捲動（`css/style.css:47`）

```css
html {
  scroll-behavior: smooth;
}
```

**為什麼這行寫在 `css/style.css` 而不是 `js/main.js`**：導覽列裡的錨點連結（`<a href="#store">`）本身就是瀏覽器內建的跳轉行為，唯一「不平滑」的地方只是跳轉的動畫效果——這件事 CSS 一個屬性就能宣告完成，不需要 JS 介入去監聽點擊、算目標位置、再呼叫 `element.scrollIntoView({ behavior: "smooth" })`。

**為什麼不用 JS 版的 `scrollIntoView`**：JS 版能做的事（自訂 easing、捲動中執行回呼、捲到一半中斷）本頁完全不需要，多寫的程式碼只是徒增維護成本與出錯機會（例如忘記排除 `prefers-reduced-motion`、或是漏綁某個新加的錨點連結）。這正是**漸進增強**的實例：先用最少、最穩固的方案（一行 CSS，任何支援它的瀏覽器都直接生效，不支援的瀏覽器也不會壞——只是變回瞬間跳轉），只有當需求超出 CSS 能力範圍時才加 JS。`scroll-behavior` 在目前主流瀏覽器支援度已經很高，沒有支援的瀏覽器會靜默忽略這個屬性、直接瞬間跳轉，不會拋錯、也不會讓連結失效，符合「壞得優雅」的原則。

## 3. 語意化 HTML 的選擇（`index.html` 全檔）

| 標籤 | 用在哪裡 | 為什麼不用 `<div>` |
|---|---|---|
| `<header>` | 導覽列（17 行） | 讓瀏覽器、螢幕閱讀器、SEO 爬蟲一眼認出「這是頁首」，不用另外猜 class 名稱 |
| `<nav>` | 導覽選單（35 行） | 螢幕閱讀器可以直接「跳到導覽」，`<div>` 沒有這種內建語意 |
| `<main>` | 主要內容（47 行） | 一個頁面只能有一個 `<main>`，明確標出「扣掉頁首頁尾，真正的內容從這裡開始」 |
| `<section>` ×7 | 品牌故事／招牌選品／開幕優惠／FAQ／門市／訂閱等區塊 | 每個區塊都配一個 `aria-labelledby` 指向自己的標題，形成瀏覽器/輔助技術看得懂的「章節」 |
| `<footer>` | 頁尾（364 行） | 同 `<header>` 的道理，語意明確 |
| `<article>` | 商品卡（122 行起） | 每張商品卡是「獨立、可以單獨拿出來也看得懂」的一個單元，符合 `<article>` 的定義 |
| `<dl>`/`<dt>`/`<dd>` | 門市資訊（301 行起） | 地址／營業時間／電話是「詞語＋說明」的成對資料，`<dl>` 是這種資料語意上最貼切的標籤 |

**`label` 對應 `input`**：`index.html:336-337`、`342-343` 的 `<label for="subscribe-name">` 對應 `<input id="subscribe-name">`，靠 `for`/`id` 這一組屬性關聯——這樣點擊文字「姓名」也會讓輸入框拿到焦點，螢幕閱讀器唸到輸入框時也會唸出對應的 label 文字，不用另外加 `aria-label` 重複一次。

**`img` 一定要有 `alt`**：全站每張 `<img>` 都寫了具體描述文字的 `alt`（例如 `alt="耶加雪菲淺焙單品豆商品插圖"`），而不是留空或寫「圖片」這種沒有資訊量的文字——螢幕閱讀器使用者要靠這段文字知道圖片內容，圖片載入失敗時瀏覽器也會顯示這段文字頂替。
