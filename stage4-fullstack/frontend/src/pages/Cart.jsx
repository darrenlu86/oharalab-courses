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
export default function Cart() {
  const { items, subtotal, updateQuantity, removeItem } = useCart()
  const [error, setError] = useState('')

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
        {items.map((item) => (
          <li key={item.product_id} className="cart-item" data-testid="cart-item">
            <img src={item.image_url} alt={item.name} className="cart-item__image" />
            <div className="cart-item__info">
              <Link to={`/products/${item.product_id}`} className="cart-item__name">
                {item.name}
              </Link>
              <span className="cart-item__unit-price">{formatCurrency(item.price)} / 件</span>
            </div>
            <QuantityStepper
              value={item.quantity}
              max={item.stock}
              onChange={(next) => handleUpdateQuantity(item.product_id, next)}
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
        ))}
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
        <Link to="/checkout" className="btn btn--primary">
          前往結帳
        </Link>
      </div>
    </div>
  )
}
