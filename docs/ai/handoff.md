交出者＝Claude／Sonnet 5.5（workflow 子代理）／effort 未記／main@be5179b／2026-10-01／記錄結構遷移（舊記憶的案例流水已移除，git 歷史可查）

## 進行中
- 無進行中開發。四份教案皆已完成並推上 GitHub，下列為 agent 無法自行驗證的未完事項。

## 待使用者拍板／目視
- `web-engineering/`：未做真實瀏覽器走查（agent 無瀏覽器工具，文件已誠實聲明）；建議本機抽走一次 stage5／stage6 前台結帳與後台看板。
- `meowshop/`：GitHub 上 PRD 的 6 張 Mermaid 圖渲染效果未目視（語法已程式驗證）。
- `weather-data-science/`：GitHub 上 mermaid 渲染與教材觀感待使用者自行瀏覽器走查。
- `weather-data-science/` 已知界線：Windows 未實機驗證；stage5 文字模型誤判僅 2 筆（合成語料太乾淨，報告有專節）；無 metrics.json 落檔，報告數字靠固定 seed 重跑可重現；本地 db（gitignored）已補到 2026-07-23，clone 初始化後只有 2015-2025。

## 已知待修
- `README.md`「使用方式」的 `cd ai-web-courses/<教案資料夾>` 應改為 `cd oharalab-courses/<教案資料夾>`（repo 改名時只改了 clone URL）。
