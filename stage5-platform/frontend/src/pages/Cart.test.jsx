import { describe, expect, it } from 'vitest'
import { screen, fireEvent, within, waitFor } from '@testing-library/react'
import Cart from './Cart'
import { renderWithProviders } from '../test/renderWithProviders'
import { stubApi } from '../test/mockApi'

// 跟 stage3 的 Cart.test.jsx 差異：stage3 用 `seedCart()` 直接把資料寫進
// localStorage，因為 CartContext 的資料來源就是 localStorage。stage4 的購物車
// 資料來自後端，測試改成用 `stubApi()` 假造 /api/cart（以及需要登入頁面共同會
// 打的 /api/auth/me）的回應，模擬「後端已經有這些購物車內容」。
const testUser = { id: 1, email: 'tester@example.com', name: '測試客人' }

const seededItem = {
  product_id: 1,
  name: '耶加雪菲 淺焙單品豆 250g',
  price: 520,
  image_url: '/images/p1.svg',
  quantity: 2,
  stock: 25,
  is_active: true,
  subtotal: 1040,
}

function emptyCart() {
  return { items: [], total_amount: 0, total_quantity: 0 }
}

function cartWith(items) {
  const total_amount = items.reduce((sum, item) => sum + item.subtotal, 0)
  const total_quantity = items.reduce((sum, item) => sum + item.quantity, 0)
  return { items, total_amount, total_quantity }
}

describe('Cart 頁', () => {
  it('未登入時顯示空車狀態（不會呼叫 /api/cart，因為那支 API 需要登入）', async () => {
    stubApi()
    renderWithProviders(<Cart />)
    expect(await screen.findByTestId('cart-empty')).toBeInTheDocument()
  })

  it('登入且購物車有商品時，顯示品項、小計與總計', async () => {
    stubApi({
      'GET /auth/me': () => ({ status: 200, body: testUser }),
      'GET /cart': () => ({ status: 200, body: cartWith([seededItem]) }),
    })
    renderWithProviders(<Cart />, { token: 'fake-token' })

    expect(await screen.findByText('耶加雪菲 淺焙單品豆 250g')).toBeInTheDocument()
    expect(screen.getByTestId('quantity-value')).toHaveTextContent('2')
    expect(within(screen.getByTestId('cart-item')).getByText('NT$1,040')).toBeInTheDocument()
    expect(screen.getByTestId('cart-total')).toHaveTextContent('NT$1,040')
  })

  it('按下數量加號會呼叫 PATCH 並更新畫面上的數量與總計', async () => {
    stubApi({
      'GET /auth/me': () => ({ status: 200, body: testUser }),
      'GET /cart': () => ({ status: 200, body: cartWith([seededItem]) }),
      'PATCH /cart/items/1': () => ({
        status: 200,
        body: cartWith([{ ...seededItem, quantity: 3, subtotal: 1560 }]),
      }),
    })
    renderWithProviders(<Cart />, { token: 'fake-token' })

    await screen.findByTestId('cart-item')
    fireEvent.click(screen.getByLabelText('增加數量'))

    await waitFor(() => expect(screen.getByTestId('quantity-value')).toHaveTextContent('3'))
    expect(screen.getByTestId('cart-total')).toHaveTextContent('NT$1,560')
  })

  it('按下移除會呼叫 DELETE，購物車變回空車狀態', async () => {
    stubApi({
      'GET /auth/me': () => ({ status: 200, body: testUser }),
      'GET /cart': () => ({ status: 200, body: cartWith([seededItem]) }),
      'DELETE /cart/items/1': () => ({ status: 200, body: emptyCart() }),
    })
    renderWithProviders(<Cart />, { token: 'fake-token' })

    await screen.findByTestId('cart-item')
    fireEvent.click(screen.getByRole('button', { name: '移除' }))

    expect(await screen.findByTestId('cart-empty')).toBeInTheDocument()
  })

  it('品項已下架（is_active=false）時顯示「已下架」徽章、停用數量調整、並停用結帳按鈕', async () => {
    const delistedItem = { ...seededItem, is_active: false }
    stubApi({
      'GET /auth/me': () => ({ status: 200, body: testUser }),
      'GET /cart': () => ({ status: 200, body: cartWith([delistedItem]) }),
    })
    renderWithProviders(<Cart />, { token: 'fake-token' })

    await screen.findByTestId('cart-item')
    expect(screen.getByTestId('delisted-badge')).toHaveTextContent('已下架')
    expect(screen.getByLabelText('增加數量')).toBeDisabled()
    expect(screen.getByLabelText('減少數量')).toBeDisabled()

    // 「前往結帳」在含下架品項時要停用（不是 <Link> 可以照樣點過去），並且
    // 附上原因文字——這是前端的體驗優化，真正擋住建單的仍然是後端 409
    // （見 backend/app/routers/orders.py），這裡只驗證前端這一層有沒有做到。
    const checkoutButton = screen.getByTestId('checkout-button')
    expect(checkoutButton.tagName).toBe('BUTTON')
    expect(checkoutButton).toBeDisabled()
    expect(screen.getByTestId('checkout-blocked-reason')).toHaveTextContent('已下架')
  })

  it('品項都還在架上時，「前往結帳」是可以點擊的連結', async () => {
    stubApi({
      'GET /auth/me': () => ({ status: 200, body: testUser }),
      'GET /cart': () => ({ status: 200, body: cartWith([seededItem]) }),
    })
    renderWithProviders(<Cart />, { token: 'fake-token' })

    await screen.findByTestId('cart-item')
    const checkoutButton = screen.getByTestId('checkout-button')
    expect(checkoutButton.tagName).toBe('A')
    expect(screen.queryByTestId('delisted-badge')).not.toBeInTheDocument()
  })

  it('更新數量遇到 409 庫存不足時，顯示後端回傳的錯誤訊息', async () => {
    stubApi({
      'GET /auth/me': () => ({ status: 200, body: testUser }),
      'GET /cart': () => ({ status: 200, body: cartWith([seededItem]) }),
      'PATCH /cart/items/1': () => ({ status: 409, body: { detail: '庫存不足，目前只剩 2 件' } }),
    })
    renderWithProviders(<Cart />, { token: 'fake-token' })

    await screen.findByTestId('cart-item')
    fireEvent.click(screen.getByLabelText('增加數量'))

    expect(await screen.findByTestId('cart-error')).toHaveTextContent('庫存不足，目前只剩 2 件')
  })
})
