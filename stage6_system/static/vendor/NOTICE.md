# Vendored third-party 檔案

## chart.umd.min.js

- 套件：[Chart.js](https://www.chartjs.org/)
- 版本：4.4.4
- 授權：MIT（見同目錄 `CHARTJS_LICENSE.md`，2026-07-24 從官方 GitHub repo
  `chartjs/Chart.js` 的 `LICENSE.md` 原文複製）
- 來源：`https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js`
  （2026-07-24 下載）
- **為什麼 vendored 進 repo 而不是掛 CDN**：SPEC 明確要求儀表板避免外網
  依賴——本課程全程可離線執行，掛 CDN 會讓 `stage6_system` 在沒有網路的
  環境下整頁圖表失效（教學現場常見離線授課情境）。vendored 之後，
  `stage6_system/templates/base.html` 用 `/static/vendor/chart.umd.min.js`
  這個本地路徑載入，不對外發任何請求。
- 這是本課程唯一一份非本課程作者撰寫、直接複製第三方原始碼的檔案；其餘
  全部程式碼與文件皆為本課程原創。
