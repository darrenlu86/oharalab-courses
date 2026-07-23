// 訂單儲存：跟購物車一樣存在 localStorage，key 分開避免互相污染。
// 誠實聲明（也寫進 README）：這裡沒有後端、沒有資料庫，換一台裝置或清瀏覽器資料，
// 訂單紀錄就會消失 —— 這個限制正是 stage4 要解決的問題（見 README「與上一階段的差異」）。
const ORDERS_STORAGE_KEY = 'brewgo_orders_v1'

export function getOrders() {
  try {
    const raw = window.localStorage.getItem(ORDERS_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch (error) {
    console.warn('讀取本機訂單資料失敗，視為沒有訂單', error)
    return []
  }
}

export function saveOrder(order) {
  const orders = getOrders()
  const next = [order, ...orders]
  window.localStorage.setItem(ORDERS_STORAGE_KEY, JSON.stringify(next))
  return next
}

export function getOrderById(orderId) {
  return getOrders().find((order) => order.id === orderId) ?? null
}

export const ORDERS_STORAGE_KEY_FOR_TESTS = ORDERS_STORAGE_KEY
