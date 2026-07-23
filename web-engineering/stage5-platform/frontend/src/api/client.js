// 集中的 fetch 封裝——stage4 新增的檔案，是這一階段前端最重要的改動之一。
//
// stage3 完全沒有這個檔案，因為 stage3 沒有後端可以呼叫；現在每個頁面/元件都要
// 呼叫真正的後端 API，如果讓每個檔案各自寫一次「組完整網址、帶 token、判斷
// response.ok、解析錯誤訊息」，這幾件事一定會有檔案漏做（例如漏帶 token、
// 漏處理非 2xx 狀態），集中寫成一個函式，全站呼叫 API 只有一個入口。
//
// 為什麼 BASE 是相對路徑 '/api'，不是寫死完整網址（例如 'http://localhost:8004/api'）：
// 這樣同一份程式碼在「開發模式」（vite proxy 把 /api 轉給後端）跟「正式合體模式」
// （FastAPI 用 StaticFiles 直接 serve 這份前端 build 產物，前後端同源）下都能正確運作，
// 完全不用依開發/正式環境切換設定值。如果真的要把前後端分開部署到不同網域，
// 這個常數就必須改成後端的完整網址——這是刻意的教學簡化，做法跟取捨寫在
// docs/DEPLOY.md「前後端分開部署」一節。

const BASE = '/api'

let authToken = null
let unauthorizedHandler = null

export function setAuthToken(token) {
  authToken = token
}

export function getAuthToken() {
  return authToken
}

// AuthProvider 掛載時會呼叫這個函式，登記「收到 401 時該做什麼」（清掉登入態、
// 導去 /login）。client.js 本身是普通的 JS 模組，不在 React 元件樹裡，沒辦法直接
// 呼叫 useNavigate()，所以用「登記一個 callback」的方式讓 React 那一側決定要做什麼，
// 這裡只負責「偵測到 401 就去呼叫它」。
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

// 後端的 {"detail": ...} 欄位有兩種形狀：一般錯誤（例如 404／409／401）是
// `detail` 直接一個字串；FastAPI 對 pydantic 驗證失敗（422，例如註冊表單
// email 格式不對、密碼太短）回的 `detail` 則是「每個欄位各一則」的陣列，
// 例如 `[{"loc": ["body", "email"], "msg": "value is not a valid email
// address..."}, ...]`。如果不特別處理，陣列直接被塞進 `new Error(message)`，
// `message` 會被強制轉成字串 `"[object Object]"`——這是真的會發生的 bug，
// 不是理論上的邊界情況：只要有表單掛了 `noValidate`、卻沒有自己的
// client-side validate()，空白或格式不對的內容照樣送得出去，讓後端的 422
// 驗證直接曝在使用者面前。這裡把陣列攤平成「欄位：訊息」再用頓號接起來，
// 使用者至少看得懂是哪個欄位出了什麼問題；如果 detail 本來就是字串或
// 完全沒有 detail，行為跟以前一樣不變。
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

// 統一的 fetch 封裝：自動帶 BASE、自動附 Authorization header（如果有登入）、
// 統一判斷 response.ok、統一從後端的 {"detail": "..."} 格式取出錯誤訊息。
// 呼叫端（頁面/Context）永遠可以假設：成功就拿到解析好的 JSON，失敗就是丟出
// ApiError，不需要自己重複判斷 status code 或呼叫 response.json()。
export async function apiFetch(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers ?? {}) }
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`
  }

  let response
  try {
    response = await fetch(`${BASE}${path}`, { ...options, headers })
  } catch (networkError) {
    // fetch 本身丟例外代表連網路都沒發出去（斷網、後端整個沒啟動），
    // 跟「後端有回應但回傳錯誤狀態碼」是不同層次的失敗，這裡統一包成同一種
    // ApiError，讓呼叫端不用分別處理兩種例外型別。
    throw new ApiError('連不上伺服器，請確認後端是否已啟動、或稍後再試一次', 0)
  }

  if (response.status === 401 && unauthorizedHandler) {
    unauthorizedHandler()
  }

  // 204 No Content 或空 body 的情況，text() 會是空字串，不能直接丟給 JSON.parse。
  const rawText = await response.text()
  const data = rawText ? JSON.parse(rawText) : null

  if (!response.ok) {
    const message = formatErrorDetail(data?.detail, response.status)
    throw new ApiError(message, response.status)
  }

  return data
}
