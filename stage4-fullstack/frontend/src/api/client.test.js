import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiFetch, ApiError, getAuthToken, setAuthToken, setUnauthorizedHandler } from './client'

// stage4 新增的測試檔案：client.js 是本階段最重要的新增檔案（stage3 完全沒有
// 這一層），所以要單獨測試它自己的行為，不透過任何頁面元件。
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

describe('apiFetch', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    setAuthToken(null)
    setUnauthorizedHandler(null)
  })

  it('成功時回傳解析好的 JSON', async () => {
    mockFetchOnce({ status: 200, body: { status: 'ok' } })
    const data = await apiFetch('/health')
    expect(data).toEqual({ status: 'ok' })
  })

  it('會自動幫請求加上 /api 前綴', async () => {
    mockFetchOnce({ status: 200, body: { status: 'ok' } })
    await apiFetch('/health')
    expect(fetch).toHaveBeenCalledWith('/api/health', expect.any(Object))
  })

  it('已登入時會自動附上 Authorization header', async () => {
    setAuthToken('abc123')
    mockFetchOnce({ status: 200, body: {} })
    await apiFetch('/auth/me')
    const [, options] = fetch.mock.calls[0]
    expect(options.headers.Authorization).toBe('Bearer abc123')
  })

  it('未登入時不會附上 Authorization header', async () => {
    mockFetchOnce({ status: 200, body: {} })
    await apiFetch('/products')
    const [, options] = fetch.mock.calls[0]
    expect(options.headers.Authorization).toBeUndefined()
  })

  it('非 2xx 狀態會丟出 ApiError，訊息取自後端的 detail 欄位', async () => {
    mockFetchOnce({ status: 404, body: { detail: '找不到這個商品' } })
    await expect(apiFetch('/products/9999')).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      message: '找不到這個商品',
    })
  })

  it('後端沒有回 detail 欄位時，用通用訊息當 fallback', async () => {
    mockFetchOnce({ status: 500, body: {} })
    await expect(apiFetch('/health')).rejects.toThrow('HTTP 500')
  })

  it('detail 是 pydantic 422 驗證陣列時，會轉成可讀的中文字串而不是 [object Object]', async () => {
    mockFetchOnce({
      status: 422,
      body: {
        detail: [
          { type: 'value_error', loc: ['body', 'email'], msg: 'value is not a valid email address' },
          { type: 'string_too_short', loc: ['body', 'password'], msg: 'String should have at least 8 characters' },
        ],
      },
    })
    await expect(apiFetch('/auth/register')).rejects.toMatchObject({
      name: 'ApiError',
      status: 422,
      message: 'email：value is not a valid email address；password：String should have at least 8 characters',
    })
  })

  it('fetch 本身失敗（斷網/後端沒啟動）時，丟出可讀的 ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(apiFetch('/health')).rejects.toBeInstanceOf(ApiError)
  })

  it('收到 401 時會呼叫已註冊的 unauthorizedHandler', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    mockFetchOnce({ status: 401, body: { detail: '請先登入' } })

    await expect(apiFetch('/auth/me')).rejects.toMatchObject({ status: 401 })
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('setAuthToken / getAuthToken 是同一份模組層級狀態', () => {
    setAuthToken('token-xyz')
    expect(getAuthToken()).toBe('token-xyz')
  })
})
