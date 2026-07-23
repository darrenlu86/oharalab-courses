import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch, ApiError } from '../api/client'
import { formatCurrency } from '../utils/formatCurrency'
import { useAuth } from '../context/AuthContext'
import { useOrdersSocket } from '../hooks/useOrdersSocket'

// 跟 stage4 的差異：stage4 的訂單只有一種狀態（'pending'），這頁不需要顯示狀態、
// 也沒有任何動作可以做。stage5 訂單有完整的狀態機（見
// backend/app/order_state.py），這頁多了三件事：
// 1. 用中文標籤＋色塊呈現目前狀態（`STATUS_LABEL` / `statusBadgeClass`）。
// 2. pending 狀態多一個「去付款」連結（導去 pages/Pay.jsx）；failed 狀態也是——
//    付款失敗不代表訂單消失，使用者應該還能重新嘗試付款。
// 3. pending 狀態多一個「取消訂單」按鈕，呼叫 `POST /api/orders/:id/cancel`
//    （後端只允許 pending 狀態的訂單被顧客自己取消，見 order_state.py 的
//    `can_customer_cancel`），成功後就地更新這筆訂單的狀態，不用整頁重新整理。
//
// 跟 stage5 的差異（stage6 新增）：這頁現在還開著一條 `/ws/my/orders` 的
// WebSocket 連線（見 hooks/useOrdersSocket.js），店家後台把某一筆訂單狀態
// 改掉的當下，這頁會就地更新那一筆訂單的狀態並閃一下背景色提示「剛剛更新過」，
// 完全不需要使用者自己按重新整理。連線狀態（連上/重連中/認證失敗）用一個
// 小徽章顯示在標題旁邊，這是刻意讓使用者知道「即時更新現在有沒有在運作」，
// 而不是靜悄悄地失敗——使用者才不會誤以為「訂單狀態一直沒變」其實只是連線斷了。
const STATUS_LABEL = {
  pending: '待付款',
  paid: '已付款',
  failed: '付款失敗',
  shipped: '已出貨',
  completed: '已完成',
  cancelled: '已取消',
}

function statusBadgeClass(status) {
  if (status === 'completed' || status === 'paid' || status === 'shipped') return 'stock-badge stock-badge--in'
  if (status === 'failed' || status === 'cancelled') return 'stock-badge stock-badge--out'
  return 'stock-badge stock-badge--low' // pending
}

const CONNECTION_LABEL = {
  idle: null,
  connecting: '正在連線即時更新...',
  connected: '即時更新已連線',
  reconnecting: '連線中斷，重新連線中...',
  'auth-failed': '即時更新連線失敗（請重新登入）',
}

export default function Orders() {
  const { token } = useAuth()
  const [orders, setOrders] = useState([])
  const [status, setStatus] = useState('loading')
  const [actionError, setActionError] = useState('')
  const [cancellingId, setCancellingId] = useState(null)
  const [recentlyUpdatedId, setRecentlyUpdatedId] = useState(null)

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

  // stage6 新增：收到後端推播的訂單事件，就地更新那一筆訂單的狀態，並且短暫
  // 標記成「剛更新過」讓 CSS 動畫（order-update-flash）閃一下背景色，提示使用者
  // 「這筆剛剛真的變了，不是你看錯」。
  const { connectionState } = useOrdersSocket(token, (message) => {
    const updated = message.order
    if (!updated) return
    setOrders((prev) => {
      const exists = prev.some((order) => order.id === updated.id)
      if (!exists) return prev // 這頁只顯示已經載入過的訂單，不主動插入新訂單
      return prev.map((order) => (order.id === updated.id ? { ...order, status: updated.status } : order))
    })
    setRecentlyUpdatedId(updated.id)
    window.setTimeout(() => setRecentlyUpdatedId((current) => (current === updated.id ? null : current)), 1600)
  })

  const handleCancel = async (orderId) => {
    setActionError('')
    setCancellingId(orderId)
    try {
      const updated = await apiFetch(`/orders/${orderId}/cancel`, { method: 'POST' })
      setOrders((prev) => prev.map((order) => (order.id === orderId ? { ...order, status: updated.status } : order)))
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : '取消訂單失敗，請稍後再試')
    } finally {
      setCancellingId(null)
    }
  }

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
      {CONNECTION_LABEL[connectionState] && (
        <span
          className={`realtime-badge realtime-badge--${connectionState}`}
          data-testid="orders-realtime-badge"
        >
          <span className="realtime-badge__dot" />
          {CONNECTION_LABEL[connectionState]}
        </span>
      )}
      {actionError && (
        <p className="form-error" role="alert" data-testid="orders-action-error">
          {actionError}
        </p>
      )}

      <ul className="order-list">
        {orders.map((order) => (
          <li
            key={order.id}
            className={`order-list__item order-list__item--stage5${
              recentlyUpdatedId === order.id ? ' order-update-flash' : ''
            }`}
          >
            <div>
              <Link to={`/order-complete/${order.id}`} className="order-list__id">
                訂單 #{order.id}
              </Link>
              <span className="order-list__date">{order.created_at}</span>
            </div>
            <span className={statusBadgeClass(order.status)}>{STATUS_LABEL[order.status] ?? order.status}</span>
            <span className="order-list__total">{formatCurrency(order.total_amount)}</span>
            <span className="order-list__actions">
              {(order.status === 'pending' || order.status === 'failed') && (
                <Link to={`/pay/${order.id}`} className="btn btn--secondary btn--small">
                  去付款
                </Link>
              )}
              {order.status === 'pending' && (
                <button
                  type="button"
                  className="btn btn--text btn--danger btn--small"
                  disabled={cancellingId === order.id}
                  onClick={() => handleCancel(order.id)}
                >
                  {cancellingId === order.id ? '取消中...' : '取消訂單'}
                </button>
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
