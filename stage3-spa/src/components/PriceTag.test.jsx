import { describe, expect, it, vi } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import PriceTag from './PriceTag'
import { renderWithProviders } from '../test/renderWithProviders'

describe('PriceTag', () => {
  it('預設只顯示 NT$ 價格，不顯示外幣', () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network disabled in test')))
    renderWithProviders(<PriceTag price={520} />)
    expect(screen.getByText('NT$520')).toBeInTheDocument()
    expect(screen.queryByTestId('price-tag-foreign')).not.toBeInTheDocument()
  })

  it('匯率 API 失敗時，切到 USD 會顯示離線參考匯率提示', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network disabled in test')))
    renderWithProviders(<PriceTag price={520} />)

    fireEvent.click(screen.getByRole('button', { name: 'USD' }))

    await waitFor(() => {
      expect(screen.getByTestId('price-tag-foreign')).toHaveTextContent('離線參考匯率')
    })
  })

  it('匯率 API 成功時，切到 JPY 會顯示換算後的參考價、不顯示離線提示', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ rates: { USD: 0.031, JPY: 5 } }),
      }),
    )
    renderWithProviders(<PriceTag price={100} />)

    fireEvent.click(screen.getByRole('button', { name: 'JPY' }))

    await waitFor(() => {
      expect(screen.getByTestId('price-tag-foreign')).toHaveTextContent('JPY 500')
    })
    expect(screen.getByTestId('price-tag-foreign')).not.toHaveTextContent('離線參考匯率')
  })
})
