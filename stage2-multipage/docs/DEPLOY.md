# 部署指引

本課程不代學員部署，這份文件分三塊：(1) 本地驗證方式（已實測，附實際指令輸出）、
(2) 主流平台部署步驟（教學指引，實際畫面以平台當下介面為準）、(3) 學員交付檢查表。

## 一、本地驗證（已實測）

在 `stage2-multipage/` 目錄下執行：

```bash
python3 -m http.server 8082
```

預期輸出：

```
Serving HTTP on :: port 8082 (http://[::]:8082/) ...
```

**驗證 1：10 個頁面逐一 curl，全部應回應 200**

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

**驗證 2：連結完整性檢查**（掃描全部 html 內的 `href`/`src`，確認目標檔案存在）：

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

**驗證 3：sitemap.xml 內容**

```bash
curl -s http://localhost:8082/sitemap.xml
```

預期看到 9 個 `<url>` 區塊（9 個內容頁，不含 `404.html`），完整清單見 `docs/SITEMAP.md`。

**驗證 4：JS 語法檢查**

```bash
node --check js/include.js && node --check js/site.js
```

預期沒有任何輸出（沒有錯誤訊息＝語法通過）。

**驗證完記得關閉伺服器**：在跑 `python3 -m http.server` 的終端機視窗按 `Ctrl+C`，
或用 `kill <pid>` 結束背景執行的 process（例如用 `lsof -i :8082` 查出 pid）。

**誠實聲明：本地 `http.server` 不會套用自訂 404.html**：實測打一個不存在的網址（例如 `http://localhost:8082/not-a-real-page`）會拿到 Python 內建的英文錯誤頁（`<title>Error response</title>`），不是這個專案的 `404.html`。`python3 -m http.server` 只是最陽春的靜態檔案伺服器，沒有「找不到頁面就轉導到自訂 404 頁」這種設定機制；`404.html -> 200` 的驗證只代表「直接打這個檔名可以正常開啟」，不代表本地環境已經具備自訂 404 行為。這個行為要部署到正式的靜態主機（GitHub Pages、Cloudflare Pages 等，見下方步驟）才會生效——這些平台本身有「找不到檔案就套用 404.html」的機制，本地開發伺服器沒有，這是兩碼事。

## 二、主流平台部署步驟（教學指引，未實測）

> 以下步驟為教學指引，本課程沒有實際申請帳號跑過這幾個平台，實際畫面與選項名稱以平台當下介面為準。
> 三個平台的共通點：這是純靜態網站（沒有 build 指令），部署設定都是「發布目錄=專案根目錄，不需要 build command」。

### 選項 A：GitHub Pages

1. 把 `stage2-multipage/` 內容 push 到一個 GitHub repo（可以是這個 repo 的子目錄，也可以另開一個 repo，只放這個資料夾的內容）。
2. Repo 設定裡的 **Settings → Pages**，Source 選擇要發布的分支與資料夾。
3. 儲存後，GitHub 會給一個 `https://<你的帳號>.github.io/<repo>/` 網址。
4. GitHub Pages 原生支援把 `404.html` 當作自訂錯誤頁，不需要額外設定。

### 選項 B：Cloudflare Pages

1. 到 Cloudflare Pages 建立新專案，連接你的 GitHub repo。
2. Build 設定：**Build command 留空**、**Build output directory 填 `stage2-multipage`**（或你 repo 的實際路徑）。
3. 部署完成後會拿到 `https://<專案名>.pages.dev` 網址。
4. Cloudflare Pages 同樣會自動辨識根目錄的 `404.html` 作為錯誤頁。

### 選項 C：Netlify

1. 到 Netlify 用「Import from Git」匯入 repo。
2. Build 設定同樣留空 build command，Publish directory 填 `stage2-multipage`。
3. 部署完成後會拿到 `https://<專案名>.netlify.app` 網址。

### 部署後一定要做的事：把佔位網域換成實際網域

`docs/SITEMAP.md` 提過，`sitemap.xml`、`robots.txt`、每個頁面的 `<link rel="canonical">`
與 `og:url` 目前都寫死 `https://www.brewgo-demo.example`（RFC 2606 保留的範例網域，故意打不開）。
部署到真實網址後，要把這幾個地方全部換成你實際拿到的網址，例如全域搜尋取代：

```bash
grep -rl "brewgo-demo.example" . | xargs sed -i '' 's#https://www.brewgo-demo.example#https://你的實際網域#g'
```

> 上面這行指令是 macOS/BSD `sed` 的寫法（`-i ''`），Linux 的 GNU `sed`語法是 `-i` 後面直接接規則、不需要空字串參數。這行指令沒有在本次建置中實際執行過（因為還沒有真實網域），使用前請自行確認語法符合你的作業系統。

換完網域後，把 `sitemap.xml` 的網址提交到 [Google Search Console](https://search.google.com/search-console)：
新增資源、驗證網域擁有權，再到「Sitemaps」分頁貼上 `https://你的網域/sitemap.xml` 送出。
這一步是手動操作，Search Console 沒有無金鑰的公開 API 可以讓程式自動完成。

## 三、學員交付檢查表

部署完成後，請自行填上你的實際結果：

- [ ] 部署平台：______________________
- [ ] 網站網址：______________________
- [ ] 10 個頁面（index / products / 3 個商品詳情頁 / about / stores / faq / contact / 404）都能正常打開
- [ ] 已將 `sitemap.xml`、`robots.txt`、canonical、`og:url` 換成實際網域
- [ ] 手機寬度（模擬或實機）確認漢堡選單與版型正常收合
- [ ] `products.html` 的分類頁籤能正確篩選、網址列有帶上 `?category=`
- [ ] `contact.html` 表單在空白/錯誤格式時會顯示對應錯誤訊息，全部填對後顯示成功訊息
- [ ] （選填）已提交 sitemap 到 Google Search Console
