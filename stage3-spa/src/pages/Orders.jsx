import { Link } from 'react-router-dom'
import { getOrders } from '../utils/ordersStorage'
import { formatCurrency } from '../utils/formatCurrency'

export default function Orders() {
  const orders = getOrders()

  if (orders.length === 0) {
    return (
      <div className="container section">
        <h1 className="section__title">我的訂單</h1>
        <p className="empty-state">
          目前沒有任何訂單紀錄。<Link to="/products">去逛逛商品</Link>
        </p>
      </div>
    )
  }

  return (
    <div className="container section">
      <h1 className="section__title">我的訂單</h1>
      <p className="mock-notice">
        訂單資料只存在你目前這台裝置的瀏覽器裡（localStorage），換一台電腦或清除瀏覽器資料就查不到了。
      </p>

      <ul className="order-list">
        {orders.map((order) => (
          <li key={order.id} className="order-list__item">
            <div>
              <Link to={`/order-complete/${order.id}`} className="order-list__id">
                {order.id}
              </Link>
              <span className="order-list__date">{new Date(order.createdAt).toLocaleString('zh-TW')}</span>
            </div>
            <span className="order-list__count">{order.items.length} 項商品</span>
            <span className="order-list__total">{formatCurrency(order.subtotal)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
