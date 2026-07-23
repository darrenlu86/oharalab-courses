import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiFetch, ApiError, setAuthToken, setUnauthorizedHandler } from './client'

// 跟 frontend/src/api/client.test.js 是同一套測試手法：用 vi.stubGlobal('fetch', ...)
// 假造後端回應，不牽涉任何真的 HTTP 呼叫。這裡只補這個檔案自己獨有的行為
// （detail 陣列轉可讀字串），基本行為（帶 token、判斷 response.ok）已經在
// frontend 那份測試涵蓋過同樣的邏輯，不重複整套。
function mockFetchOnce(response) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: response.status < 400,
      status: response.status,
      text: async () => JSON.stringify(response.body ?? null),
    }),
  )
}

describe('apiFetch（admin）', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    setAuthToken(null)
    setUnauthorizedHandler(null)
  })

  it('非 2xx 狀態會丟出 ApiError，訊息取自後端的 detail 欄位', async () => {
    mockFetchOnce({ status: 404, body: { detail: '找不到這筆訂單' } })
    await expect(apiFetch('/admin/orders/9999')).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      message: '找不到這筆訂單',
    })
  })

  it('detail 是 pydantic 422 驗證陣列時，會轉成可讀的中文字串而不是 [object Object]', async () => {
    mockFetchOnce({
      status: 422,
      body: {
        detail: [
          { type: 'value_error', loc: ['body', 'email'], msg: 'value is not a valid email address' },
          { type: 'missing', loc: ['body', 'password'], msg: 'Field required' },
        ],
      },
    })
    await expect(apiFetch('/auth/login')).rejects.toMatchObject({
      name: 'ApiError',
      status: 422,
      message: 'email：value is not a valid email address；password：Field required',
    })
  })

  it('後端沒有回 detail 欄位時，用通用訊息當 fallback', async () => {
    mockFetchOnce({ status: 500, body: {} })
    await expect(apiFetch('/admin/summary')).rejects.toThrow('HTTP 500')
  })
})
