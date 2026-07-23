import { createContext, useContext, useEffect, useMemo, useReducer } from 'react'
import { cartReducer, initialCartState, cartSubtotal, cartTotalQuantity } from './cartReducer'

// 為什麼用 Context + useReducer，而不是 Redux/Zustand：
// 這個 App 只有「一份」全站共享狀態（購物車），沒有跨模組的複雜非同步流程、
// 也不需要 middleware、time-travel debugging 或跨頁簽同步這些進階需求。
// Context 負責「跨元件共享」，useReducer 負責「集中管理狀態變化的邏輯」，
// 兩個都是 React 內建 API，組合起來剛好打平這個規模的需求 —— 這是刻意的簡化，
// 詳細取捨寫在 docs/ARCHITECTURE.md「狀態管理決策」一節，不在這裡展開。

const CART_STORAGE_KEY = 'brewgo_cart_v1'

const CartContext = createContext(null)

function loadCartFromStorage() {
  try {
    const raw = window.localStorage.getItem(CART_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch (error) {
    // 讀壞資料（例如使用者手動改過 localStorage）時，不讓整個 App 白屏，
    // 退而求其次視為空購物車，並在 console 留下痕跡方便除錯。
    console.warn('讀取本機購物車資料失敗，改用空購物車', error)
    return []
  }
}

export function CartProvider({ children }) {
  const [state, dispatch] = useReducer(cartReducer, initialCartState, (init) => ({
    ...init,
    items: loadCartFromStorage(),
  }))

  useEffect(() => {
    window.localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(state.items))
  }, [state.items])

  const value = useMemo(
    () => ({
      items: state.items,
      totalQuantity: cartTotalQuantity(state),
      subtotal: cartSubtotal(state),
      addItem: (product, quantity) => dispatch({ type: 'ADD_ITEM', payload: { product, quantity } }),
      updateQuantity: (id, quantity) => dispatch({ type: 'UPDATE_QUANTITY', payload: { id, quantity } }),
      removeItem: (id) => dispatch({ type: 'REMOVE_ITEM', payload: { id } }),
      clearCart: () => dispatch({ type: 'CLEAR_CART' }),
    }),
    [state],
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

export const CART_STORAGE_KEY_FOR_TESTS = CART_STORAGE_KEY
