import { useEffect, useState } from 'react'
import { apiFetch } from '../api/client'

const ROLE_LABEL = { customer: '顧客', admin: '管理員' }

// 會員清單——唯讀，沒有刪除也沒有編輯。理由（隱私教學點，見
// backend/app/routers/admin.py 開頭的說明）：帳號的歷史訂單需要保留 user_id
// 才能對帳，直接刪除帳號會破壞這個關聯；正式產品的作法是「停用帳號」而不是
// 刪除，本階段教學上只示範最基本的「唯讀清單」。
export default function Members() {
  const [users, setUsers] = useState([])
  const [status, setStatus] = useState('loading')

  useEffect(() => {
    apiFetch('/admin/users')
      .then((data) => {
        setUsers(data.items)
        setStatus('ready')
      })
      .catch(() => setStatus('error'))
  }, [])

  if (status === 'loading') {
    return <p className="admin-empty">會員讀取中...</p>
  }

  if (status === 'error') {
    return <p className="admin-empty">會員讀取失敗，請確認已登入且後端伺服器正常運作。</p>
  }

  return (
    <div>
      <h1 className="admin-page-title">會員清單</h1>
      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>會員 id</th>
              <th>Email</th>
              <th>姓名</th>
              <th>角色</th>
              <th>註冊時間</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td>{user.id}</td>
                <td>{user.email}</td>
                <td>{user.name}</td>
                <td>{ROLE_LABEL[user.role] ?? user.role}</td>
                <td>{user.created_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
