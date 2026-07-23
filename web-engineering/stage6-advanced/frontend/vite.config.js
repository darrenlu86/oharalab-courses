import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 教學點——開發環境代理（proxy）vs 正式合體 serve：
// 開發時前端由 Vite dev server（預設 5173）提供，後端是另一個獨立 process（8006，
// stage6 的埠號跟 stage5 的 8005 錯開，方便兩個階段的伺服器需要同時跑在同一台機器
// 上時不會撞埠號）；瀏覽器發出 fetch('/api/...') 時實際連到的是 5173，如果沒有
// 下面這段 proxy 設定，
// 瀏覽器會回報 CORS 錯誤（兩個不同埠號在瀏覽器眼中就是不同來源）。
// `server.proxy` 讓 Vite dev server 收到 `/api` 開頭的請求時，在伺服器端（不經過瀏覽器）
// 轉發給後端，瀏覽器全程只看到「我在跟 5173 講話」，完全不會觸發 CORS 檢查——
// 這是開發階段最方便的做法，不需要後端額外設定 CORS_ORIGINS。
// `/ws` 這條路徑也要另外設定 proxy 才能轉發 WebSocket 升級請求（`ws: true`）——
// 一般的 `/api` proxy 只處理普通 HTTP，WebSocket 的協定升級（Upgrade: websocket）
// 預設不會被轉發，這是 stage6 新增即時通訊功能後才會踩到的設定，stage5 完全
// 不需要這一段。
// 正式部署（`npm run build` 之後由 FastAPI 用 StaticFiles 直接 serve dist/）則完全不需要
// 這段 proxy：前後端變成同一個來源，瀏覽器發出的請求本來就是同源請求。
// 兩種模式的完整比較見 docs/DEPLOY.md。
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8006',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8006',
        ws: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    css: true,
  },
})
