import { describe, expect, it, vi } from 'vitest'
import { screen, fireEvent, within } from '@testing-library/react'
import Cart from './Cart'
import { renderWithProviders } from '../test/renderWithProviders'
import { CART_STORAGE_KEY_FOR_TESTS } from '../context/CartContext'

const seededItem = {
  id: 1,
  name: '耶加雪菲 淺焙單品豆 250g',
  price: 520,
  image: '/images/p1.svg',
  stock: 25,
  quantity: 2,
}

function seedCart(items) {
  window.localStorage.setItem(CART_STORAGE_KEY_FOR_TESTS, JSON.stringify(items))
}

describe('Cart 頁', () => {
  it('沒有商品時顯示空車狀態', () => {
    // renderWithProviders 一定會掛上 ExchangeRateProvider（即使這頁沒用到匯率），
    // 它掛載時會呼叫 fetch，所以每個用到這個 helper 的測試都要先擋掉真網路呼叫。
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network disabled in test')))
    renderWithProviders(<Cart />)
    expect(screen.getByTestId('cart-empty')).toBeInTheDocument()
  })

  it('有商品時顯示品項、小計與總計', () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network disabled in test')))
    seedCart([seededItem])
    renderWithProviders(<Cart />)

    expect(screen.getByText('耶加雪菲 淺焙單品豆 250g')).toBeInTheDocument()
    expect(screen.getByTestId('quantity-value')).toHaveTextContent('2')
    expect(within(screen.getByTestId('cart-item')).getByText('NT$1,040')).toBeInTheDocument() // 520 * 2 的品項小計
    expect(screen.getByTestId('cart-total')).toHaveTextContent('NT$1,040')
  })

  it('按下數量加號會更新該品項數量與總計', () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network disabled in test')))
    seedCart([seededItem])
    renderWithProviders(<Cart />)

    fireEvent.click(screen.getByLabelText('增加數量'))

    expect(screen.getByTestId('quantity-value')).toHaveTextContent('3')
    expect(screen.getByTestId('cart-total')).toHaveTextContent('NT$1,560') // 520 * 3
  })

  it('按下移除會把品項拿掉，購物車變回空車狀態', () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network disabled in test')))
    seedCart([seededItem])
    renderWithProviders(<Cart />)

    fireEvent.click(screen.getByRole('button', { name: '移除' }))

    expect(screen.getByTestId('cart-empty')).toBeInTheDocument()
  })
})
