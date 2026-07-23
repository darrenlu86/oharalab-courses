# Stage 1 部署教學

回上層：[Stage 1 README](../README.md)｜課程總覽：[../../README.md](../../README.md)

本文件對應課綱產出要求 2「可存取的線上部署連結」。**本課程不代學員部署**：以下第 1 節是本地驗證方式（已實測，附實際輸出）；第 2 節是主流平台部署步驟教學（文件指引，實際操作畫面請以平台當下介面為準）；第 3 節是給學員部署完自己填寫的交付檢查表。

## 1. 本地驗證（已實測）

Stage 1 是純靜態網頁，零依賴、零 build step，兩種方式都能看到成品：

### 方式 A：直接用瀏覽器開啟 `index.html`（`file://` 協定）

Finder／檔案總管裡雙擊 `index.html`，或瀏覽器網址列貼上 `file:///你的路徑/stage1-onepage/index.html`。因為本階段沒有任何 `fetch`／AJAX 呼叫，`file://` 協定不會遇到瀏覽器的同源限制，可以完整看到頁面與所有互動功能。

### 方式 B：本地伺服器（`python3 -m http.server`）

```bash
cd stage1-onepage
python3 -m http.server 8081
```

預期看到：

```
Serving HTTP on :: port 8081 (http://[::]:8081/) ...
```

打開瀏覽器 [http://localhost:8081](http://localhost:8081) 即可看到頁面。

**為什麼零依賴的靜態頁面也示範本地伺服器，而不是只用 `file://`**：`file://` 在本階段夠用，但從 stage2 開始一旦牽涉多頁式相對路徑、之後階段牽涉 `fetch` 呼叫 API，瀏覽器的同源政策會擋掉 `file://` 底下的請求——提早養成「用本地伺服器預覽」的習慣，之後階段轉換會比較順。`python3 -m http.server` 是 Python 標準庫內建的指令，不需要另外安裝任何套件。

### 實測驗證（本次建置實際執行結果）

```bash
$ curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/
200
```

```bash
$ curl -s http://localhost:8081/ | grep -c '<section'
7
$ curl -s http://localhost:8081/ | grep -o 'lang="zh-Hant"'
lang="zh-Hant"
```

```bash
$ node --check js/main.js
（無輸出＝語法正確）
```

```bash
$ for f in $(grep -oE '(href|src)="(css|js|images)/[^"]+"' index.html | sed -E 's/^(href|src)="//; s/"$//' | sort -u); do
    if [ -f "$f" ]; then echo "OK   $f"; else echo "MISSING $f"; fi
  done
OK   css/style.css
OK   images/hero-coffee.svg
OK   images/logo.svg
OK   images/p1.svg
OK   images/p12.svg
OK   images/p4.svg
OK   images/p5.svg
OK   images/store-map.svg
OK   js/main.js
```

全部 9 個本地資源都存在，沒有斷圖斷連結。

## 2. 靜態部署教學（文件指引，非實際代操作）

> 以下步驟為教學指引，實際畫面與按鈕位置以你使用當下的平台介面為準（平台介面會持續更新）。三個平台都是「拖拉資料夾／連 git repo 就自動產生網址」的靜態網站託管服務，不需要任何後端伺服器。

### 選項 A：Cloudflare Pages

1. 到 [pages.cloudflare.com](https://pages.cloudflare.com) 登入（需要 Cloudflare 帳號）。
2. 「Create a project」→ 選擇「Upload assets」（直接上傳資料夾）或連接 GitHub repo。
3. 如果用資料夾上傳：把整個 `stage1-onepage/` 資料夾（含 `index.html`、`css/`、`js/`、`images/`）拖進去，不需要設定 build command（本階段沒有 build step，留空即可）。
4. 部署完成後會拿到一個 `*.pages.dev` 的網址。

### 選項 B：GitHub Pages

1. 把 `stage1-onepage/` 的內容 push 到一個 GitHub repo（或 repo 裡的一個資料夾）。
2. repo 的 Settings → Pages → Source 選擇你的分支與資料夾。
3. 存檔後 GitHub 會產生一個 `https://你的帳號.github.io/repo名稱/` 網址（通常需要等 1-2 分鐘生效）。

### 選項 C：Netlify

1. 到 [app.netlify.com](https://app.netlify.com) 登入。
2. 「Add new site」→「Deploy manually」，把 `stage1-onepage/` 資料夾拖進上傳區。
3. 部署完成後會拿到一個 `*.netlify.app` 的網址。

**三個選項怎麼選**：都是免費方案就能用的靜態託管，功能對本階段來說沒有實質差異，選一個你熟悉、或未來想深入用的平台即可。

## 3. 學員交付檢查表

部署完成後，請自行填寫以下項目（本課程不會替你部署，也不會知道你選了哪個平台）：

- [ ] 部署平台：__________________（Cloudflare Pages／GitHub Pages／Netlify／其他）
- [ ] 線上網址：__________________
- [ ] 手機瀏覽器實測：頁面正常顯示、漢堡選單可展開收合 [ ] 是 [ ] 否
- [ ] 平板／視窗縮放到 768-1023px 寬度：導覽列展開成橫列、商品卡 3 欄 [ ] 是 [ ] 否
- [ ] 桌機／視窗寬度 ≥1024px：商品卡 4 欄 [ ] 是 [ ] 否
- [ ] 倒數計時數字有跳動（等 1 秒重新整理，秒數應該不同） [ ] 是 [ ] 否
- [ ] FAQ 手風琴可以用滑鼠點擊展開/收合，也可以用 Tab+Enter 用鍵盤操作 [ ] 是 [ ] 否
- [ ] 訂閱表單：留空姓名或 email 送出會出現錯誤訊息，兩者都填對送出會顯示成功訊息 [ ] 是 [ ] 否
