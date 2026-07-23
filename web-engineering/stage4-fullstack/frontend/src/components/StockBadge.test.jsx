import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import StockBadge from './StockBadge'

describe('StockBadge', () => {
  it('庫存充足時顯示「現貨供應」', () => {
    render(<StockBadge stock={25} />)
    expect(screen.getByTestId('stock-badge')).toHaveTextContent('現貨供應')
  })

  it('庫存 <= 5 時顯示「僅剩 N 件」', () => {
    render(<StockBadge stock={3} />)
    expect(screen.getByTestId('stock-badge')).toHaveTextContent('僅剩 3 件')
  })

  it('庫存為 0 時顯示「補貨中」', () => {
    render(<StockBadge stock={0} />)
    expect(screen.getByTestId('stock-badge')).toHaveTextContent('補貨中')
  })
})
