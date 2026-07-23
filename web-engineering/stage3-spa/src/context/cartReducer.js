// 購物車狀態機：純函式 reducer，不 import React、不碰 localStorage。
// 為什麼特地拆成獨立檔案：這樣寫單元測試時完全不需要掛載元件、不需要 jsdom，
// 純粹丟 (state, action) 進去、檢查回傳的新 state，跑起來快、也最能測到邏輯本身的正確性。
// CartContext.jsx 負責「把這支 reducer 接上 React 的 useReducer + localStorage 持久化」。

export const initialCartState = {
  items: [],
}

// 每個 item 的形狀：{ id, name, price, image, quantity, stock }
// stock 是「加入購物車當下」商品的庫存快照 —— 本階段商品資料是本地固定 JSON，
// 不會有人在背景把庫存改掉，所以拿加入當下的庫存當作這個購物車項目的數量上限是安全的；
// 如果之後接了會即時變動庫存的後端（stage4 起），數量上限就要改成即時查詢，不能再用快照。
export function cartReducer(state, action) {
  switch (action.type) {
    case 'ADD_ITEM': {
      const { product, quantity } = action.payload
      if (!product || product.stock <= 0 || quantity <= 0) {
        return state
      }
      const existing = state.items.find((item) => item.id === product.id)
      if (existing) {
        const nextQuantity = Math.min(existing.quantity + quantity, product.stock)
        return {
          ...state,
          items: state.items.map((item) =>
            item.id === product.id ? { ...item, quantity: nextQuantity } : item,
          ),
        }
      }
      const nextQuantity = Math.min(quantity, product.stock)
      return {
        ...state,
        items: [
          ...state.items,
          {
            id: product.id,
            name: product.name,
            price: product.price,
            image: product.image,
            stock: product.stock,
            quantity: nextQuantity,
          },
        ],
      }
    }

    case 'UPDATE_QUANTITY': {
      const { id, quantity } = action.payload
      return {
        ...state,
        items: state.items.map((item) => {
          if (item.id !== id) return item
          const clamped = Math.max(1, Math.min(quantity, item.stock))
          return { ...item, quantity: clamped }
        }),
      }
    }

    case 'REMOVE_ITEM': {
      const { id } = action.payload
      return {
        ...state,
        items: state.items.filter((item) => item.id !== id),
      }
    }

    case 'CLEAR_CART':
      return { ...state, items: [] }

    case 'LOAD_CART': {
      const items = Array.isArray(action.payload) ? action.payload : []
      return { ...state, items }
    }

    default:
      return state
  }
}

export function cartTotalQuantity(state) {
  return state.items.reduce((sum, item) => sum + item.quantity, 0)
}

export function cartSubtotal(state) {
  return state.items.reduce((sum, item) => sum + item.price * item.quantity, 0)
}
