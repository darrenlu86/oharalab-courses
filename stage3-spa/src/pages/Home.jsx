import { Link } from 'react-router-dom'
import ProductCard from '../components/ProductCard'
import products from '../data/products.json'
import { CATEGORY_ORDER, categoryLabel } from '../utils/categories'

const FEATURED_IDS = [1, 4, 7, 12]

export default function Home() {
  const featured = FEATURED_IDS.map((id) => products.find((product) => product.id === id)).filter(Boolean)

  return (
    <>
      <section className="hero">
        <div className="container hero__inner">
          <h1 className="hero__title">每天沖一杯好咖啡</h1>
          <p className="hero__subtitle">
            BrewGo 沖沖咖啡線上選購 — 精選咖啡豆、掛耳包與沖煮器具，從一顆豆子到一杯手沖，一次備齊。
          </p>
          <Link to="/products" className="btn btn--primary">
            前往選購
          </Link>
        </div>
      </section>

      <section className="container section">
        <h2 className="section__title">分類快速入口</h2>
        <div className="category-grid">
          {CATEGORY_ORDER.map((code) => (
            <Link key={code} to={`/products?category=${code}`} className="category-grid__item">
              {categoryLabel(code)}
            </Link>
          ))}
        </div>
      </section>

      <section className="container section">
        <h2 className="section__title">精選商品</h2>
        <div className="product-grid">
          {featured.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      </section>
    </>
  )
}
