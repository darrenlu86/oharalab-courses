import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useCart } from '../context/CartContext'
import QuantityStepper from '../components/QuantityStepper'
import { formatCurrency } from '../utils/formatCurrency'
import { ApiError } from '../api/client'

// 跟 stage3 的差異：items 現在來自後端（`product_id` 取代 stage3 的 `id`，
// 因為這是後端 CartItemOut 的欄位命名，對齊「商品」跟「購物車項目」是兩個不同
// 概念這件事——見 docs/DATABASE.md 的資料表設計）；改數量／移除現在是打
// PATCH / DELETE API，庫存上限是後端當下給的即時值，不是加入當下的快照，
// 所以這裡多了「後端可能回 409」的錯誤處理（例如你打開這頁面之後，商品被
// 別人買到剩更少的庫存）。
//
// 已下架品項（`is_active === false`）：商品被後台下架後不會自動從購物車移除
// （見 backend/app/db/database.py `get_cart_items()` 的說明），這裡把它標成
// 「已下架」徽章、停用數量調整、並且擋掉「前往結帳」按鈕——這一整段判斷純粹
// 是**前端的體驗優化**，就算完全跳過（例如直接打 API），真正擋住建單的仍然是
// 後端 `POST /api/orders` 的 409（見 backend/app/routers/orders.py）。這是本
// 教材「後端守門、前端好心提示」分層的一個具體示範：兩邊都要做，但角色不同。
export default function Cart() {
  const { items, subtotal, updateQuantity, removeItem } = useCart()
  const [error, setError] = useState('')
  const hasInactiveItems = items.some((item) => item.is_active === false)

  const handleUpdateQuantity = async (productId, next) => {
    setError('')
    try {
      await updateQuantity(productId, next)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '更新數量失敗，請稍後再試')
    }
  }

  const handleRemove = async (productId) => {
    setError('')
    try {
      await removeItem(productId)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '移除商品失敗，請稍後再試')
    }
  }

  if (items.length === 0) {
    return (
      <div className="container section">
        <h1 className="section__title">購物車</h1>
        <p className="empty-state" data-testid="cart-empty">
          購物車是空的。<Link to="/products">去逛逛商品</Link>
        </p>
      </div>
    )
  }

  return (
    <div className="container section">
      <h1 className="section__title">購物車</h1>

      {error && (
        <p className="form-error" role="alert" data-testid="cart-error">
          {error}
        </p>
      )}

      <ul className="cart-list">
        {items.map((item) => {
          const isDelisted = item.is_active === false
          return (
            <li
              key={item.product_id}
              className={`cart-item${isDelisted ? ' cart-item--delisted' : ''}`}
              data-testid="cart-item"
            >
              <img src={item.image_url} alt={item.name} className="cart-item__image" />
              <div className="cart-item__info">
                <Link to={`/products/${item.product_id}`} className="cart-item__name">
                  {item.name}
                </Link>
                <span className="cart-item__unit-price">{formatCurrency(item.price)} / 件</span>
                {isDelisted && (
                  <span className="cart-item__delisted-note">
                    <span className="delisted-badge" data-testid="delisted-badge">
                      已下架
                    </span>
                    建議移除，無法用這個品項結帳
                  </span>
                )}
              </div>
              <QuantityStepper
                value={item.quantity}
                max={item.stock}
                onChange={(next) => handleUpdateQuantity(item.product_id, next)}
                disabled={isDelisted}
              />
              <span className="cart-item__line-total">{formatCurrency(item.subtotal)}</span>
              <button
                type="button"
                className="btn btn--text btn--danger"
                onClick={() => handleRemove(item.product_id)}
              >
                移除
              </button>
            </li>
          )
        })}
      </ul>

      <div className="cart-summary">
        <span className="cart-summary__label">總計</span>
        <span className="cart-summary__total" data-testid="cart-total">
          {formatCurrency(subtotal)}
        </span>
      </div>

      <div className="cart-actions">
        <Link to="/products" className="btn btn--secondary">
          繼續購物
        </Link>
        {hasInactiveItems ? (
          <div className="cart-actions__checkout-blocked">
            <button
              type="button"
              className="btn btn--primary"
              disabled
              data-testid="checkout-button"
              title="購物車內有已下架商品，請先移除再結帳"
            >
              前往結帳
            </button>
            <p className="cart-actions__blocked-reason" data-testid="checkout-blocked-reason">
              購物車內有已下架商品，請先移除再結帳
            </p>
          </div>
        ) : (
          <Link to="/checkout" className="btn btn--primary" data-testid="checkout-button">
            前往結帳
          </Link>
        )}
      </div>
    </div>
  )
}
