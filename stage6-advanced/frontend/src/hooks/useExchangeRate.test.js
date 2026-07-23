import { describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useExchangeRate, FALLBACK_RATES } from './useExchangeRate'

describe('useExchangeRate', () => {
  it('loading -> success：API 成功時採用回應的匯率，isFallback 為 false', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ rates: { USD: 0.031, JPY: 5.1 } }),
      }),
    )

    const { result } = renderHook(() => useExchangeRate())

    expect(result.current.status).toBe('loading')

    await waitFor(() => {
      expect(result.current.status).toBe('success')
    })

    expect(result.current.rates).toEqual({ USD: 0.031, JPY: 5.1 })
    expect(result.current.isFallback).toBe(false)
  })

  it('loading -> error：fetch 失敗（例如斷網）時改用離線參考匯率，並標記 isFallback', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network error')))

    const { result } = renderHook(() => useExchangeRate())

    await waitFor(() => {
      expect(result.current.status).toBe('error')
    })

    expect(result.current.rates).toEqual(FALLBACK_RATES)
    expect(result.current.isFallback).toBe(true)
  })

  it('API 回傳非 2xx 狀態時也視為失敗、改用離線參考匯率', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({}),
      }),
    )

    const { result } = renderHook(() => useExchangeRate())

    await waitFor(() => {
      expect(result.current.status).toBe('error')
    })

    expect(result.current.isFallback).toBe(true)
  })

  it('API 回應格式跑掉（缺少 rates 欄位）時也會安全地 fallback', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ unexpected: 'shape' }),
      }),
    )

    const { result } = renderHook(() => useExchangeRate())

    await waitFor(() => {
      expect(result.current.status).toBe('error')
    })

    expect(result.current.rates).toEqual(FALLBACK_RATES)
  })
})
