import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

// 每個測試跑完都做三件事：卸載元件、清空 localStorage（購物車/訂單都存在這裡，
// 不清掉的話上一個測試留下的資料會滲透到下一個測試）、還原所有 vi.stubGlobal（例如 fetch mock）。
afterEach(() => {
  cleanup()
  window.localStorage.clear()
  vi.unstubAllGlobals()
})
