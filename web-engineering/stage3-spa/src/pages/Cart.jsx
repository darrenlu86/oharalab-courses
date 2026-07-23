import { Link } from 'react-router-dom'
import { useCart } from '../context/CartContext'
import QuantityStepper from '../components/QuantityStepper'
import { formatCurrency } from '../utils/formatCurrency'

export default function Cart() {
  const { items, subtotal, updateQuantity, removeItem } = useCart()

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

      <ul className="cart-list">
        {items.map((item) => (
          <li key={item.id} className="cart-item" data-testid="cart-item">
            <img src={item.image} alt={item.name} className="cart-item__image" />
            <div className="cart-item__info">
              <Link to={`/products/${item.id}`} className="cart-item__name">
                {item.name}
              </Link>
              <span className="cart-item__unit-price">{formatCurrency(item.price)} / 件</span>
            </div>
            <QuantityStepper
              value={item.quantity}
              max={item.stock}
              onChange={(next) => updateQuantity(item.id, next)}
            />
            <span className="cart-item__line-total">{formatCurrency(item.price * item.quantity)}</span>
            <button
              type="button"
              className="btn btn--text btn--danger"
              onClick={() => removeItem(item.id)}
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
