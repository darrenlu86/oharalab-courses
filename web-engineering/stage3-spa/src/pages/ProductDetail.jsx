import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import products from '../data/products.json'
import StockBadge from '../components/StockBadge'
import PriceTag from '../components/PriceTag'
import QuantityStepper from '../components/QuantityStepper'
import { useCart } from '../context/CartContext'
import { categoryLabel } from '../utils/categories'

export default function ProductDetail() {
  const { id } = useParams()
  const product = products.find((item) => item.id === Number(id))
  const { addItem } = useCart()
  const [quantity, setQuantity] = useState(1)
  const [justAdded, setJustAdded] = useState(false)

  if (!product) {
    return (
      <div className="container section">
        <p className="empty-state">
          找不到這個商品。<Link to="/products">回到商品列表</Link>
        </p>
      </div>
    )
  }

  const outOfStock = product.stock <= 0

  const handleAddToCart = () => {
    addItem(product, quantity)
    setJustAdded(true)
  }

  return (
    <div className="container section product-detail">
      <Link to="/products" className="back-link">
        ← 回商品列表
      </Link>

      <div className="product-detail__grid">
        <img src={product.image} alt={product.name} className="product-detail__image" />

        <div className="product-detail__info">
          <span className="product-card__category">{categoryLabel(product.category)}</span>
          <h1 className="product-detail__name">{product.name}</h1>
          <p className="product-detail__description">{product.description}</p>

          <PriceTag price={product.price} />
          <StockBadge stock={product.stock} />

          {outOfStock ? (
            <p className="product-detail__out-of-stock" data-testid="out-of-stock-note">
              此商品目前補貨中，暫時無法加入購物車。
            </p>
          ) : (
            <div className="product-detail__actions">
              <QuantityStepper value={quantity} max={product.stock} onChange={setQuantity} />
              <button type="button" className="btn btn--primary" onClick={handleAddToCart}>
                加入購物車
              </button>
            </div>
          )}

          {justAdded && (
            <p className="product-detail__added-note" role="status">
              已加入購物車，
              <Link to="/cart">查看購物車</Link>
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
