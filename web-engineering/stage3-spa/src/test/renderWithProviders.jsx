import { MemoryRouter } from 'react-router-dom'
import { render } from '@testing-library/react'
import { CartProvider } from '../context/CartContext'
import { ExchangeRateProvider } from '../context/ExchangeRateContext'

// 共用的測試 render helper：把「跑元件測試會用到的三層 Provider」包成一個函式，
// 每支測試檔就不用重複寫同一段 wrapper。route 預設 '/'，需要測特定網址的元件（例如
// ProductDetail 需要知道 :id）可以傳 route 進來。
export function renderWithProviders(ui, { route = '/' } = {}) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <ExchangeRateProvider>
        <CartProvider>{ui}</CartProvider>
      </ExchangeRateProvider>
    </MemoryRouter>,
  )
}
