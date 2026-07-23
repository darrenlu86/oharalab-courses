import { describe, expect, it } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import Login from './Login'
import { renderWithProviders } from '../test/renderWithProviders'
import { stubApi } from '../test/mockApi'

describe('Login 頁（後台）', () => {
  it('非 admin 帳號登入會被前端擋下來，顯示錯誤訊息、不儲存 token', async () => {
    stubApi({
      'POST /auth/login': () => ({
        status: 200,
        body: {
          access_token: 'fake-customer-token',
          token_type: 'bearer',
          user: { id: 1, email: 'customer@brewgo.test', name: '測試顧客', role: 'customer' },
        },
      }),
    })
    renderWithProviders(<Login />)

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'customer@brewgo.test' } })
    fireEvent.change(screen.getByLabelText('密碼'), { target: { value: 'Customer12345' } })
    fireEvent.click(screen.getByRole('button', { name: '登入' }))

    expect(await screen.findByTestId('admin-login-error')).toHaveTextContent('不是管理員')
    expect(window.localStorage.getItem('brewgo_admin_token_v1')).toBeNull()
  })

  it('admin 帳號登入成功會呼叫 /auth/login 並把 token 存進 localStorage', async () => {
    stubApi({
      'POST /auth/login': () => ({
        status: 200,
        body: {
          access_token: 'fake-admin-token',
          token_type: 'bearer',
          user: { id: 2, email: 'admin@brewgo.test', name: '店長 Admin', role: 'admin' },
        },
      }),
    })
    renderWithProviders(<Login />)

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'admin@brewgo.test' } })
    fireEvent.change(screen.getByLabelText('密碼'), { target: { value: 'Admin12345' } })
    fireEvent.click(screen.getByRole('button', { name: '登入' }))

    await waitFor(() => expect(window.localStorage.getItem('brewgo_admin_token_v1')).toBe('fake-admin-token'))
  })

  it('帳密錯誤時顯示後端回傳的錯誤訊息', async () => {
    stubApi({
      'POST /auth/login': () => ({ status: 401, body: { detail: 'email 或密碼錯誤' } }),
    })
    renderWithProviders(<Login />)

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'nobody@brewgo.test' } })
    fireEvent.change(screen.getByLabelText('密碼'), { target: { value: 'wrongpassword' } })
    fireEvent.click(screen.getByRole('button', { name: '登入' }))

    expect(await screen.findByTestId('admin-login-error')).toHaveTextContent('email 或密碼錯誤')
  })
})
