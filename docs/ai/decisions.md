# 決策紀錄

格式：YYYY-MM-DD｜決定或否決什麼｜理由｜推翻條件｜來源（只增不刪；推翻＝新增一行並標舊行 superseded）

2026-07-22｜四份教案全本地端：Supabase 只文件化不實測，不動用任何雲端資源；「部署連結」類課綱產出以各階段 `docs/DEPLOY.md` 教學＋學員交付檢查表取代，課程不代部署｜使用者明示不串雲端、不動用雲端資源｜使用者改變範圍時｜使用者 2026-07-22 夜間過夜任務授權（meowshop、tsmc 明示不串雲端；weather、web-engineering 依同口徑建置，皆零雲端帳號）
2026-07-24｜`web-engineering/stage6-advanced/ci/github-actions-ci.yml` 刻意不放 repo 根 `.github/workflows/`｜不代學員啟用雲端自動化（GitHub Actions 用量與雲端資源是學員自己的帳號與費用）；理由全文見 `web-engineering/docs/DEPLOYMENT_ROADMAP.md` 第 4 節｜課程改成要實際跑 CI 時｜web-engineering 建置決策
2026-07-24｜四份教案以 `git subtree` 併成單一 monorepo `oharalab-courses`，舊的獨立 repo 自 GitHub 刪除，原始 22 個 commit 歷史全數保留｜使用者不想在 GitHub 開一堆教案 repo，要「資料夾」概念；刪除前實查 0 fork／0 star／0 issue、只有 main 無 tag／release；fresh clone 後 802 項測試／檢查全綠｜需要獨立發佈單一教案時｜使用者 2026-07-24 拍板
