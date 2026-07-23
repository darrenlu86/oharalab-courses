import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 後台是完全獨立的 Vite React app（跟 frontend/ 是兩個各自 build、各自 package.json
// 的專案），共用同一個後端 API（見 backend/app/main.py）。開發時跑在 5176（跟
// stage5 後台的 5175 錯開，方便兩個階段同時跑在同一台機器上時不會撞埠號），
// proxy 設定跟 frontend/vite.config.js 是同一套道理，這裡不重複展開；`/ws` 那段
// 的用途（WebSocket 需要獨立設定 `ws: true` 才會轉發協定升級請求）也一樣。
//
// `base: '/admin/'` 是這個設定檔跟 frontend/ 最關鍵的差異：正式部署時，後端會把
// 這個 app 的 build 產物掛在 `/admin` 這個路徑下（見 main.py 的
// `_ADMIN_DIST` 那段），如果不設 base，build 出來的資源網址會是 `/assets/xxx.js`
// （從網站根目錄找），但實際檔案是掛在 `/admin/assets/xxx.js`，瀏覽器會抓錯路徑。
// 設了 `base: '/admin/'` 之後，build 產物裡的資源網址會自動變成
// `/admin/assets/xxx.js`，跟後端的掛載路徑一致。
export default defineConfig({
  base: '/admin/',
  plugins: [react()],
  server: {
    port: 5176,
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
