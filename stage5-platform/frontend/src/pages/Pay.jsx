import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiFetch, ApiError } from '../api/client'
import { formatCurrency } from '../utils/formatCurrency'

// stage5 全新頁面——結帳兩步流程的第二步（第一步見 pages/Checkout.jsx 開頭的說明）。
// 這頁本身不建立訂單，只針對「已經存在、狀態是 pending 或 failed」的訂單嘗試付款，
// 訂單 id 直接從網址帶進來（`/pay/:orderId`），可以從結帳流程導過來，也可以從
// 「我的訂單」（pages/Orders.jsx）點一筆 pending/failed 訂單的「去付款」連結過來——
// 兩個入口共用同一個頁面，不用維護兩套付款表單邏輯。

// 測試卡號表——比照 meowshop 的規則，顯示在付款頁面上，讓學員操作時知道要
// 打哪組卡號才能示範「付款失敗、可以重試」這個情境。
const TEST_CARDS = [
  { number: '4242 4242 4242 4242', result: '付款成功' },
  { number: '4000 0000 0000 0002', result: '付款失敗（可重新輸入卡號重試）' },
  { number: '其他任意 13-19 碼數字', result: '一律視為成功（教學上示範用 4242 那組即可）' },
]

// 這幾種狀態代表「這筆訂單目前不能付款」——已經付過（paid/shipped/completed）
// 或已經取消，理由跟後端 app/order_state.py 的 PAYMENT_ALLOWED_FROM 是同一份規則，
// 前端這裡只是提前擋一次、給使用者更明確的訊息，真正擋住重複付款的仍然是後端。
const NOT_PAYABLE_MESSAGE = {
  paid: '這筆訂單已經付款完成，不需要再付款一次。',
  shipped: '這筆訂單已經出貨，不需要再付款一次。',
  completed: '這筆訂單已經完成，不需要再付款一次。',
  cancelled: '這筆訂單已經取消，無法付款。',
}

export default function Pay() {
  const { orderId } = useParams()
  const navigate = useNavigate()

  const [order, setOrder] = useState(null)
  const [loadStatus, setLoadStatus] = useState('loading')

  const [cardNumber, setCardNumber] = useState('4242 4242 4242 4242')
  const [cardHolder, setCardHolder] = useState('')
  const [paymentError, setPaymentError] = useState('')
  const [paying, setPaying] = useState(false)

  useEffect(() => {
    let cancelled = false
    apiFetch(`/orders/${orderId}`)
      .then((data) => {
        if (!cancelled) {
          setOrder(data)
          setLoadStatus('ready')
        }
      })
      .catch((err) => {
        if (cancelled) return
        setLoadStatus(err instanceof ApiError && err.status === 404 ? 'not-found' : 'error')
      })
    return () => {
      cancelled = true
    }
  }, [orderId])

  if (loadStatus === 'loading') {
    return (
      <div className="container section">
        <p className="empty-state">訂單讀取中...</p>
      </div>
    )
  }

  if (loadStatus !== 'ready') {
    return (
      <div className="container section">
        <p className="empty-state">
          找不到這筆訂單（可能不是你帳號底下的訂單，或訂單編號不存在）。
          <Link to="/orders">查看我的訂單</Link>
        </p>
      </div>
    )
  }

  if (order.status in NOT_PAYABLE_MESSAGE) {
    return (
      <div className="container section">
        <h1 className="section__title">付款</h1>
        <p className="empty-state">
          {NOT_PAYABLE_MESSAGE[order.status]}
          <Link to={`/order-complete/${order.id}`}>查看訂單詳情</Link>
        </p>
      </div>
    )
  }

  const handleSubmitPayment = async (event) => {
    event.preventDefault()
    setPaymentError('')
    setPaying(true)
    try {
      const result = await apiFetch('/payments/mock', {
        method: 'POST',
        body: JSON.stringify({
          order_id: order.id,
          card_number: cardNumber,
          card_holder: cardHolder.trim() || order.recipient_name,
        }),
      })
      if (result.payment.status === 'success') {
        navigate(`/order-complete/${order.id}`)
        return
      }
      // 付款失敗：後端把訂單狀態改成了 'failed'，但訂單本身還在，允許使用者
      // 換一組卡號重新嘗試（見 backend/app/order_state.py 的 PAYMENT_ALLOWED_FROM）。
      setOrder(result.order)
      setPaymentError('付款失敗（測試卡號 4000 0000 0000 0002 一律失敗），請換一組卡號重試。')
    } catch (err) {
      setPaymentError(err instanceof ApiError ? err.message : '付款失敗，請稍後再試')
    } finally {
      setPaying(false)
    }
  }

  return (
    <div className="container section">
      <h1 className="section__title">付款</h1>
      <p className="mock-notice">
        本站沒有串接任何真實金流，這是自建的模擬付款（mock payment）：後端只是讀「卡號字串」做規則判斷，
        不會、也不可能真的請款。訂單 #{order.id} 目前狀態是「{order.status}」，庫存要等付款成功才會扣減。
      </p>

      <div className="checkout-grid">
        <form className="checkout-form" onSubmit={handleSubmitPayment} noValidate>
          <div className="form-field">
            <label htmlFor="cardHolder">持卡人姓名</label>
            <input
              id="cardHolder"
              type="text"
              value={cardHolder}
              onChange={(event) => setCardHolder(event.target.value)}
              placeholder={order.recipient_name}
            />
          </div>

          <div className="form-field">
            <label htmlFor="cardNumber">測試卡號</label>
            <input
              id="cardNumber"
              type="text"
              value={cardNumber}
              onChange={(event) => setCardNumber(event.target.value)}
            />
          </div>

          <div className="test-card-table-wrap">
            <table className="test-card-table">
              <thead>
                <tr>
                  <th>卡號</th>
                  <th>結果</th>
                </tr>
              </thead>
              <tbody>
                {TEST_CARDS.map((card) => (
                  <tr key={card.number}>
                    <td>{card.number}</td>
                    <td>{card.result}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {paymentError && (
            <p className="form-error" role="alert" data-testid="payment-error">
              {paymentError}
            </p>
          )}

          <button type="submit" className="btn btn--primary" disabled={paying}>
            {paying ? '付款處理中...' : '送出付款'}
          </button>
        </form>

        <aside className="checkout-summary">
          <h2 className="section__title">訂單摘要</h2>
          <ul className="checkout-summary__list">
            {order.items.map((item) => (
              <li key={item.product_id}>
                <span>
                  {item.product_name} × {item.quantity}
                </span>
                <span>{formatCurrency(item.unit_price * item.quantity)}</span>
              </li>
            ))}
          </ul>
          <div className="checkout-summary__total">
            <span>總計</span>
            <span>{formatCurrency(order.total_amount)}</span>
          </div>
        </aside>
      </div>
    </div>
  )
}
