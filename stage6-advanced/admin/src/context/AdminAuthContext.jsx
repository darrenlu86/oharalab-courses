import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch, setAuthToken, setUnauthorizedHandler } from '../api/client'

// 後台的登入狀態管理——跟 frontend/src/context/AuthContext.jsx 是同一套 Context
// 設計，但多了一件事：**登入時檢查 role 是不是 'admin'**，不是 admin 就直接
// 擋在前端、不儲存 token（後端本來就會用 require_admin 擋掉所有 /api/admin/*
// 端點，這裡的前端檢查只是「提早給使用者明確的錯誤訊息」，不是唯一的防線——
// 就算有人跳過前端、直接拿 customer 的 token 打 /api/admin/*，後端一樣會回 403）。
//
// TOKEN_STORAGE_KEY 刻意跟前台的 'brewgo_token_v1' 不同：正式部署時前台跟後台
// 掛在同一個網站（同源，只是路徑不同），瀏覽器的 localStorage 是「整個網站共用」
// 而不是分路徑的，如果兩邊用同一把 key，登入其中一邊會把另一邊的登入狀態蓋掉。
const TOKEN_STORAGE_KEY = 'brewgo_admin_token_v1'

const AdminAuthContext = createContext(null)

export function AdminAuthProvider({ children }) {
  const navigate = useNavigate()
  const [token, setToken] = useState(() => window.localStorage.getItem(TOKEN_STORAGE_KEY))
  const [user, setUser] = useState(null)
  const [status, setStatus] = useState('checking')

  function logout() {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY)
    setAuthToken(null)
    setToken(null)
    setUser(null)
  }

  useEffect(() => {
    setUnauthorizedHandler(() => {
      logout()
      navigate('/login')
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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
        if (cancelled) return
        if (data.role !== 'admin') {
          // token 有效但不是管理員（例如手動改了 localStorage）：一律登出，
          // 跟登入當下擋非 admin 帳號是同一套判斷邏輯。
          logout()
        } else {
          setUser(data)
        }
        setStatus('ready')
      })
      .catch(() => {
        if (!cancelled) setStatus('ready')
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
    if (data.user.role !== 'admin') {
      // 刻意不儲存這個 token：非 admin 帳號登入本站一律視為失敗，回一句清楚的
      // 中文錯誤訊息，不要讓使用者以為「登入成功但看不到任何東西」。
      throw new Error('這個帳號不是管理員，無法登入後台')
    }
    window.localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token)
    setAuthToken(data.access_token)
    setToken(data.access_token)
    setUser(data.user)
    return data.user
  }

  const value = useMemo(
    () => ({
      token,
      user,
      isAuthenticated: Boolean(user),
      isChecking: status === 'checking',
      login,
      logout,
    }),
    [token, user, status],
  )

  return <AdminAuthContext.Provider value={value}>{children}</AdminAuthContext.Provider>
}

export function useAdminAuth() {
  const context = useContext(AdminAuthContext)
  if (!context) {
    throw new Error('useAdminAuth 必須在 <AdminAuthProvider> 內使用')
  }
  return context
}

export const ADMIN_TOKEN_STORAGE_KEY_FOR_TESTS = TOKEN_STORAGE_KEY
