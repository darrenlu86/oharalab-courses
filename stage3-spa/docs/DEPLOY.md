# DEPLOY — SPA 建置與靜態部署教學

回上層：[stage3-spa README](../README.md)

> 以下（一）（二）兩節是實測過的本地驗證步驟，附實際執行輸出。（三）主流平台部署步驟是教學指引，**實際操作畫面請以各平台當下介面為準**——本課程不代學員部署，部署完成後請自行填寫本文件最後的「學員交付檢查表」。

## 一、`npm run build` 產物是什麼

```bash
npm run build
```

實測輸出（2026-07-24 本機實際執行）：

```
vite v8.1.5 building client environment for production...
transforming...✓ 49 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.65 kB │ gzip:  0.45 kB
dist/assets/index-iia0sqIS.css    9.97 kB │ gzip:  2.33 kB
dist/assets/index-DM2FPoAx.js   255.49 kB │ gzip: 81.21 kB

✓ built in 104ms
```

（檔名裡的 hash、確切 kB 數字每次 build 可能因為內容或版本微調而略有不同，這是正常現象——重點是有沒有成功產出 `index.html` + `assets/*.js` + `assets/*.css` 這三類檔案。）

`dist/` 資料夾就是「這個網站的成品」，裡面是：

- `index.html`：入口 HTML，`<script>` 標籤指向打包後的 JS
- `assets/index-<hash>.js`：整個 React App 打包後的單一 JS 檔（React、react-router-dom、我們寫的所有元件全部打包在一起，檔名裡的 hash 是內容的雜湊值，內容沒變 hash 就不會變——這是瀏覽器快取優化的常見做法）
- `assets/index-<hash>.css`：所有 CSS 打包後的單一檔案

**這跟 `npm run dev` 的差異**：開發模式下瀏覽器是即時跟 Vite 開發伺服器要每個檔案、還會注入 Hot Module Replacement 用的程式碼方便開發除錯；`build` 產出的是「純靜態檔案」，不需要 Node.js 執行環境，任何一個能 serve 靜態檔案的伺服器（甚至只是 `file://` 打開，但下面會講為什麼路由功能在 `file://` 下可能有問題）都能把它跑起來。

## 二、本地驗證（已實測）

```bash
npm run preview -- --port 4173
```

另開一個終端機視窗執行：

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:4173/
```

實測輸出：

```
200
```

```bash
curl -s http://localhost:4173/ | grep -o '<div id="root">'
```

實測輸出：

```
<div id="root">
```

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:4173/products
```

實測輸出：

```
200
```

（最後這行驗證的正是下一節要講的「SPA fallback routing」——直接打一個非根路徑的網址，`vite preview` 內建的靜態伺服器有把它導回 `index.html`，回應才會是 200 而不是 404。）

## 三、SPA 的 404／fallback routing 問題

### 為什麼「直接輸入 `/products` 網址」在很多靜態主機上會 404

這個專案只有一個實體 HTML 檔案：`dist/index.html`。`/products`、`/cart`、`/products/3` 這些路徑**在檔案系統裡並不存在對應的檔案**——它們是 `react-router-dom` 在瀏覽器裡用 JavaScript 動態判斷網址、換掉畫面內容做出來的「假路由」（這種技術叫 Client-side Routing）。

流程是這樣：

1. 使用者從首頁點連結進入 `/products`：瀏覽器**沒有**重新跟伺服器要一個新頁面，是 JS 攔截了這次導覽、直接在同一個 `index.html` 裡切換畫面內容。這種情況完全不會 404，因為根本沒有發出新的 HTTP 請求。
2. 使用者**直接在網址列輸入** `https://your-site.example.com/products`，或是重新整理已經在 `/products` 的頁面：這次瀏覽器會真的發出一個 HTTP 請求給伺服器，問「有沒有 `/products` 這個資源」。一般的靜態檔案伺服器只認得實體檔案／資料夾，找不到 `dist/products/index.html` 這種東西，就會回 404。

### 解法：伺服器端的 rewrite／fallback 設定

所有支援 SPA 的靜態主機都有「找不到實體檔案時，改回傳 `index.html`（但 HTTP 狀態碼通常還是 200，網址列還是保留使用者輸入的原始路徑）」這個機制，讓瀏覽器重新拿到 `index.html` 之後，`react-router-dom` 再依網址列的路徑（這次是 `/products`）自己判斷該顯示哪個頁面。以下是幾個主流平台的設定方式（教學指引，實際操作介面請以平台當下畫面為準）：

- **Cloudflare Pages**：預設就會幫 SPA 專案自動處理 fallback（偵測到專案沒有對應路徑的檔案時退回 `index.html`）；如果沒有自動生效，可以在 `dist/` 建立一個 `_redirects` 檔案，內容 `/* /index.html 200`。
- **Netlify**：同樣是在 `dist/` 建立 `_redirects` 檔案，內容 `/* /index.html 200`。
- **Vercel**：在專案根目錄的 `vercel.json` 設定 `rewrites`，把所有路徑都指向 `/index.html`。
- **GitHub Pages**：沒有原生的 rewrite 設定，常見做法是把 `dist/index.html` 複製一份成 `dist/404.html`（GitHub Pages 找不到路徑時預設會顯示 `404.html`，React Router 依然能從網址列讀到正確路徑並顯示對應頁面）。
- **一般 Nginx**：在 `location /` 區塊設定 `try_files $uri /index.html;`。

**本課程不代學員部署，上面這份清單是教學指引，實際操作請以你選擇的平台當下畫面為準。**

## 四、環境變數與 build-time 概念

Vite 支援在 build 時把環境變數「烤進」最終的 JS 檔案（build-time，不是 runtime）：凡是 `import.meta.env.VITE_XXX` 這種寫法，Vite 在執行 `npm run build` 的當下就會把它換成實際字串值，之後不管誰、在哪台伺服器上開啟這個網站，值都不會再變（因為它已經變成打包後 JS 檔案裡的一段固定文字，不是伺服器執行期讀取的設定）。

**本階段沒有用到任何環境變數**：商品資料是打包進去的靜態 JSON、匯率 API 網址是寫死在程式碼裡的公開端點（不需要金鑰），完全不需要區分「開發環境」跟「正式環境」要打不同的 API 位址。這是刻意的簡化——等到 stage4 接上真正的後端 API，前端需要知道「後端網址」這種會隨部署環境不同而改變的設定，才會真正需要 `VITE_API_BASE_URL` 這類環境變數，屆時會在 stage4 的文件裡示範。

## 五、學員交付檢查表

> 部署到你選擇的平台後，請自行勾選並填上你自己的連結。

- [ ] 已執行 `npm run build`，`dist/` 資料夾成功產生
- [ ] 已部署到一個靜態網站平台，網址：`____________________`
- [ ] 直接在網址列輸入子路徑（例如 `你的網址/products`）重新整理，畫面正確顯示，沒有 404（SPA fallback 設定成功）
- [ ] 商品列表、分類篩選、關鍵字搜尋都能正常運作
- [ ] 可以完整走過「加入購物車 → 改數量 → 結帳 → 訂單完成 → 訂單查詢」整個流程
- [ ] 切換 USD／JPY 參考價功能正常（不管匯率 API 當下是否可連得上，都不應該讓頁面壞掉）
- [ ] 手機／平板寬度下畫面正常（開發者工具切換裝置模擬，或用實機測試）
