import { vi } from 'vitest'

// 測試用的最小 fetch 假伺服器：只認得 `/api` 開頭的路徑，依「METHOD 路徑」
// （query string 不算在 key 裡）對照到呼叫端傳進來的 handler 函式。
// 為什麼要這樣做，而不是每支測試各自寫一個 `vi.fn().mockResolvedValueOnce(...)`：
// stage4 很多頁面掛載時會連續打好幾支 API（例如 AuthProvider 先打 /auth/me，
// CartProvider 才接著打 /cart），用「路由表」的方式統一處理，測試案例只要
// 宣告「這個路徑該回什麼」，不用管呼叫順序，測試比較不容易因為實作內部呼叫
// 順序微調就跟著壞掉。
export function stubApi(handlers = {}) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url, options = {}) => {
      if (typeof url !== 'string' || !url.startsWith('/api')) {
        // 非 `/api` 開頭的請求（例如 ExchangeRateProvider 打的外部匯率 API）一律
        // 模擬斷網——測試環境不可以打真網路，這點跟 stage3 的測試守則一致。
        return Promise.reject(new Error('network disabled in test'))
      }
      const method = (options.method ?? 'GET').toUpperCase()
      const path = url.slice('/api'.length).split('?')[0]
      const key = `${method} ${path}`
      const handler = handlers[key]
      if (!handler) {
        return Promise.reject(new Error(`測試沒有替這個請求設定假回應：${key}`))
      }
      const result = handler(options, url)
      return Promise.resolve({
        ok: result.status < 400,
        status: result.status,
        text: async () => JSON.stringify(result.body ?? null),
      })
    }),
  )
}
