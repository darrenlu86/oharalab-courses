import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../api/client'
import { useAuth } from './AuthContext'

// stage3 的 CartContext 用 useReducer + localStorage：購物車完全活在使用者自己的
// 瀏覽器裡，換一台裝置就消失，庫存上限也只是「加入當下」的一份快照（見 stage3
// cartReducer.js 開頭註解）。
//
// stage4 把購物車搬到伺服器：這裡不再需要 reducer，因為「狀態怎麼變化」的邏輯
// 已經搬到後端（app/routers/cart.py），前端只負責「呼叫 API、把後端回傳的最新
// 購物車內容整包存下來」——這是本階段「資料層從假的換成真的」最直接的體現：
// 庫存上限不再是快照，而是後端 `CartItemOut.stock` 給的即時值；購物車內容也不再
// 是本機 state，而是「跟後端同步」的結果，任何操作都先打 API、拿到最新回應
// 才更新畫面（教學簡化：不做樂觀更新 optimistic update，每次操作都乖乖等後端
// 回應才變畫面，程式碼比較好懂，代價是操作會有一個網路來回的小延遲）。
const CartContext = createContext(null)

const EMPTY_CART = { items: [], total_amount: 0, total_quantity: 0 }

export function CartProvider({ children }) {
  const { isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const [cart, setCart] = useState(EMPTY_CART)
  const [loading, setLoading] = useState(false)

  const refreshCart = useCallback(async () => {
    if (!isAuthenticated) {
      // 未登入時購物車一律視為空——不是「假裝有資料」，是後端本來就沒有
      // 這個訪客的購物車可以查（/api/cart 需要登入），這裡直接反映這個事實。
      setCart(EMPTY_CART)
      return
    }
    setLoading(true)
    try {
      const data = await apiFetch('/cart')
      setCart(data)
    } finally {
      setLoading(false)
    }
  }, [isAuthenticated])

  useEffect(() => {
    refreshCart()
  }, [refreshCart])

  // 教學簡化（也寫進 README「與上一階段的差異」）：未登入使用者點「加入購物車」
  // 直接導去登入頁，不像很多正式電商會先讓訪客把商品放進一個「訪客購物車」
  // （通常也是存在瀏覽器 localStorage），登入後才「合併」成帳號購物車。
  // 那種合併邏輯本身就有不少邊界情況要處理（例如兩邊都有同一件商品、數量該
  // 累加還是取大者），對初學者是不必要的複雜度，所以本階段直接省略，
  // 未登入就是不能把商品放進（伺服器端的）購物車。
  const addItem = useCallback(
    async (productId, quantity) => {
      if (!isAuthenticated) {
        navigate('/login')
        return
      }
      const data = await apiFetch('/cart/items', {
        method: 'POST',
        body: JSON.stringify({ product_id: productId, quantity }),
      })
      setCart(data)
    },
    [isAuthenticated, navigate],
  )

  const updateQuantity = useCallback(async (productId, quantity) => {
    const data = await apiFetch(`/cart/items/${productId}`, {
      method: 'PATCH',
      body: JSON.stringify({ quantity }),
    })
    setCart(data)
  }, [])

  const removeItem = useCallback(async (productId) => {
    const data = await apiFetch(`/cart/items/${productId}`, { method: 'DELETE' })
    setCart(data)
  }, [])

  const value = useMemo(
    () => ({
      items: cart.items,
      totalQuantity: cart.total_quantity,
      subtotal: cart.total_amount,
      loading,
      addItem,
      updateQuantity,
      removeItem,
      refreshCart,
    }),
    [cart, loading, addItem, updateQuantity, removeItem, refreshCart],
  )

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>
}

export function useCart() {
  const context = useContext(CartContext)
  if (!context) {
    throw new Error('useCart 必須在 <CartProvider> 內使用')
  }
  return context
}
