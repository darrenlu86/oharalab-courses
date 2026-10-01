# AGENTS.md — oharalab-courses

四份教學範例（`weather-data-science/`、`web-engineering/`、`tsmc-stock-analysis/`、`meowshop/`）的 monorepo，**公開 repo**。教案地圖與使用方式見 `README.md`，各教案細節見其自己的 README／DEVELOPMENT.md，這裡只放改動前必須知道的約束。

## 約束
- **公開 repo**：新增或修改內容前確認不含個資、客戶名、本機絕對路徑、憑證、備份路徑。
- **全本地端，不接雲端**：Supabase 在 `meowshop/`、`tsmc-stock-analysis/` 是文件化選項，程式碼完整但從未實際連線；不要加入真實雲端串接、帳號或憑證。付款是自建模擬金流，不接真實金流。
- **各 `.env` 只放教學佔位值**，且被各教案的 `.gitignore` 擋住；不要放真實憑證。
- **`web-engineering/stage6-advanced/ci/github-actions-ci.yml` 是教材，刻意不放根目錄 `.github/workflows/`**（不代學員啟用雲端自動化）；「部署連結」類產出＝各階段 `docs/DEPLOY.md` 教學，課程不代部署。
- **教材裡標「實測」的數字**（測試數、壓測、build hash、npm 套件數）在任何修改後都要重跑；已全部加浮動但書。報告類產物中「城市×數值」「類別×筆數」這種配對敘述，驗收時獨立重算，不只檢查數字存在（曾兩度出現對調）。
- **簡體字掃描**用 OpenCC 字表並排除同形字；靠 grep 常用字表會漏（如「够」）也會誤報（如「群」「峰」）。
- 各教案各自獨立、沒有共用程式碼，虛擬環境與套件各自安裝。

## Git
- 教案以 `git subtree` 併入：舊 commit 內檔案路徑在原 repo 根層，`git log -- <子資料夾>` 只看得到合併點之後，看全歷史用不帶路徑的 `git log`。
- 大型 push 遇 HTTP 400「遠端意外掛斷」且誤導性顯示 "Everything up-to-date"：先 `git config http.postBuffer 524288000` 再推；push 後用 `git rev-parse origin/main` 對本地 HEAD 驗證，不信 push 的文字輸出。
- 備份 gitignored 檔案後，立即把備份模式（如 `data/*.bak*`）補進 `.gitignore`（tsmc 教案曾差點讓備份進版控）。

## 記錄
進行中事項 `docs/ai/handoff.md`；決策 `docs/ai/decisions.md`。
