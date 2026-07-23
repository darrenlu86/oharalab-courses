import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import { AuthProvider } from './context/AuthContext'
import { CartProvider } from './context/CartContext'
import { ExchangeRateProvider } from './context/ExchangeRateContext'

// Provider 順序有意義：AuthProvider 跟 CartProvider 都要用到 react-router 的
// useNavigate()，所以兩者都必須在 <BrowserRouter> 之內；CartProvider 內部會呼叫
// useAuth() 判斷「現在是不是登入狀態」，所以 AuthProvider 必須包在 CartProvider
// 外層（先有登入狀態，購物車才能決定要不要去打 API）。
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <ExchangeRateProvider>
          <CartProvider>
            <App />
          </CartProvider>
        </ExchangeRateProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
