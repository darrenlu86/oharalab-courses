import { vi } from 'vitest'

// 跟 frontend/src/test/mockApi.js 是同一套「假伺服器」設計，理由不重複展開。
export function stubApi(handlers = {}) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url, options = {}) => {
      if (typeof url !== 'string' || !url.startsWith('/api')) {
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
