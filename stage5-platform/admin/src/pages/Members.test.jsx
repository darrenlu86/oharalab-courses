import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import Members from './Members'
import { renderWithProviders } from '../test/renderWithProviders'
import { stubApi } from '../test/mockApi'

const adminUser = { id: 1, email: 'admin@brewgo.test', name: '店長 Admin', role: 'admin' }

describe('Members 頁（後台）', () => {
  it('顯示會員清單，且不包含密碼欄位', async () => {
    stubApi({
      'GET /auth/me': () => ({ status: 200, body: adminUser }),
      'GET /admin/users': () => ({
        status: 200,
        body: {
          items: [
            { id: 1, email: 'admin@brewgo.test', name: '店長 Admin', role: 'admin', created_at: '2026-07-01 00:00:00' },
            {
              id: 2,
              email: 'customer@brewgo.test',
              name: '測試顧客',
              role: 'customer',
              created_at: '2026-07-02 00:00:00',
            },
          ],
        },
      }),
    })

    renderWithProviders(<Members />, { token: 'fake-admin-token' })

    expect(await screen.findByText('customer@brewgo.test')).toBeInTheDocument()
    expect(screen.getByText('顧客')).toBeInTheDocument()
    expect(screen.getByText('管理員')).toBeInTheDocument()
    expect(screen.queryByText(/password/i)).not.toBeInTheDocument()
  })
})
