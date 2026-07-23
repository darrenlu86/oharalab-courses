# 部署指引

回上層：[stage4 README](../README.md)

跟 stage1-3（純靜態或純前端）不一樣，stage4 有一個真正要「跑起來」的後端
process，部署選項也變多了。本文件分三段：(a) 本地驗證方式（下面全部指令都是
本次撰寫教材時實際執行過的，附貼實測輸出）、(b) 主流平台部署教學（**教學指引，
沒有真的部署到任何雲端平台，實際操作畫面請以你使用的平台當下介面為準**）、
(c) 學員交付檢查表。

## (a) 本地驗證方式（已實測）

### 開發分離模式（推薦用來開發）

前後端各自獨立啟動，前端用 Vite dev server（5173），後端用 uvicorn（8004），
中間靠 [`vite.config.js`](../frontend/vite.config.js) 的 `server.proxy` 設定
把 `/api` 轉給後端——這是本階段開發時的預設模式，改一行前端程式碼存檔就會
立刻反映（Vite 的 Hot Module Replacement），不需要重新 build。

**後端**：
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/init_db.py
uvicorn app.main:app --port 8004
```
預期看到 log 出現 `Application startup complete.`；`curl http://localhost:8004/api/health`
實測回應：
```json
{"status":"ok"}
```

**前端**（另開一個終端機視窗）：
```bash
cd frontend
npm install
npm run dev
```
預期看到終端機印出本地網址（`http://localhost:5173/`），瀏覽器打開會看到
BrewGo 首頁；這個模式下前端所有 `/api/...` 請求會被 Vite 自動轉給 8004 的後端，
瀏覽器開發者工具的 Network 分頁看到的請求網址仍然是 `localhost:5173`（同源，
不會有 CORS 錯誤）。

### 正式合體模式（模擬正式部署的單一 process）

前端先 build 成靜態檔案，後端偵測到 `frontend/dist/` 存在就會直接把它 serve
出來（見 [`backend/app/main.py`](../backend/app/main.py)），整個網站只需要
啟動一個 process：

```bash
# 1. 前端 build
cd frontend
npm run build
```
本次實測輸出：
```
dist/index.html                   0.66 kB │ gzip:  0.46 kB
dist/assets/index-MKKrbm6k.css   10.77 kB │ gzip:  2.44 kB
dist/assets/index-DwWsUXhp.js   259.89 kB │ gzip: 81.69 kB

✓ built in 451ms
```

```bash
# 2. 啟動後端（會自動偵測到 frontend/dist 並掛載）
cd ../backend
source .venv/bin/activate
uvicorn app.main:app --port 8004
```

實測驗證（同一台機器上跑）：
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8004/
# 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:8004/products/5
# 200 —— 這是 react-router 的 client-side 路徑，伺服器本來沒有這個檔案，
#         能回 200 代表 SPA fallback（見 main.py 的 serve_spa()）正常運作
curl -s -o /dev/null -w "%{http_code}" http://localhost:8004/assets/index-DwWsUXhp.js
# 200
```

### 教學點——為什麼正式模式需要額外的 SPA fallback（跟 meowshop 的差異）

meowshop 前端是純多頁 HTML，每個網址都對應一個真實檔案，`StaticFiles(html=True)`
就夠用。stage3/4 前端是 react-router 的 client-side routing，瀏覽器網址列的
`/products/5` 在伺服器端根本沒有對應檔案——直接訪問這個網址（重新整理、或
分享連結給別人）如果沒有特別處理，伺服器會回 404，即使前端 App 本身完全正常。
`main.py` 用一個「吃掉其他所有路徑」的 catch-all 路由解決這個問題：找不到對應
的靜態檔案就一律回傳 `index.html`，交給前端的 react-router 自己判斷要顯示哪個
頁面（包含判斷是不是真的要顯示 404 頁）。完整程式碼與註解見
`backend/app/main.py` 的 `serve_spa()`。

## (b) 主流平台部署教學（教學指引，未實際部署）

> 以下步驟沒有在任何雲端平台實際操作過，是依照各平台公開文件整理的教學指引，
> 實際畫面與選項請以你當下登入的平台介面為準。

### 後端：任何能跑 Python container 的 PaaS（Google Cloud Run / Render / Railway）

1. 把 `backend/` 打包成容器，或用平台原生支援直接執行
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`。
2. 環境變數（`SECRET_KEY`、`CORS_ORIGINS`）改在平台的環境變數設定介面填入，
   **不要**把正式的 `SECRET_KEY` 寫死進程式碼或 commit 進 git；正式環境務必
   換成長隨機字串（`.env.example` 有附產生指令 `openssl rand -hex 32`）。
