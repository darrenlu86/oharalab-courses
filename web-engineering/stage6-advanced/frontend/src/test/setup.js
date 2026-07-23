import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import { setAuthToken, setUnauthorizedHandler } from '../api/client'

// 每個測試跑完做四件事：卸載元件、清空 localStorage（登入 token 存在這裡，
// 不清掉會滲透到下一個測試）、還原所有 vi.stubGlobal（例如 fetch mock）、
// 重置 api/client.js 的模組層級狀態（authToken、unauthorizedHandler）——
// stage3 沒有這一步，是因為 stage3 完全沒有「跨測試會殘留的模組層級狀態」；
// stage4 的 client.js 是單例模組，token 不清掉的話，上一個測試登入過的 token
// 會被下一個測試的 apiFetch 呼叫繼續帶著送出去。
afterEach(() => {
  cleanup()
  window.localStorage.clear()
  vi.unstubAllGlobals()
  setAuthToken(null)
  setUnauthorizedHandler(null)
})
