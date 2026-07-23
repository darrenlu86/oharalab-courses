import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiFetch, ApiError } from '../api/client'
import { formatCurrency } from '../utils/formatCurrency'

// 跟 stage3 的差異：訂單用 GET /api/orders/:id 向後端查，不再是從 localStorage
// 讀出剛剛存的物件——這代表現在換一台裝置、清過瀏覽器資料，只要你還記得訂單
// 網址、而且用同一個帳號登入，一樣查得到這筆訂單，這正是 stage3 README
// 「與上一階段的差異」點出的限制在這裡被解決掉的地方。
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
      <h1 className="section__title">訂購完成</h1>
      <p className="mock-notice">
        這筆訂單已經寫進資料庫、庫存也已經扣減，但沒有真實付款、也不會有商品實際出貨——
        本階段還沒有金流與付款狀態的概念，訂單一律是「pending」狀態。
      </p>

      <div className="order-complete__card">
        <p>
          訂單編號：<strong data-testid="order-id">{order.id}</strong>
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
