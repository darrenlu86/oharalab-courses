import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { ApiError } from '../api/client'

// stage4 全新頁面：stage3 完全沒有登入功能。用單一頁面搭配兩個分頁（登入／註冊）
// 而不是兩個獨立網址，是常見的教學簡化——真實產品也常常這樣做（例如 email 已存在時
// 可以直接切去登入分頁、保留已輸入的 email），不算偷工減料。

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

// 表單驗證：跟 pages/Checkout.jsx 的 validate() 是同一種寫法（純函式，輸入目前的
// form 物件，回傳「欄位名 → 錯誤訊息」的物件）。這個頁面故意搭配 <form noValidate>
// 使用，不能只靠瀏覽器內建的 HTML5 驗證（required／type="email"／minLength）：
// 內建驗證的錯誤氣泡不能客製化中文文案，樣式也沒辦法跟站內其他表單的錯誤訊息
// 一致，而且完全不會擋下「送出後才發現密碼只有 3 碼」這種情境去阻止畫面閃一下
// 再顯示錯誤。這裡自己接管驗證邏輯：HTML 屬性（required、type="email"、
// minLength）留著當作「支援的瀏覽器仍會做基本檢查」的保險，真正決定擋不擋
// 送出、顯示什麼訊息的是這個函式。
function validate(form, tab) {
  const errors = {}
  if (!EMAIL_PATTERN.test(form.email.trim())) {
    errors.email = '請輸入正確格式的 email'
  }
  if (form.password.length < 8) {
    errors.password = '密碼至少需要 8 碼'
  }
  if (tab === 'register' && form.name.trim().length === 0) {
    errors.name = '請填寫姓名'
  }
  return errors
}

export default function Login() {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const [tab, setTab] = useState('login')
  const [form, setForm] = useState({ email: '', password: '', name: '' })
  const [errors, setErrors] = useState({})
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleChange = (field) => (event) => {
    setForm((prev) => ({ ...prev, [field]: event.target.value }))
  }

  const switchTab = (nextTab) => {
    setTab(nextTab)
    setError('')
    setErrors({})
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    const nextErrors = validate(form, tab)
    setErrors(nextErrors)
    setError('')
    if (Object.keys(nextErrors).length > 0) {
      return
    }

    setSubmitting(true)
    try {
      if (tab === 'login') {
        await login(form.email, form.password)
      } else {
        await register(form.email, form.password, form.name)
      }
      navigate('/products')
    } catch (err) {
      // ApiError 的 message 就是後端回傳的中文錯誤訊息（例如「email 或密碼錯誤」
      // 「這個 email 已經註冊過了」），直接顯示給使用者看即可，不需要另外翻譯。
      setError(err instanceof ApiError ? err.message : '發生未預期的錯誤，請稍後再試')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="container section auth-page">
      <h1 className="section__title">會員登入</h1>

      <div className="auth-tabs" role="tablist" aria-label="登入或註冊">
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'login'}
          className={tab === 'login' ? 'auth-tab is-active' : 'auth-tab'}
          onClick={() => switchTab('login')}
        >
          登入
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'register'}
          className={tab === 'register' ? 'auth-tab is-active' : 'auth-tab'}
          onClick={() => switchTab('register')}
        >
          註冊新帳號
        </button>
      </div>

      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        {tab === 'register' && (
          <div className="form-field">
            <label htmlFor="name">姓名</label>
            <input
              id="name"
              type="text"
              value={form.name}
              onChange={handleChange('name')}
              required
              aria-invalid={errors.name ? 'true' : undefined}
              aria-describedby={errors.name ? 'name-error' : undefined}
            />
            {errors.name && (
              <p className="form-error" id="name-error">
                {errors.name}
              </p>
            )}
          </div>
        )}

        <div className="form-field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            value={form.email}
            onChange={handleChange('email')}
            required
            aria-invalid={errors.email ? 'true' : undefined}
            aria-describedby={errors.email ? 'email-error' : undefined}
          />
          {errors.email && (
            <p className="form-error" id="email-error">
              {errors.email}
            </p>
          )}
        </div>

        <div className="form-field">
          <label htmlFor="password">密碼</label>
          <input
            id="password"
            type="password"
            value={form.password}
            onChange={handleChange('password')}
            minLength={8}
            required
            aria-invalid={errors.password ? 'true' : undefined}
            aria-describedby={errors.password ? 'password-error' : undefined}
          />
          {tab === 'register' && !errors.password && <p className="form-hint">至少 8 碼</p>}
          {errors.password && (
            <p className="form-error" id="password-error">
              {errors.password}
            </p>
          )}
        </div>

        {error && (
          <p className="form-error" role="alert" data-testid="auth-error">
            {error}
          </p>
        )}

        <button type="submit" className="btn btn--primary" disabled={submitting}>
          {submitting ? '處理中...' : tab === 'login' ? '登入' : '註冊並登入'}
        </button>
      </form>

      <p className="auth-page__note">
        本站沒有寄送任何驗證信，註冊後就直接視為已驗證的帳號——這是教學簡化，真實產品
        通常需要 email 驗證流程確認信箱是本人的，避免有人拿別人的 email 亂註冊。
        <Link to="/">回首頁</Link>
      </p>
    </div>
  )
}
