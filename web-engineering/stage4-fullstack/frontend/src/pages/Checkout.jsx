import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useCart } from '../context/CartContext'
import { formatCurrency } from '../utils/formatCurrency'
import { apiFetch, ApiError } from '../api/client'

// 跟 stage3 的差異：
// 1. 表單欄位從「姓名／手機／地址／備註」簡化成「姓名／地址」兩欄——因為後端
//    `OrderCreateIn`（見 backend/app/schemas.py）目前只收 recipient_name /
//    recipient_address 這兩個欄位。這是刻意的教學簡化：真實訂單系統的收件資訊
//    通常會更完整（手機、備註、多筆收件地址管理），本階段的教學重點是「前後端
//    如何串接一支會寫入資料庫、會扣庫存的 API」，不是把收件表單的欄位做齊全，
//    要加欄位只需要同時改 schemas.py / database.py 的 schema 與這裡的表單。
// 2. 「送出訂單」不再是把物件存進 localStorage，而是打 POST /api/orders，
//    由後端在資料庫裡真正建立訂單、扣庫存、清空購物車——這裡完全不用自己組
//    訂單編號（stage3 的 generateOrderId()），因為後端會用資料庫的 AUTOINCREMENT
//    id 保證全域唯一，比前端用 Math.random() 產生的編號可靠得多。
// 3. 建單可能會失敗（例如結帳這幾秒內庫存被別人買走了），要接住 409/400 並顯示錯誤，
//    stage3 的 mock 版本因為只是存 localStorage，不可能「送出訂單失敗」。
const INITIAL_FORM = {
  recipientName: '',
  address: '',
}

function validate(form) {
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
    const nextErrors = validate(form)
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
      // 後端建單成功時已經清空了伺服器端的購物車，這裡呼叫 refreshCart() 讓
      // Header 的購物車徽章、以及等一下如果按「繼續選購」回到 Cart 頁都能立刻
      // 反映「購物車是空的」，不用等下一次自然重新整理。
      await refreshCart()
      navigate(`/order-complete/${order.id}`)
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
        本站沒有串接任何真實金流，送出訂單後會直接在資料庫成立一筆狀態為「pending」的訂單並扣減庫存，
        但不會有任何金錢往來，也不會有商品實際出貨。
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
            {submitting ? '送出中...' : '送出訂單'}
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
