import { MemoryRouter } from 'react-router-dom'
import { render } from '@testing-library/react'
import { AdminAuthProvider, ADMIN_TOKEN_STORAGE_KEY_FOR_TESTS } from '../context/AdminAuthContext'

// 跟 frontend/src/test/renderWithProviders.jsx 同一套設計：`token` 選項讓測試
// 「已登入狀態」的頁面時，直接把 token 先寫進 localStorage 再 render。
export function renderWithProviders(ui, { route = '/', token = null } = {}) {
  if (token) {
    window.localStorage.setItem(ADMIN_TOKEN_STORAGE_KEY_FOR_TESTS, token)
  }
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AdminAuthProvider>{ui}</AdminAuthProvider>
    </MemoryRouter>,
  )
}
