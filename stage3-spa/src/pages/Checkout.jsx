import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useCart } from '../context/CartContext'
import { formatCurrency } from '../utils/formatCurrency'
import { generateOrderId } from '../utils/generateOrderId'
import { saveOrder } from '../utils/ordersStorage'

const INITIAL_FORM = {
  recipientName: '',
  phone: '',
  address: '',
  note: '',
}

function validate(form) {
  const errors = {}
  if (form.recipientName.trim().length === 0) {
    errors.recipientName = '請填寫收件人姓名'
  }
  if (!/^09\d{8}$/.test(form.phone.trim())) {
    errors.phone = '請填寫正確格式的手機號碼（例如 0912345678）'
  }
  if (form.address.trim().length < 6) {
    errors.address = '請填寫完整收件地址（至少 6 個字）'
  }
  return errors
}

export default function Checkout() {
  const { items, subtotal, clearCart } = useCart()
  const navigate = useNavigate()
  const [form, setForm] = useState(INITIAL_FORM)
  const [errors, setErrors] = useState({})

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

  const handleSubmit = (event) => {
    event.preventDefault()
    const nextErrors = validate(form)
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) {
      return
    }

    // mock 訂單：沒有金流、沒有後端，這裡只是把目前購物車內容連同收件資訊
    // 一起包成一筆物件、存進 localStorage。真實網站的下單流程還會有庫存鎖定、
    // 建立付款、等金流回呼確認等步驟（見 README「與上一階段的差異」的誠實聲明）。
    const order = {
      id: generateOrderId(),
      createdAt: new Date().toISOString(),
      recipient: {
        name: form.recipientName.trim(),
        phone: form.phone.trim(),
        address: form.address.trim(),
        note: form.note.trim(),
      },
      items,
      subtotal,
    }
    saveOrder(order)
    clearCart()
    navigate(`/order-complete/${order.id}`)
  }

  return (
    <div className="container section">
      <h1 className="section__title">結帳</h1>
      <p className="mock-notice">
        本站沒有串接任何真實金流，這裡的「送出訂單」只會把資料存在你目前這台裝置的瀏覽器裡，不會實際請款。
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
            />
            {errors.recipientName && <p className="form-error">{errors.recipientName}</p>}
          </div>

          <div className="form-field">
            <label htmlFor="phone">聯絡手機</label>
            <input id="phone" type="tel" value={form.phone} onChange={handleChange('phone')} />
            {errors.phone && <p className="form-error">{errors.phone}</p>}
          </div>

          <div className="form-field">
            <label htmlFor="address">收件地址</label>
            <input id="address" type="text" value={form.address} onChange={handleChange('address')} />
            {errors.address && <p className="form-error">{errors.address}</p>}
          </div>

          <div className="form-field">
            <label htmlFor="note">備註（選填）</label>
            <textarea id="note" value={form.note} onChange={handleChange('note')} rows={3} />
          </div>

          <button type="submit" className="btn btn--primary">
            送出訂單
          </button>
        </form>

        <aside className="checkout-summary">
          <h2 className="section__title">訂單摘要</h2>
          <ul className="checkout-summary__list">
            {items.map((item) => (
              <li key={item.id}>
                <span>
                  {item.name} × {item.quantity}
                </span>
                <span>{formatCurrency(item.price * item.quantity)}</span>
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
