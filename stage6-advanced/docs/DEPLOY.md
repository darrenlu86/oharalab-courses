# 部署指引

回上層：[stage6 README](../README.md)

> **金流警示：本站的付款功能是自建的模擬金流（mock payment），完全沒有串接
> 任何真實的第三方金流服務，不會有任何一筆真實金錢往來。** 不管你在付款頁面
> 輸入什麼卡號，都只是後端用「卡號字串」做規則判斷（見
> [`API.md`](API.md) 測試卡號表），不會、也不可能真的請款。**請勿把本專案
> 原封不動拿去對外收費使用。**

跟 stage4（一個前端＋一個後端）不一樣，stage5 開始有三個各自獨立的部署單位：
後端（`backend/`）、前台（`frontend/`）、後台（`admin/`），stage6 沿用這個
拓樸沒有改變，只是後端多了 WebSocket／SSE 兩種連線類型，部署時需要多注意
一件事（見下方「(d) WebSocket 部署注意事項」）。本文件分四段：
(a) 本地驗證方式（下面全部指令都是本次撰寫教材時實際執行過的，附貼實測輸出）、
(b) 主流平台部署教學（**教學指引，沒有真的部署到任何雲端平台**）、
(c) 學員交付檢查表、(d) WebSocket 部署注意事項（stage6 新增）。

## 部署拓撲圖

```mermaid
flowchart TB
    subgraph 選項一：三合一單一 process（最省事，本教材預設教學路徑）
        A1["後端 process<br/>uvicorn app.main:app"] -->|serve /| A2["frontend/dist"]
        A1 -->|serve /admin| A3["admin/dist"]
    end
    subgraph 選項二：前台/後台分開部署到靜態平台
        B1["後端 API（Cloud Run / Render）"]
        B2["frontend（Cloudflare Pages）"] -->|CORS_ORIGINS 需列入| B1
        B3["admin（另一個 Cloudflare Pages 專案，或同一個後端 /admin）"] -->|CORS_ORIGINS 需列入| B1
    end
```

## (a) 本地驗證方式（已實測）

### 開發分離模式（推薦用來開發）

三個 process 各自獨立啟動：後端 uvicorn（8006，跟 stage5 的 8005 錯開）、
前台 Vite dev server（5173，proxy `/api` 與 `/ws` 到 8006）、後台 Vite dev
server（5176，跟 stage5 後台的 5175 錯開，proxy `/api` 與 `/ws` 到 8006）。

**後端**：
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/init_db.py
uvicorn app.main:app --port 8006
```
實測輸出（`init_db.py`）：
```
建立資料表於：/你的路徑/backend/data/brewgo.db
已匯入 12 筆種子商品資料。
已建立管理員帳號：admin@brewgo.test（id=1）
已建立顧客測試帳號：customer@brewgo.test（id=2）
已匯入 7 筆示範訂單（含對應 payments 紀錄）。
SQLite 資料庫初始化完成！
```
`curl http://localhost:8006/api/health` 實測回應：
```json
{"status":"ok"}
```

**前台**（另開一個終端機視窗）：
```bash
cd frontend
npm install
npm run dev
```
瀏覽器打開 `http://localhost:5173/` 會看到 BrewGo 首頁。

**後台**（再另開一個終端機視窗）：
```bash
cd admin
npm install
npm run dev
```
瀏覽器打開 `http://localhost:5176/admin/` 會看到後台登入頁（記得網址要有
`/admin/` 這段路徑，因為 `vite.config.js` 設了 `base: '/admin/'`）。

### 正式合體模式（模擬正式部署的單一 process）

前台、後台各自先 build 成靜態檔案，後端偵測到 `frontend/dist/` 與
`admin/dist/` 存在就會分別掛載，整個網站只需要啟動一個 process：

```bash
cd frontend && npm run build
```
本次實測輸出：
```
dist/index.html                   0.66 kB │ gzip:  0.46 kB
dist/assets/index-BXkVcSyj.css   12.41 kB │ gzip:  2.81 kB
dist/assets/index-10nhKOe1.js   268.91 kB │ gzip: 84.00 kB

✓ built in 447ms
```

```bash
cd ../admin && npm run build
```
本次實測輸出：
```
dist/index.html                   0.47 kB │ gzip:  0.31 kB
dist/assets/index-W5vmnr0h.css    5.78 kB │ gzip:  1.64 kB
dist/assets/index-Bj50AXTf.js   253.30 kB │ gzip: 79.51 kB

✓ built in 436ms
```

