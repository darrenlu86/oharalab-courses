import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api/client'
import { formatCurrency } from '../utils/formatCurrency'

// 跟 stage3 的差異：訂單列表來自 GET /api/orders（後端只回傳「目前登入使用者」
// 自己的訂單，見 backend/app/db/database.py 的 list_orders_by_user()），不是
// 讀本機 localStorage 裡的全部訂單——這一頁本身就需要登入，App.jsx 沒有另外做
// 路由層級的保護（例如未登入自動導去 /login），是因為 apiFetch 遇到 401 時
// client.js 的 unauthorizedHandler 本來就會自動導去登入頁，效果一樣，
// 不需要在每個「需要登入」的頁面重複寫一次判斷邏輯。
export default function Orders() {
  const [orders, setOrders] = useState([])
  const [status, setStatus] = useState('loading')

  useEffect(() => {
    let cancelled = false
    apiFetch('/orders')
      .then((data) => {
        if (!cancelled) {
          setOrders(data.items)
          setStatus('ready')
        }
      })
      .catch(() => {
        if (!cancelled) setStatus('error')
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (status === 'loading') {
    return (
      <div className="container section">
        <h1 className="section__title">我的訂單</h1>
        <p className="empty-state">訂單讀取中...</p>
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div className="container section">
        <h1 className="section__title">我的訂單</h1>
        <p className="empty-state">訂單讀取失敗，請確認已經登入、且後端伺服器正常運作。</p>
      </div>
    )
  }

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
      <p className="mock-notice">訂單資料存在後端資料庫裡，換裝置只要用同一個帳號登入就查得到。</p>

      <ul className="order-list">
        {orders.map((order) => (
          <li key={order.id} className="order-list__item">
            <div>
              <Link to={`/order-complete/${order.id}`} className="order-list__id">
                訂單 #{order.id}
              </Link>
              <span className="order-list__date">{order.created_at}</span>
            </div>
            <span className="order-list__count">{order.status}</span>
            <span className="order-list__total">{formatCurrency(order.total_amount)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
