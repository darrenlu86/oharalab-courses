import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import ProductCard from './ProductCard'
import { renderWithProviders } from '../test/renderWithProviders'
import { stubApi } from '../test/mockApi'

// 跟 stage3 的差異：product 物件的圖片欄位是 `image_url`（後端 ProductOut 的
// 欄位命名），不是 stage3 靜態 JSON 裡的 `image`；渲染這個元件時 AuthProvider
// 會嘗試打 /auth/me（因為 renderWithProviders 沒有給 token，會直接判定未登入、
// 不會真的呼叫 API），所以這裡不需要額外 stub /auth/me。
const product = {
  id: 1,
  name: '耶加雪菲 淺焙單品豆 250g',
  category: 'beans',
  price: 520,
  stock: 25,
  description: '柑橘與茉莉花香，日曬處理',
  image_url: '/images/p1.svg',
}

describe('ProductCard', () => {
  it('渲染商品名稱、分類中文名、價格與庫存徽章', () => {
    stubApi()
    renderWithProviders(<ProductCard product={product} />)

    expect(screen.getByText('耶加雪菲 淺焙單品豆 250g')).toBeInTheDocument()
    expect(screen.getByText('咖啡豆')).toBeInTheDocument()
    expect(screen.getByText('NT$520')).toBeInTheDocument()
    expect(screen.getByTestId('stock-badge')).toHaveTextContent('現貨供應')
  })

  it('商品圖片的 alt 文字等於商品名稱，src 指向 image_url', () => {
    stubApi()
    renderWithProviders(<ProductCard product={product} />)
    const img = screen.getByAltText('耶加雪菲 淺焙單品豆 250g')
    expect(img).toHaveAttribute('src', '/images/p1.svg')
  })
})
