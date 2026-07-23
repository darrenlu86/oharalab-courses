import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import ProductCard from '../components/ProductCard'
import { apiFetch } from '../api/client'
import { CATEGORY_ORDER, categoryLabel } from '../utils/categories'

const FEATURED_IDS = [1, 4, 7, 12]

// 跟 stage3 的差異：商品資料改成 useEffect + fetch 向後端要，不再是
// `import products from '../data/products.json'` 這種打包進前端的靜態資料。
// 這代表 Home 頁現在需要處理「還沒拿到資料」的 loading 狀態——stage3 因為資料
// 是同步就能拿到的本地 JSON，完全不需要考慮這件事。
export default function Home() {
  const [products, setProducts] = useState([])
  const [status, setStatus] = useState('loading') // 'loading' | 'ready' | 'error'

  useEffect(() => {
    let cancelled = false
    apiFetch('/products')
      .then((data) => {
        if (!cancelled) {
          setProducts(data.items)
          setStatus('ready')
        }
      })
      .catch(() => {
        if (!cancelled) setStatus('error')
      })
    return () => {
      cancelled = true
    }
  }, [])

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
        {status === 'loading' && <p className="empty-state">商品讀取中...</p>}
        {status === 'error' && (
          <p className="empty-state">
            商品讀取失敗，請確認後端伺服器是否已啟動（見 README「快速開始」）。
          </p>
        )}
        {status === 'ready' && (
          <div className="product-grid">
            {featured.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
        )}
      </section>
    </>
  )
}
