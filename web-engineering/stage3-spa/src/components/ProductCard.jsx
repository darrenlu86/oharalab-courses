import { Link } from 'react-router-dom'
import StockBadge from './StockBadge'
import PriceTag from './PriceTag'
import { categoryLabel } from '../utils/categories'

export default function ProductCard({ product }) {
  return (
    <article className="product-card" data-testid="product-card">
      <Link to={`/products/${product.id}`} className="product-card__image-link">
        <img src={product.image} alt={product.name} className="product-card__image" loading="lazy" />
      </Link>
      <div className="product-card__body">
        <span className="product-card__category">{categoryLabel(product.category)}</span>
        <h3 className="product-card__name">
          <Link to={`/products/${product.id}`}>{product.name}</Link>
        </h3>
        <p className="product-card__description">{product.description}</p>
        <div className="product-card__meta">
          <PriceTag price={product.price} />
          <StockBadge stock={product.stock} />
        </div>
      </div>
    </article>
  )
}
