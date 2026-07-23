import { MemoryRouter } from 'react-router-dom'
import { render } from '@testing-library/react'
import { AuthProvider, AUTH_TOKEN_STORAGE_KEY_FOR_TESTS } from '../context/AuthContext'
import { CartProvider } from '../context/CartContext'
import { ExchangeRateProvider } from '../context/ExchangeRateContext'

// 跟 stage3 的差異：多包了一層 AuthProvider（順序跟 main.jsx 一致），並且多支援
// 一個 `token` 選項——測試「登入狀態下」的頁面時，直接把 token 先寫進
// localStorage 再 render，AuthProvider 掛載時會自己讀到、呼叫 /auth/me 驗證。
export function renderWithProviders(ui, { route = '/', token = null } = {}) {
  if (token) {
    window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY_FOR_TESTS, token)
  }
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AuthProvider>
        <ExchangeRateProvider>
          <CartProvider>{ui}</CartProvider>
        </ExchangeRateProvider>
      </AuthProvider>
    </MemoryRouter>,
  )
}
