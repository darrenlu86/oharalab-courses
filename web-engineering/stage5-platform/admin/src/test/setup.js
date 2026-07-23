import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import { setAuthToken, setUnauthorizedHandler } from '../api/client'

// 跟 frontend/src/test/setup.js 同一套理由：每個測試跑完清掉 localStorage
// （admin 的 token 存在 'brewgo_admin_token_v1'）、還原 fetch mock、重置
// api/client.js 的模組層級狀態，避免上一個測試的登入狀態滲透到下一個測試。
afterEach(() => {
  cleanup()
  window.localStorage.clear()
  vi.unstubAllGlobals()
  setAuthToken(null)
  setUnauthorizedHandler(null)
})
