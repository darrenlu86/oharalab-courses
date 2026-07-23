import { describe, expect, it } from 'vitest'
import { cartReducer, initialCartState, cartSubtotal, cartTotalQuantity } from './cartReducer'

const product = { id: 1, name: '耶加雪菲 淺焙單品豆 250g', price: 520, image: '/images/p1.svg', stock: 25 }
const lowStockProduct = { id: 6, name: '深焙醇厚掛耳包 10 入', price: 300, image: '/images/p6.svg', stock: 3 }

describe('cartReducer', () => {
  it('ADD_ITEM：加入新商品時建立一筆項目', () => {
    const state = cartReducer(initialCartState, {
      type: 'ADD_ITEM',
      payload: { product, quantity: 2 },
    })
    expect(state.items).toHaveLength(1)
    expect(state.items[0]).toMatchObject({ id: 1, quantity: 2, price: 520 })
  })

  it('ADD_ITEM：同一商品再次加入會累加數量，而不是新增第二筆', () => {
    let state = cartReducer(initialCartState, { type: 'ADD_ITEM', payload: { product, quantity: 2 } })
    state = cartReducer(state, { type: 'ADD_ITEM', payload: { product, quantity: 3 } })
    expect(state.items).toHaveLength(1)
    expect(state.items[0].quantity).toBe(5)
  })

  it('ADD_ITEM：累加後的數量不能超過商品庫存上限', () => {
    let state = cartReducer(initialCartState, {
      type: 'ADD_ITEM',
      payload: { product: lowStockProduct, quantity: 2 },
    })
    state = cartReducer(state, { type: 'ADD_ITEM', payload: { product: lowStockProduct, quantity: 5 } })
    expect(state.items[0].quantity).toBe(3) // 庫存只有 3，不會變成 7
  })

  it('ADD_ITEM：庫存為 0 的商品不會被加入購物車', () => {
    const outOfStock = { ...product, id: 11, stock: 0 }
    const state = cartReducer(initialCartState, {
      type: 'ADD_ITEM',
      payload: { product: outOfStock, quantity: 1 },
    })
    expect(state.items).toHaveLength(0)
  })

  it('UPDATE_QUANTITY：可以改成合法範圍內的數量', () => {
    let state = cartReducer(initialCartState, { type: 'ADD_ITEM', payload: { product, quantity: 2 } })
    state = cartReducer(state, { type: 'UPDATE_QUANTITY', payload: { id: 1, quantity: 10 } })
    expect(state.items[0].quantity).toBe(10)
  })

  it('UPDATE_QUANTITY：超過庫存時會被夾住在庫存上限', () => {
    let state = cartReducer(initialCartState, {
      type: 'ADD_ITEM',
      payload: { product: lowStockProduct, quantity: 1 },
    })
    state = cartReducer(state, { type: 'UPDATE_QUANTITY', payload: { id: 6, quantity: 99 } })
    expect(state.items[0].quantity).toBe(3)
  })

  it('UPDATE_QUANTITY：低於 1 時會被夾住在最小值 1', () => {
    let state = cartReducer(initialCartState, { type: 'ADD_ITEM', payload: { product, quantity: 2 } })
    state = cartReducer(state, { type: 'UPDATE_QUANTITY', payload: { id: 1, quantity: 0 } })
    expect(state.items[0].quantity).toBe(1)
  })

  it('REMOVE_ITEM：移除指定商品', () => {
    let state = cartReducer(initialCartState, { type: 'ADD_ITEM', payload: { product, quantity: 1 } })
    state = cartReducer(state, { type: 'REMOVE_ITEM', payload: { id: 1 } })
    expect(state.items).toHaveLength(0)
  })

  it('CLEAR_CART：清空整個購物車', () => {
    let state = cartReducer(initialCartState, { type: 'ADD_ITEM', payload: { product, quantity: 1 } })
    state = cartReducer(state, {
      type: 'ADD_ITEM',
      payload: { product: lowStockProduct, quantity: 1 },
    })
    state = cartReducer(state, { type: 'CLEAR_CART' })
    expect(state.items).toHaveLength(0)
  })

  it('cartTotalQuantity / cartSubtotal：正確加總數量與金額', () => {
    let state = cartReducer(initialCartState, { type: 'ADD_ITEM', payload: { product, quantity: 2 } })
    state = cartReducer(state, {
      type: 'ADD_ITEM',
      payload: { product: lowStockProduct, quantity: 3 },
    })
    expect(cartTotalQuantity(state)).toBe(5)
    expect(cartSubtotal(state)).toBe(520 * 2 + 300 * 3)
  })
})
