import { Link, useParams } from 'react-router-dom'
import { getOrderById } from '../utils/ordersStorage'
import { formatCurrency } from '../utils/formatCurrency'

export default function OrderComplete() {
  const { orderId } = useParams()
  const order = getOrderById(orderId)

  if (!order) {
    return (
      <div className="container section">
        <p className="empty-state">
          找不到這筆訂單（可能是清過瀏覽器資料，或換了裝置）。<Link to="/orders">查看我的訂單</Link>
        </p>
      </div>
    )
  }

  return (
    <div className="container section order-complete">
      <h1 className="section__title">訂購完成</h1>
      <p className="mock-notice">
        這是模擬訂單，沒有真實付款、也不會有商品實際出貨 —— 純前端 demo 只走到「訂單存進你的瀏覽器」這一步。
      </p>

      <div className="order-complete__card">
        <p>
          訂單編號：<strong data-testid="order-id">{order.id}</strong>
        </p>
        <p>收件人：{order.recipient.name}</p>
        <p>聯絡手機：{order.recipient.phone}</p>
        <p>收件地址：{order.recipient.address}</p>
        {order.recipient.note && <p>備註：{order.recipient.note}</p>}

        <ul className="checkout-summary__list">
          {order.items.map((item) => (
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
          <span>{formatCurrency(order.subtotal)}</span>
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
