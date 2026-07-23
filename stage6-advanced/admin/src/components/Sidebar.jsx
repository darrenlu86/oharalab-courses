import { NavLink, useNavigate } from 'react-router-dom'
import { useAdminAuth } from '../context/AdminAuthContext'

// 側欄導覽——深色變體（`--admin-sidebar-bg`），沿用 BrewGo 的色彩 tokens
// （--color-primary 系列），只是把背景跟前景反過來，讓後台一眼就能跟前台區分開，
// 不會誤以為自己還在顧客看的頁面。
export default function Sidebar() {
  const { user, logout } = useAdminAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <aside className="admin-sidebar">
      <div className="admin-sidebar__brand">
        <span className="admin-sidebar__brand-name">BrewGo 後台</span>
      </div>

      <nav className="admin-sidebar__nav" aria-label="後台導覽">
        <NavLink to="/" end className={({ isActive }) => (isActive ? 'admin-nav-link is-active' : 'admin-nav-link')}>
          Dashboard
        </NavLink>
        <NavLink
          to="/products"
          className={({ isActive }) => (isActive ? 'admin-nav-link is-active' : 'admin-nav-link')}
        >
          商品管理
        </NavLink>
        <NavLink to="/orders" className={({ isActive }) => (isActive ? 'admin-nav-link is-active' : 'admin-nav-link')}>
          訂單管理
        </NavLink>
        <NavLink
          to="/members"
          className={({ isActive }) => (isActive ? 'admin-nav-link is-active' : 'admin-nav-link')}
        >
          會員清單
        </NavLink>
      </nav>

      <div className="admin-sidebar__footer">
        {user && <p className="admin-sidebar__user">{user.name}</p>}
        <button type="button" className="admin-btn admin-btn--ghost" onClick={handleLogout}>
          登出
        </button>
      </div>
    </aside>
  )
}
