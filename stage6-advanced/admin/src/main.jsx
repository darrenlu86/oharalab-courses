import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import { AdminAuthProvider } from './context/AdminAuthContext'

// `basename="/admin"` 讓 react-router 產生的所有路徑（<Link to="/products">…）
// 自動補上 `/admin` 前綴，元件內部完全不需要自己手動拼路徑；正式部署時後端把
// 這個 app 掛在 `/admin` 下（見 backend/app/main.py），開發時 Vite dev server
// 也是用同一個 base（見 vite.config.js 的 `base: '/admin/'`），兩種模式的網址
// 結構因此保持一致。
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter basename="/admin">
      <AdminAuthProvider>
        <App />
      </AdminAuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
