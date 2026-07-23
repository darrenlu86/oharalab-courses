import { NavLink } from 'react-router-dom'
import { useCart } from '../context/CartContext'

// header 的購物車數字徽章是「全站共享狀態」最直接的示範：
// 不管你在 Home、Products 還是 ProductDetail 加入商品，Header（跟它一起被渲染的所有頁面）
// 都會立刻看到數字更新 —— 因為大家讀的都是同一個 CartContext，不是各自複製一份狀態。
export default function Header() {
  const { totalQuantity } = useCart()

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
        </nav>
      </div>
    </header>
  )
}
