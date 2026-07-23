// 集中的 fetch 封裝——跟 frontend/src/api/client.js 是同樣的設計（同一套理由不
//重複展開：BASE 用相對路徑、統一帶 token、統一判斷 response.ok）。這裡刻意獨立
// 複製一份，而不是想辦法讓 admin/ 跟 frontend/ 共用同一支檔案：master spec 規定
// 後台是「全新獨立的 Vite React app」（各自的 package.json、各自 build、各自可以
// 單獨部署），跨專案共用原始碼需要額外的 monorepo 工具鏈（例如 workspaces），
// 對初學者是不必要的複雜度，本課程刻意不引入。
const BASE = '/api'

let authToken = null
let unauthorizedHandler = null

export function setAuthToken(token) {
  authToken = token
}

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

// 後端的 {"detail": ...} 欄位有兩種形狀：一般錯誤（例如 404／409／401／403）是
// `detail` 直接一個字串；FastAPI 對 pydantic 驗證失敗（422，例如登入表單 email
// 格式不對）回的 `detail` 則是「每個欄位各一則」的陣列，例如 `[{"loc": ["body",
// "email"], "msg": "value is not a valid email address..."}, ...]`。如果不特別
// 處理，陣列直接被塞進 `new Error(message)`，`message` 會被強制轉成字串
// `"[object Object]"`——這是真的會發生的 bug，不是理論上的邊界情況：只要表單
// 掛了 `noValidate` 卻沒有自己的 client-side validate()，空白內容照樣送得出去，
// 讓後端的 422 驗證直接曝在使用者面前（跟 frontend/src/api/client.js 是同一個
// 問題、同一套修法）。這裡把陣列攤平成「欄位：訊息」再用頓號接起來；如果
// detail 本來就是字串或完全沒有 detail，行為跟以前一樣不變。
function formatErrorDetail(detail, status) {
  if (typeof detail === 'string') {
    return detail
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        const field = Array.isArray(item?.loc) ? item.loc[item.loc.length - 1] : null
        return field ? `${field}：${item.msg}` : item?.msg
      })
      .filter(Boolean)
    if (messages.length > 0) {
      return messages.join('；')
    }
  }
  return `發生未預期的錯誤（HTTP ${status}）`
}

export async function apiFetch(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers ?? {}) }
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`
  }

  let response
  try {
    response = await fetch(`${BASE}${path}`, { ...options, headers })
  } catch (networkError) {
    throw new ApiError('連不上伺服器，請確認後端是否已啟動、或稍後再試一次', 0)
  }

  if ((response.status === 401 || response.status === 403) && unauthorizedHandler) {
    unauthorizedHandler(response.status)
  }

  const rawText = await response.text()
  const data = rawText ? JSON.parse(rawText) : null

  if (!response.ok) {
    const message = formatErrorDetail(data?.detail, response.status)
    throw new ApiError(message, response.status)
  }

  return data
}
