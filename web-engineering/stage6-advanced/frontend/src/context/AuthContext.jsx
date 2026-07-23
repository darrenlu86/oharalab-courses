import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch, setAuthToken, setUnauthorizedHandler } from '../api/client'

// stage4 新增的 Context：stage3 完全沒有「登入」這個概念，商品資料是打包進前端的
// 靜態 JSON，購物車跟訂單都不需要知道「這是誰的」。現在有了真實後端，購物車與
// 訂單都必須綁在某個帳號底下（伺服器端才擋得住「改別人的購物車」），所以需要
// 一個全站共享的「目前登入的是誰」狀態——設計理由跟 CartContext 是同一套邏輯
// （Context + 集中管理），這裡不重複展開。

const TOKEN_STORAGE_KEY = 'brewgo_token_v1'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const navigate = useNavigate()
  const [token, setToken] = useState(() => window.localStorage.getItem(TOKEN_STORAGE_KEY))
  const [user, setUser] = useState(null)
  // 'checking'：頁面剛載入、還在用舊 token 跟後端確認身份；'ready'：已經確認完畢
  // （不管有沒有登入）。這個狀態存在的理由：如果不等 'checking' 結束就直接判斷
  // 「沒有 user 就是沒登入」，重新整理頁面時會有一瞬間誤判成「訪客」，
  // 觸發不必要的畫面閃爍（例如購物車圖示先閃出訪客版、一秒後才變回登入版）。
  const [status, setStatus] = useState('checking')

  function logout() {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY)
    setAuthToken(null)
    setToken(null)
    setUser(null)
  }

  // 註冊「收到 401 該怎麼辦」：清掉登入態、導去登入頁。放在 useEffect 裡只註冊一次，
  // client.js 是模組層級的單例，不需要每次 render 都重新註冊。
  useEffect(() => {
    setUnauthorizedHandler(() => {
      logout()
      navigate('/login')
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // token 一變動（登入、登出、或頁面載入時讀到舊 token）就同步給 client.js，
  // 並且用這個 token 去跟後端要一次「我是誰」，藉此驗證 token 到底還有沒有效
  // （可能已經過期，或是使用者手動改了 localStorage 塞一個假的）。
  useEffect(() => {
    setAuthToken(token)
    if (!token) {
      setUser(null)
      setStatus('ready')
      return
    }
    let cancelled = false
    apiFetch('/auth/me')
      .then((data) => {
        if (!cancelled) {
          setUser(data)
          setStatus('ready')
        }
      })
      .catch(() => {
        // token 失效（過期/被竄改）：/auth/me 會回 401，client.js 的 unauthorizedHandler
        // 已經處理了登出，這裡只需要把 loading 狀態收尾即可。
        if (!cancelled) {
          setStatus('ready')
        }
      })
    return () => {
      cancelled = true
    }
  }, [token])

  async function login(email, password) {
    const data = await apiFetch('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    window.localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token)
    setAuthToken(data.access_token)
    setToken(data.access_token)
    setUser(data.user)
    return data.user
  }

  async function register(email, password, name) {
    // 註冊本身不會回傳 token（跟 login 是分開的兩支 API，見 docs/API.md），
    // 所以註冊成功後緊接著呼叫一次 login，讓使用者註冊完就直接是登入狀態，
    // 不用「註冊完 → 跳回登入頁 → 再手動輸入一次帳密」這種多一步的體驗。
    await apiFetch('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, name }),
    })
    return login(email, password)
  }

  const value = useMemo(
    () => ({
      token,
      user,
      isAuthenticated: Boolean(user),
      isChecking: status === 'checking',
      login,
      register,
      logout,
    }),
    [token, user, status],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth 必須在 <AuthProvider> 內使用')
  }
  return context
}

export const AUTH_TOKEN_STORAGE_KEY_FOR_TESTS = TOKEN_STORAGE_KEY
