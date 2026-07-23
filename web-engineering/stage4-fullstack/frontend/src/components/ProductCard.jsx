import { Link } from 'react-router-dom'
import StockBadge from './StockBadge'
import PriceTag from './PriceTag'
import { categoryLabel } from '../utils/categories'

// 跟 stage3 的差異只有一個欄位名稱：後端 ProductOut 回傳的圖片欄位叫 `image_url`
// （對齊資料庫欄位名稱），不是 stage3 靜態 JSON 裡的 `image`。元件邏輯完全沒變。
export default function ProductCard({ product }) {
  return (
    <article className="product-card" data-testid="product-card">
      <Link to={`/products/${product.id}`} className="product-card__image-link">
        <img src={product.image_url} alt={product.name} className="product-card__image" loading="lazy" />
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
