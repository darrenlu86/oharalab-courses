import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiFetch, ApiError } from '../api/client'
import { formatCurrency } from '../utils/formatCurrency'

const STATUS_LABEL = {
  pending: '待付款',
  paid: '已付款',
  failed: '付款失敗',
  shipped: '已出貨',
  completed: '已完成',
  cancelled: '已取消',
}

// 跟 stage4 的差異：stage4 這頁的說明文字寫死「訂單一律是 pending 狀態」，
// 因為那時候真的只有一種狀態。本階段訂單有完整的狀態機，這頁改成如實顯示
// 「目前狀態」，而不是重複寫死一段跟事實不符的說明文字。
export default function OrderComplete() {
  const { orderId } = useParams()
  const [order, setOrder] = useState(null)
  const [status, setStatus] = useState('loading')

  useEffect(() => {
    let cancelled = false
    apiFetch(`/orders/${orderId}`)
      .then((data) => {
        if (!cancelled) {
          setOrder(data)
          setStatus('ready')
        }
      })
      .catch((err) => {
        if (cancelled) return
        setStatus(err instanceof ApiError && err.status === 404 ? 'not-found' : 'error')
      })
    return () => {
      cancelled = true
    }
  }, [orderId])

  if (status === 'loading') {
    return (
      <div className="container section">
        <p className="empty-state">訂單讀取中...</p>
      </div>
    )
  }

  if (status !== 'ready') {
    return (
      <div className="container section">
        <p className="empty-state">
          找不到這筆訂單（可能不是你帳號底下的訂單，或訂單編號不存在）。
          <Link to="/orders">查看我的訂單</Link>
        </p>
      </div>
    )
  }

  return (
    <div className="container section order-complete">
      <h1 className="section__title">訂單詳情</h1>
      <p className="mock-notice">
        這筆訂單已經寫進資料庫，目前狀態是「{STATUS_LABEL[order.status] ?? order.status}」。本站的付款只是
        模擬金流，沒有真實付款，也不會有商品實際出貨。
      </p>

      <div className="order-complete__card">
        <p>
          訂單編號：<strong data-testid="order-id">{order.id}</strong>
        </p>
        <p>
          目前狀態：<strong>{STATUS_LABEL[order.status] ?? order.status}</strong>
        </p>
        <p>收件人：{order.recipient_name}</p>
        <p>收件地址：{order.recipient_address}</p>

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
      </div>

      <div className="cart-actions">
        {(order.status === 'pending' || order.status === 'failed') && (
          <Link to={`/pay/${order.id}`} className="btn btn--primary">
            前往付款
          </Link>
        )}
        <Link to="/orders" className="btn btn--secondary">
          查看我的訂單
        </Link>
        <Link to="/products" className="btn btn--primary">
          繼續選購
        </Link>
      </div>
    </div>
  )
}
