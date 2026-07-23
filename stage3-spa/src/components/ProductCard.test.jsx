import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import ProductCard from './ProductCard'
import { renderWithProviders } from '../test/renderWithProviders'

const product = {
  id: 1,
  name: '耶加雪菲 淺焙單品豆 250g',
  category: 'beans',
  price: 520,
  stock: 25,
  description: '柑橘與茉莉花香，日曬處理',
  image: '/images/p1.svg',
}

describe('ProductCard', () => {
  it('渲染商品名稱、分類中文名、價格與庫存徽章', () => {
    // ProductCard 內部用到 PriceTag -> useExchangeRateContext -> useExchangeRate 會呼叫 fetch，
    // 測試不可以打真網路，這裡固定回傳「失敗」讓它走 fallback（fallback 是同步可預期的內建值）。
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network disabled in test')))

    renderWithProviders(<ProductCard product={product} />)

    expect(screen.getByText('耶加雪菲 淺焙單品豆 250g')).toBeInTheDocument()
    expect(screen.getByText('咖啡豆')).toBeInTheDocument()
    expect(screen.getByText('NT$520')).toBeInTheDocument()
    expect(screen.getByTestId('stock-badge')).toHaveTextContent('現貨供應')
  })

  it('商品圖片的 alt 文字等於商品名稱', () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network disabled in test')))
    renderWithProviders(<ProductCard product={product} />)
    expect(screen.getByAltText('耶加雪菲 淺焙單品豆 250g')).toBeInTheDocument()
  })
})