```bash
cd ../backend
source .venv/bin/activate
uvicorn app.main:app --port 8006
```

實測驗證（同一台機器上跑）：
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8006/
# 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:8006/admin
# 307（沒有結尾斜線會先轉址到 /admin/，見 backend/app/main.py 的 redirect_admin_root）
curl -s -o /dev/null -w "%{http_code}" http://localhost:8006/admin/
# 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:8006/products/5
# 200 —— 前台 react-router 的 client-side 路徑，SPA fallback 正常運作
curl -s -o /dev/null -w "%{http_code}" http://localhost:8006/admin/orders
# 200 —— 後台 react-router 的 client-side 路徑，另一組 SPA fallback 正常運作
```

### 教學點——為什麼要有兩組獨立的 SPA fallback，順序還不能寫反

跟 stage4 一樣，react-router 的 client-side 路徑（例如 `/products/5`）在伺服器
端沒有對應的實體檔案，需要「找不到就回 index.html」的 catch-all 路由接住。
stage5 有兩個 SPA（前台、後台），如果前台的 catch-all（`GET
/{full_path:path}`，語法上會吃掉任何路徑）比後台那組先註冊，所有 `/admin/*`
的請求都會被前台搶先攔截，後台永遠進不去——所以 `backend/app/main.py` 裡
後台的路由必須寫在前台的 catch-all**之前**，完整程式碼與註解見該檔案。

## (b) 主流平台部署教學（教學指引，未實際部署）

> 以下步驟沒有在任何雲端平台實際操作過，是依照各平台公開文件整理的教學指引，
> 實際畫面與選項請以你當下登入的平台介面為準。

### 選項一：三合一單一 process（推薦，最省事）

跟本地的正式合體模式完全一樣的做法搬到雲端：`frontend/` 跟 `admin/` 都先
`npm run build`，把兩份 `dist/` 一起打進後端的容器（或跟後端擺在同一台機器
上），部署 `backend/` 這一個服務即可，前台跟後台同時上線。適合 Google Cloud
Run / Render / Railway 這類能跑 Python container 的 PaaS。

環境變數（`SECRET_KEY`、`CORS_ORIGINS`）改在平台的環境變數設定介面填入，
**不要**把正式的 `SECRET_KEY` 寫死進程式碼或 commit 進 git；正式環境務必換成
長隨機字串（`.env.example` 有附產生指令 `openssl rand -hex 32`）。

### 選項二：前台/後台分開部署到靜態平台

前台、後台各自 build 後放到靜態網站平台（Cloudflare Pages、GitHub Pages、
Vercel），後端單獨部署成 API 服務。要注意三件事：

1. 後端 `.env` 的 `CORS_ORIGINS` 要同時列入前台跟後台各自的網址（逗號分隔），
   例如 `CORS_ORIGINS=https://your-frontend.pages.dev,https://your-admin.pages.dev`。
2. `frontend/src/api/client.js` 與 `admin/src/api/client.js` 的 `BASE` 都是
   寫死的相對路徑 `'/api'`。如果前台/後台跟後端分開部署到不同網域，**必須
   手動修改這兩個常數**成後端的完整網址——這是刻意的教學簡化，理由跟 stage4
   `docs/DEPLOY.md` 的同一個限制一致（沒有引入 build-time 環境變數機制）。
3. `admin/vite.config.js` 的 `base: '/admin/'` 是為了「後端把後台掛在
   `/admin` 路徑下」這個假設而設的。如果後台改成獨立網域部署（不再掛在後端
   底下的 `/admin` 路徑），要把這個 `base` 改回 `'/'`，否則 build 出來的資源
   網址會多一層用不到的 `/admin/` 前綴。

### 環境變數與 `SECRET_KEY` 管理

所有機密（`SECRET_KEY`）一律用平台的環境變數設定介面或 Secret Manager 類
服務管理，絕對不要進 git；`.env` 已經被 `.gitignore` 排除，部署前再檢查一次
`git status` 確認沒有意外把機密內容 commit 進去。前台跟後台是純靜態檔案，
沒有機密可管理。

**程式啟動會自動警告**：`SECRET_KEY` 只要還是預設值 `dev-secret-change-me`，
後端啟動時就會在終端機（stderr）印出一段醒目的多行安全警告（見
`app/config.py` 的 `warn_if_default_secret_key()`）——本機開發看到這個警告
可以忽略，但部署前如果還看得到它，代表 `SECRET_KEY` 還沒換成正式的隨機值，
務必先處理再繼續部署。

### 測試帳號聲明範本（部署後放在你的作業說明裡）

```
管理員測試帳號：admin@brewgo.test / Admin12345
顧客測試帳號：  customer@brewgo.test / Customer12345
（以上帳號由 backend/scripts/init_db.py 的種子資料建立，僅供評分/展示使用，
 不是真實個人資料。）
```

### 資料庫

SQLite 檔案存在容器裡，容器重啟/重新部署容易連同資料一起消失——這是本課程
刻意保留的已知限制（跟 stage4 一致），正式產品通常會換成獨立的雲端資料庫，
本教材不處理這部分。

## (c) 學員交付檢查表

課程本身不代學員部署，交作業前請自行完成以下項目並填上你自己的連結：

- [ ] 後端已部署，`curl <你的網址>/api/health` 回 `{"status":"ok"}`
- [ ] 前台可以正常開啟，走過一次完整流程：註冊 → 登入 → 加入購物車 →
      結帳建單（確認庫存未扣）→ 付款（先用失敗卡號測試重試、再用成功卡號
      測試扣庫存）→ 我的訂單查看狀態
- [ ] 後台可以正常開啟，用 `admin@brewgo.test` 登入，走過一次：看 Dashboard
      數字 → 商品管理（試著下架一件、確認前台看不到）→ 訂單管理（把一筆
      paid 訂單標記出貨、完成）→ 會員清單
- [ ] 用 customer 帳號的 token 打 `/api/admin/summary`，確認回 403（不是 401）
- [ ] 正式環境的 `SECRET_KEY` 已經換成長隨機字串（不是 `.env.example` 裡的
      `dev-secret-change-me`）
- [ ] 後台開著訂單管理頁，另開一個瀏覽器視窗以顧客身分下單，確認後台**不用
      重新整理**就跳出新訂單提示（驗證 WebSocket 在部署環境真的能連得上，
      見下方「(d) WebSocket 部署注意事項」）
- [ ] 客服頁輸入問題，確認文字是逐字跳出來（SSE 串流），不是等全部回覆
      產生完才一次顯示
- [ ] 後端部署網址：`___________________________`
- [ ] 前台網址（若分開部署）：`___________________________`
- [ ] 後台網址：`___________________________`
- [ ] 測試帳號已在作業說明裡明確列出（照上方範本）

## (d) WebSocket 部署注意事項（stage6 新增）

> 以下同樣是**教學指引**，沒有實際部署驗證過，請以你使用的平台官方文件為準。

WebSocket 是長連線（跟一般 HTTP 請求「發出去、收回應、結束」不一樣，
連線會保持開啟直到雙方主動關閉），部署時容易踩到兩類坑：

1. **反向代理／負載平衡器要開啟 WebSocket 支援**：Nginx 預設不會自動轉發
   `Upgrade: websocket` 這個 HTTP header，需要額外設定
   `proxy_set_header Upgrade $http_upgrade;` 這類指令；如果用的是平台代管
   的負載平衡器（例如 Cloud Run、Render），通常已經內建支援，但仍建議部署
   後實際測試一次連線（見上方檢查表）。
2. **多 instance／自動擴展環境**：如果部署平台會依流量自動開多個
   instance（例如 Cloud Run 的自動擴展），使用者的 WebSocket 連線會固定在
   「當初接受這個連線的那個 instance」，但本課程的 `ConnectionManager`／
   `TTLCache` 都是**只存在單一 process 記憶體裡**的狀態（見
   [`ARCHITECTURE.md`](ARCHITECTURE.md)「uvicorn workers」一節），多
   instance 情境下會出現「連在 instance A 的使用者收不到 instance B
   處理的訂單事件」這種不一致。教學規模建議部署時把 instance 數量鎖定為 1
   （多數 PaaS 平台的免費方案本來就是這樣），要真正支援多 instance 需要
   引入 Redis Pub/Sub，本課程刻意不實作，見 `ARCHITECTURE.md` 該節的完整
   說明。
