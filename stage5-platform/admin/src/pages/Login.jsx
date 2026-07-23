import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAdminAuth } from '../context/AdminAuthContext'

// 後台登入頁——刻意沒有「註冊」分頁：管理員帳號只能由 scripts/init_db.py 的
// 種子資料建立（見 backend/scripts/init_db.py），後台本身不提供自助建立管理員
// 帳號的入口，這是刻意的安全邊界（理由跟 AdminAuthContext.jsx 的說明一致）。

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

// 表單驗證：跟 frontend/src/pages/Login.jsx、Checkout.jsx 是同一套寫法——搭配
// <form noValidate> 使用，自己接管驗證邏輯，不依賴瀏覽器內建的 HTML5 驗證氣泡
// （無法客製化中文文案）。這裡故意只檢查「格式」（email 有沒有 @、密碼有沒有
// 填），不檢查「密碼長度是不是 8 碼」——因為登入表單不像註冊表單，帳密錯誤
// 本來就該讓後端判斷（後端不會告訴你「密碼太短」還是「帳號不存在」，一律回
// 「email 或密碼錯誤」，前端沒有必要也沒有立場先幫使用者過濾）；這裡要擋的
// 只是「完全沒填」會讓後端回傳 pydantic 422 陣列、被舊版 client.js 顯示成
// [object Object] 的那個情境。
function validate(email, password) {
  const errors = {}
  if (!EMAIL_PATTERN.test(email.trim())) {
    errors.email = '請輸入正確格式的 email'
  }
  if (password.length === 0) {
    errors.password = '請輸入密碼'
  }
  return errors
}

export default function Login() {
  const { login, isAuthenticated } = useAdminAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState({})
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    const nextErrors = validate(email, password)
    setErrors(nextErrors)
    setError('')
    if (Object.keys(nextErrors).length > 0) {
      return
    }

    setSubmitting(true)
    try {
      await login(email, password)
      navigate('/')
    } catch (err) {
      setError(err.message || '登入失敗，請稍後再試')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="admin-login">
      <form className="admin-login__card" onSubmit={handleSubmit} noValidate>
        <h1 className="admin-login__title">BrewGo 後台管理登入</h1>
        <p className="admin-login__hint">
          測試帳號：admin@brewgo.test ／ 密碼 Admin12345（見 README「測試帳號」一節）
        </p>

        <div className="admin-form-field">
          <label htmlFor="admin-email">Email</label>
          <input
            id="admin-email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
            aria-invalid={errors.email ? 'true' : undefined}
            aria-describedby={errors.email ? 'admin-email-error' : undefined}
          />
          {errors.email && (
            <p className="admin-form-error" id="admin-email-error">
              {errors.email}
            </p>
          )}
        </div>

        <div className="admin-form-field">
          <label htmlFor="admin-password">密碼</label>
          <input
            id="admin-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            aria-invalid={errors.password ? 'true' : undefined}
            aria-describedby={errors.password ? 'admin-password-error' : undefined}
          />
          {errors.password && (
            <p className="admin-form-error" id="admin-password-error">
              {errors.password}
            </p>
          )}
        </div>

        {error && (
          <p className="admin-form-error" role="alert" data-testid="admin-login-error">
            {error}
          </p>
        )}

        <button type="submit" className="admin-btn admin-btn--primary" disabled={submitting}>
          {submitting ? '登入中...' : '登入'}
        </button>
      </form>
    </div>
  )
}