3. SQLite 檔案存在容器裡，容器重啟/重新部署容易連同資料一起消失——這是
   SQLite 適合教學/本機開發、不適合正式多副本環境的已知限制；正式產品通常會
   換成獨立的雲端資料庫（PostgreSQL/MySQL），這是刻意留給更後面階段（或學員
   自己）的延伸，本教材不在 stage4 處理。
4. HTTPS 由部署平台提供（Cloud Run、Render 等主流 PaaS 預設都有）。

### 前端：跟後端同一個 process 一起 serve（最省事），或拆開部署

**選項 1（推薦，最省事）**：`npm run build` 產出的 `frontend/dist/` 由後端的
`main.py` 自動 serve，部署後端的同時前端也一起上線，只需要一個服務。

**選項 2（前後端分開部署）**：前端另外放到靜態網站平台（Cloudflare Pages、
GitHub Pages、Vercel），要注意兩件事：

1. 後端 `.env` 的 `CORS_ORIGINS` 要改成前端實際網址（例如
   `CORS_ORIGINS=https://your-frontend.pages.dev`），不能再用開發預設的 `*`。
2. 前端 `src/api/client.js` 目前的 `BASE` 是寫死的相對路徑 `'/api'`（同源請求）。
   如果前後端分開部署，**必須手動修改這個常數**成後端的完整網址（例如
   `const BASE = 'https://your-api.example.com/api'`）——本專案目前沒有做成
   環境變數/build-time 設定，這是刻意的教學簡化，理由跟 meowshop
   `frontend/js/api.js` 的同一個限制一致：沒有引入額外的 build-time 環境變數
   機制，要拆分部署請自己改這一行程式碼。

### 金鑰管理原則

所有機密（`SECRET_KEY`）一律用平台的環境變數設定介面或 Secret Manager 類服務
管理，絕對不要進 git；`.env` 已經被 `.gitignore` 排除，部署前再檢查一次
`git status` 確認沒有意外把機密內容 commit 進去。

**程式啟動會自動警告**：`SECRET_KEY` 只要還是預設值 `dev-secret-change-me`，
後端啟動時就會在終端機（stderr）印出一段醒目的多行安全警告（見
`app/config.py` 的 `warn_if_default_secret_key()`）——本機開發看到這個警告
可以忽略，但部署前如果還看得到它，代表 `SECRET_KEY` 還沒換成正式的隨機值，
務必先處理再繼續部署。

## (c) 學員交付檢查表

課程本身不代學員部署，交作業前請自行完成以下項目並填上你自己的連結：

- [ ] 後端已部署到你選擇的平台，`curl <你的網址>/api/health` 回 `{"status":"ok"}`
- [ ] 前端可以正常開啟（合體模式：跟後端同網址；分離部署：確認 `client.js` 的
      `BASE` 已經改成後端完整網址、後端 `CORS_ORIGINS` 已經改成前端網址）
- [ ] 正式環境的 `SECRET_KEY` 已經換成長隨機字串（不是 `.env.example` 裡的
      `dev-secret-change-me`）
- [ ] 走過一次完整流程：註冊 → 登入 → 加入購物車 → 結帳送出訂單 → 訂單查詢，
      確認庫存有跟著扣減（重新整理商品頁確認數字有變）
- [ ] 部署網址：`___________________________`（你的後端／合體網址）
- [ ] 前端網址（若分開部署）：`___________________________`
