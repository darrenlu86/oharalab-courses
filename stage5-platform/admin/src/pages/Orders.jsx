import { useEffect, useState } from 'react'
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

const STATUS_OPTIONS = ['', 'pending', 'paid', 'failed', 'shipped', 'completed', 'cancelled']

// 每個狀態底下，後台可以手動按下去的「下一步」——這份清單必須跟後端
// backend/app/order_state.py 的 `ADMIN_STATUS_TRANSITIONS` 保持一致；前端這裡
// 只是「不要顯示按了也一定會被後端拒絕的按鈕」，真正擋住非法轉移的還是後端
// （按鈕按下去一樣會呼叫 API，後端狀態機仍然會驗證一次）。
const NEXT_ACTIONS = {
  pending: [{ status: 'cancelled', label: '取消訂單' }],
  failed: [{ status: 'cancelled', label: '取消訂單' }],
  paid: [
    { status: 'shipped', label: '標記已出貨' },
    { status: 'cancelled', label: '取消訂單' },
  ],
  shipped: [{ status: 'completed', label: '標記已完成' }],
  completed: [],
  cancelled: [],
}

export default function Orders() {
  const [orders, setOrders] = useState([])
  const [statusFilter, setStatusFilter] = useState('')
  const [loadStatus, setLoadStatus] = useState('loading')
  const [actionError, setActionError] = useState('')
  const [updatingId, setUpdatingId] = useState(null)

  const loadOrders = () => {
    setLoadStatus('loading')
    const query = statusFilter ? `?order_status=${statusFilter}` : ''
    apiFetch(`/admin/orders${query}`)
      .then((data) => {
        setOrders(data.items)
        setLoadStatus('ready')
      })
      .catch(() => setLoadStatus('error'))
  }

  useEffect(loadOrders, [statusFilter])

  const updateStatus = async (orderId, nextStatus) => {
    setActionError('')
    setUpdatingId(orderId)
    try {
      const updated = await apiFetch(`/admin/orders/${orderId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status: nextStatus }),
      })
      setOrders((prev) => prev.map((order) => (order.id === orderId ? updated : order)))
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : '更新訂單狀態失敗')
    } finally {
      setUpdatingId(null)
    }
  }

  return (
    <div>
      <div className="admin-page-header">
        <h1 className="admin-page-title">訂單管理</h1>
        <div className="admin-form-field admin-form-field--inline">
          <label htmlFor="status-filter">狀態篩選</label>
          <select id="status-filter" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            {STATUS_OPTIONS.map((option) => (
              <option key={option || 'all'} value={option}>
                {option ? STATUS_LABEL[option] : '全部'}
              </option>
            ))}
          </select>
        </div>
      </div>

      {actionError && (
        <p className="admin-form-error" role="alert" data-testid="orders-action-error">
          {actionError}
        </p>
      )}

      {loadStatus === 'loading' && <p className="admin-empty">訂單讀取中...</p>}
      {loadStatus === 'error' && <p className="admin-empty">訂單讀取失敗，請確認已登入且後端伺服器正常運作。</p>}

      {loadStatus === 'ready' && (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>訂單編號</th>
                <th>會員 id</th>
                <th>狀態</th>
                <th>金額</th>
                <th>收件人</th>
                <th>建立時間</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.id}>
                  <td>{order.id}</td>
                  <td>{order.user_id}</td>
                  <td>{STATUS_LABEL[order.status] ?? order.status}</td>
                  <td>{formatCurrency(order.total_amount)}</td>
                  <td>{order.recipient_name}</td>
                  <td>{order.created_at}</td>
                  <td className="admin-table__actions">
                    {(NEXT_ACTIONS[order.status] ?? []).map((action) => (
                      <button
                        key={action.status}
                        type="button"
                        className="admin-btn admin-btn--small"
                        disabled={updatingId === order.id}
                        onClick={() => updateStatus(order.id, action.status)}
                      >
                        {action.label}
                      </button>
                    ))}
                    {(NEXT_ACTIONS[order.status] ?? []).length === 0 && <span className="admin-muted">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {orders.length === 0 && <p className="admin-empty">沒有符合條件的訂單。</p>}
        </div>
      )}
    </div>
  )
}
