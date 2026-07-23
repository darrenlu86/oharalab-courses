import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import Dashboard from './Dashboard'
import { renderWithProviders } from '../test/renderWithProviders'
import { stubApi } from '../test/mockApi'

const adminUser = { id: 1, email: 'admin@brewgo.test', name: '店長 Admin', role: 'admin' }

describe('Dashboard 頁（後台）', () => {
  it('顯示 /api/admin/summary 回傳的數字卡、低庫存表與最近訂單', async () => {
    stubApi({
      'GET /auth/me': () => ({ status: 200, body: adminUser }),
      'GET /admin/summary': () => ({
        status: 200,
        body: {
          total_revenue: 12345,
          total_orders: 8,
          pending_shipment_orders: 2,
          low_stock_products: [{ id: 11, name: '冷萃咖啡瓶 1L', category: 'gear', stock: 0 }],
          member_count: 3,
        },
      }),
      'GET /admin/orders': () => ({
        status: 200,
        body: {
          items: [
            {
              id: 1,
              user_id: 2,
              status: 'paid',
              total_amount: 520,
              recipient_name: '測試顧客',
              recipient_address: '台北市',
              created_at: '2026-07-14 10:00:00',
              updated_at: '2026-07-14 10:00:00',
              items: [],
            },
          ],
        },
      }),
    })

    renderWithProviders(<Dashboard />, { token: 'fake-admin-token' })

    expect(await screen.findByText('NT$12,345')).toBeInTheDocument()
    expect(screen.getByText('8')).toBeInTheDocument()
    expect(screen.getByText('冷萃咖啡瓶 1L')).toBeInTheDocument()
  })

  it('讀取失敗時顯示錯誤訊息，不會整頁崩潰', async () => {
    stubApi({
      'GET /auth/me': () => ({ status: 200, body: adminUser }),
      'GET /admin/summary': () => ({ status: 500, body: { detail: '伺服器錯誤' } }),
      'GET /admin/orders': () => ({ status: 500, body: { detail: '伺服器錯誤' } }),
    })

    renderWithProviders(<Dashboard />, { token: 'fake-admin-token' })

    expect(await screen.findByText(/Dashboard 讀取失敗/)).toBeInTheDocument()
  })
})
