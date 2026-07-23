import { NavLink, useNavigate } from 'react-router-dom'
import { useCart } from '../context/CartContext'
import { useAuth } from '../context/AuthContext'

// 跟 stage3 的差異：多了登入狀態的顯示。未登入時顯示「登入」連結；登入後顯示
// 使用者姓名與「登出」按鈕——這是全站共享的 AuthContext 最直接的示範，
// 邏輯跟「header 的購物車數字徽章跨頁即時同步」是同一套 Context 共享狀態的道理。
export default function Header() {
  const { totalQuantity } = useCart()
  const { isAuthenticated, user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <header className="site-header">
      <div className="container site-header__inner">
        <NavLink to="/" className="brand" end>
          <img src="/images/logo.svg" alt="" className="brand__logo" width="36" height="36" />
          <span className="brand__name">BrewGo 沖沖咖啡</span>
        </NavLink>

        <nav className="site-nav" aria-label="主要導覽">
          <NavLink to="/" end className={({ isActive }) => (isActive ? 'site-nav__link is-active' : 'site-nav__link')}>
            首頁
          </NavLink>
          <NavLink to="/products" className={({ isActive }) => (isActive ? 'site-nav__link is-active' : 'site-nav__link')}>
            全部商品
          </NavLink>
          <NavLink to="/orders" className={({ isActive }) => (isActive ? 'site-nav__link is-active' : 'site-nav__link')}>
            訂單查詢
          </NavLink>
          <NavLink
            to="/cart"
            className={({ isActive }) => (isActive ? 'site-nav__link cart-link is-active' : 'site-nav__link cart-link')}
          >
            購物車
            {totalQuantity > 0 && (
              <span className="cart-badge" data-testid="cart-badge">
                {totalQuantity}
              </span>
            )}
          </NavLink>

          {isAuthenticated ? (
            <span className="site-nav__auth" data-testid="header-user">
              <span className="site-nav__user-name">{user.name}</span>
              <button type="button" className="btn btn--text" onClick={handleLogout}>
                登出
              </button>
            </span>
          ) : (
            <NavLink
              to="/login"
              className={({ isActive }) => (isActive ? 'site-nav__link is-active' : 'site-nav__link')}
            >
              登入
            </NavLink>
          )}
        </nav>
      </div>
    </header>
  )
}
