import { useEffect, useState } from 'react'
import { apiFetch } from '../api/client'
import { formatCurrency } from '../utils/formatCurrency'
import { useAdminAuth } from '../context/AdminAuthContext'
import { useAdminOrdersSocket } from '../hooks/useAdminOrdersSocket'

const STATUS_LABEL = {
  pending: '待付款',
  paid: '已付款',
  failed: '付款失敗',
  shipped: '已出貨',
  completed: '已完成',
  cancelled: '已取消',
}

const CONNECTION_LABEL = {
  idle: null,
  connecting: '正在連線即時看板...',
  connected: '即時看板已連線',
  reconnecting: '連線中斷，重新連線中...',
  'auth-failed': '即時看板連線失敗（請重新登入）',
}

// Dashboard——刻意只用「數字卡」＋「純 HTML 表格」呈現，不引任何圖表庫（master
// spec 的依賴白名單本來就沒有圖表庫；教學重點也不是「怎麼畫圖表」，是「怎麼用
// SQL 做聚合、後端算好再給前端」，見 backend/app/db/database.py 的 admin_summary()）。
// 所有數字都是真的從 `GET /api/admin/summary` 拿到的，這裡的元件完全不做任何
// 加總計算——前端只負責排版，聚合邏輯全部在後端（教學點：能在資料庫層做的聚合
// 就不要搬到前端重算一次）。
//
// 跟 stage5 的差異（stage6 新增）：這頁開著 `/ws/admin/orders` 連線（見
// hooks/useAdminOrdersSocket.js）。新訂單建立時，最上面會跳出一條「有新訂單」
// 提示條（不自動加進表格——summary 的統計數字如果沒有一起更新，表格單方面
// 多一筆會跟數字卡對不起來，這裡刻意只提示、不假裝完整同步，教學上比較誠實）；
// 既有訂單的狀態被改變時（例如另一個管理員標記出貨），表格裡對應那一列會
// 就地更新狀態並閃一下背景色。
export default function Dashboard() {
  const { token } = useAdminAuth()
  const [summary, setSummary] = useState(null)
  const [recentOrders, setRecentOrders] = useState([])
  const [status, setStatus] = useState('loading')
  const [newOrderCount, setNewOrderCount] = useState(0)
  const [flashRowId, setFlashRowId] = useState(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([apiFetch('/admin/summary'), apiFetch('/admin/orders')])
      .then(([summaryData, ordersData]) => {
        if (cancelled) return
        setSummary(summaryData)
        setRecentOrders(ordersData.items.slice(0, 5))
        setStatus('ready')
      })
      .catch(() => {
        if (!cancelled) setStatus('error')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const { connectionState } = useAdminOrdersSocket(token, (message) => {
    if (message.type === 'order_created') {
      setNewOrderCount((count) => count + 1)
      return
    }
    // order_paid / order_status_changed / order_payment_failed：如果這筆訂單
    // 剛好在目前顯示的「最近訂單」清單裡，就地更新狀態並閃一下背景色。
    const updated = message.order
    if (!updated) return
    setRecentOrders((prev) => {
      const exists = prev.some((order) => order.id === updated.id)
      if (!exists) return prev
      return prev.map((order) => (order.id === updated.id ? { ...order, status: updated.status } : order))
    })
    setFlashRowId(updated.id)
    window.setTimeout(() => setFlashRowId((current) => (current === updated.id ? null : current)), 1600)
  })

  const refreshAfterNewOrders = () => {
    setNewOrderCount(0)
    // 刻意不動 `status`——這是「補一次資料」而不是「整頁重新進入 loading」，
    // 避免畫面因為切成 loading 狀態而整個閃爍消失又出現。
    Promise.all([apiFetch('/admin/summary'), apiFetch('/admin/orders')]).then(([summaryData, ordersData]) => {
      setSummary(summaryData)
      setRecentOrders(ordersData.items.slice(0, 5))
    })
  }

  if (status === 'loading') {
    return <p className="admin-empty">Dashboard 讀取中...</p>
  }

  if (status === 'error' || !summary) {
    return <p className="admin-empty">Dashboard 讀取失敗，請確認已登入且後端伺服器正常運作。</p>
  }

  return (
    <div>
      <h1 className="admin-page-title">Dashboard</h1>

      {CONNECTION_LABEL[connectionState] && (
        <span
          className={`admin-realtime-badge admin-realtime-badge--${connectionState}`}
          data-testid="admin-realtime-badge"
        >
          <span className="admin-realtime-badge__dot" />
          {CONNECTION_LABEL[connectionState]}
        </span>
      )}

      {newOrderCount > 0 && (
        <div className="admin-new-order-banner" role="status" data-testid="new-order-banner">
          <span>
            有 {newOrderCount} 筆新訂單進來了
          </span>
          <button type="button" className="admin-btn admin-btn--small" onClick={refreshAfterNewOrders}>
            重新整理
          </button>
        </div>
      )}

      <div className="admin-stat-grid">
        <div className="admin-stat-card">
          <span className="admin-stat-card__label">總營收（paid＋shipped＋completed）</span>
          <span className="admin-stat-card__value">{formatCurrency(summary.total_revenue)}</span>
        </div>
        <div className="admin-stat-card">
          <span className="admin-stat-card__label">訂單總數</span>
          <span className="admin-stat-card__value">{summary.total_orders}</span>
        </div>
        <div className="admin-stat-card">
          <span className="admin-stat-card__label">待出貨（已付款未出貨）</span>
          <span className="admin-stat-card__value">{summary.pending_shipment_orders}</span>
        </div>
        <div className="admin-stat-card">
          <span className="admin-stat-card__label">會員數</span>
          <span className="admin-stat-card__value">{summary.member_count}</span>
        </div>
      </div>

      <section className="admin-section">
        <h2 className="admin-section-title">低庫存商品（少於 5 件）</h2>
        {summary.low_stock_products.length === 0 ? (
          <p className="admin-empty">目前沒有低庫存商品。</p>
        ) : (
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>商品編號</th>
                  <th>名稱</th>
                  <th>分類</th>
                  <th>庫存</th>
                </tr>
              </thead>
              <tbody>
                {summary.low_stock_products.map((product) => (
                  <tr key={product.id}>
                    <td>{product.id}</td>
                    <td>{product.name}</td>
                    <td>{product.category}</td>
                    <td>{product.stock}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="admin-section">
        <h2 className="admin-section-title">最近訂單</h2>
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>訂單編號</th>
                <th>會員 id</th>
                <th>狀態</th>
                <th>金額</th>
                <th>建立時間</th>
              </tr>
            </thead>
            <tbody>
              {recentOrders.map((order) => (
                <tr key={order.id} className={flashRowId === order.id ? 'admin-row-flash' : undefined}>
                  <td>{order.id}</td>
                  <td>{order.user_id}</td>
                  <td>{STATUS_LABEL[order.status] ?? order.status}</td>
                  <td>{formatCurrency(order.total_amount)}</td>
                  <td>{order.created_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
