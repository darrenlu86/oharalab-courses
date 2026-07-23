import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useCart } from '../context/CartContext'
import { formatCurrency } from '../utils/formatCurrency'
import { apiFetch, ApiError } from '../api/client'

// 跟 stage4 的差異——結帳從「一步」變成「兩步」，這個頁面只負責第一步：
// stage4 送出表單當下同時完成「建單」跟「（沒有真的存在的）付款」，因為那時候
// 根本沒有付款這個概念。本階段有了真正的 `/api/payments/mock`，於是結帳自然
// 拆成兩個各自獨立的頁面：
//   這一頁（Checkout）：填收件資訊 → 呼叫 `POST /api/orders` 建立一筆
//   status='pending' 的訂單（這時還沒扣庫存，見
//   backend/app/routers/orders.py 開頭的說明），建好之後導去 `/pay/:orderId`。
//   下一頁（`pages/Pay.jsx`）：對這筆訂單呼叫 `POST /api/payments/mock`，
//   這裡才是真正「確定要買」的時刻，付款成功才會扣庫存、訂單狀態才會變成 'paid'。
// 把付款頁拆成獨立路由（而不是同一個元件內用 state 切換畫面）的好處：使用者可以
// 從「我的訂單」（見 pages/Orders.jsx）直接連回一筆 pending/failed 訂單的付款頁
// 繼續付款，不需要重新走一次收件資訊表單、也不會意外建出第二筆重複訂單。
const INITIAL_FORM = {
  recipientName: '',
  address: '',
}

function validateAddressForm(form) {
  const errors = {}
  if (form.recipientName.trim().length === 0) {
    errors.recipientName = '請填寫收件人姓名'
  }
  if (form.address.trim().length < 6) {
    errors.address = '請填寫完整收件地址（至少 6 個字）'
  }
  return errors
}

export default function Checkout() {
  const { items, subtotal, refreshCart } = useCart()
  const navigate = useNavigate()
  const [form, setForm] = useState(INITIAL_FORM)
  const [errors, setErrors] = useState({})
  const [submitError, setSubmitError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (items.length === 0) {
    return (
      <div className="container section">
        <h1 className="section__title">結帳</h1>
        <p className="empty-state">
          購物車是空的，沒有可以結帳的商品。<Link to="/products">去逛逛商品</Link>
        </p>
      </div>
    )
  }

  const handleChange = (field) => (event) => {
    setForm((prev) => ({ ...prev, [field]: event.target.value }))
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    const nextErrors = validateAddressForm(form)
    setErrors(nextErrors)
    setSubmitError('')
    if (Object.keys(nextErrors).length > 0) {
      return
    }

    setSubmitting(true)
    try {
      const order = await apiFetch('/orders', {
        method: 'POST',
        body: JSON.stringify({
          recipient_name: form.recipientName.trim(),
          recipient_address: form.address.trim(),
        }),
      })
      // 建單成功時後端已經清空了伺服器端的購物車（見 backend/app/routers/orders.py），
      // 這裡呼叫 refreshCart() 讓 Header 的購物車徽章立刻反映「購物車是空的」。
      await refreshCart()
      navigate(`/pay/${order.id}`)
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : '送出訂單失敗，請稍後再試')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="container section">
      <h1 className="section__title">結帳</h1>
      <p className="mock-notice">
        送出訂單只是登記「想買這些東西」（訂單狀態會是 pending），不會扣庫存、也還沒有付款；
        下一步的付款頁才會真正扣減庫存，付款成功前隨時可以在「我的訂單」取消這筆訂單。
      </p>

      <div className="checkout-grid">
        <form className="checkout-form" onSubmit={handleSubmit} noValidate>
          <div className="form-field">
            <label htmlFor="recipientName">收件人姓名</label>
            <input
              id="recipientName"
              type="text"
              value={form.recipientName}
              onChange={handleChange('recipientName')}
              aria-invalid={errors.recipientName ? 'true' : undefined}
              aria-describedby={errors.recipientName ? 'recipientName-error' : undefined}
            />
            {errors.recipientName && (
              <p className="form-error" id="recipientName-error">
                {errors.recipientName}
              </p>
            )}
          </div>

          <div className="form-field">
            <label htmlFor="address">收件地址</label>
            <input
              id="address"
              type="text"
              value={form.address}
              onChange={handleChange('address')}
              aria-invalid={errors.address ? 'true' : undefined}
              aria-describedby={errors.address ? 'address-error' : undefined}
            />
            {errors.address && (
              <p className="form-error" id="address-error">
                {errors.address}
              </p>
            )}
          </div>

          {submitError && (
            <p className="form-error" role="alert" data-testid="checkout-error">
              {submitError}
            </p>
          )}

          <button type="submit" className="btn btn--primary" disabled={submitting}>
            {submitting ? '送出中...' : '下一步：付款'}
          </button>
        </form>

        <aside className="checkout-summary">
          <h2 className="section__title">訂單摘要</h2>
          <ul className="checkout-summary__list">
            {items.map((item) => (
              <li key={item.product_id}>
                <span>
                  {item.name} × {item.quantity}
                </span>
                <span>{formatCurrency(item.subtotal)}</span>
              </li>
            ))}
          </ul>
          <div className="checkout-summary__total">
            <span>總計</span>
            <span>{formatCurrency(subtotal)}</span>
          </div>
        </aside>
      </div>
    </div>
  )
}
