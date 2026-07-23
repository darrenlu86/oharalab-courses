import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import ProductCard from '../components/ProductCard'
import CategoryTabs from '../components/CategoryTabs'
import SearchBox from '../components/SearchBox'
import { apiFetch } from '../api/client'

// 跟 stage3 最大的差異：分類篩選跟關鍵字搜尋不再是前端對本地陣列做 `.filter()`，
// 而是直接把 category / search 帶成 query string 打給後端，由資料庫的 SQL
// （`WHERE category = ? AND name LIKE ?`，見 backend/app/db/database.py 的
// list_products()）做真正的篩選——這是「同一個前端，把資料層從假的換成真的」
// 在這一頁最直接的示範。分類一樣用 URL query string 記錄（沿用 stage3 的設計
// 理由：分類快速入口的連結可以分享／加書籤／重新整理都還在同一個分類）。
export default function Products() {
  const [searchParams, setSearchParams] = useSearchParams()
  const category = searchParams.get('category') ?? 'all'
  const [keyword, setKeyword] = useState('')
  const [products, setProducts] = useState([])
  const [status, setStatus] = useState('loading')

  useEffect(() => {
    let cancelled = false
    setStatus('loading')
    const params = new URLSearchParams()
    if (category !== 'all') params.set('category', category)
    if (keyword.trim()) params.set('search', keyword.trim())
    const query = params.toString()

    apiFetch(`/products${query ? `?${query}` : ''}`)
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
  }, [category, keyword])

  const handleCategoryChange = (nextCategory) => {
    if (nextCategory === 'all') {
      setSearchParams({})
    } else {
      setSearchParams({ category: nextCategory })
    }
  }

  return (
    <div className="container section">
      <h1 className="section__title">全部商品</h1>

      <div className="products-toolbar">
        <CategoryTabs active={category} onChange={handleCategoryChange} />
        <SearchBox value={keyword} onChange={setKeyword} />
      </div>

      {status === 'loading' && <p className="empty-state">商品讀取中...</p>}
      {status === 'error' && (
        <p className="empty-state">商品讀取失敗，請確認後端伺服器是否已啟動。</p>
      )}
      {status === 'ready' && products.length === 0 && (
        <p className="empty-state">沒有符合條件的商品，換個分類或關鍵字試試。</p>
      )}
      {status === 'ready' && products.length > 0 && (
        <div className="product-grid">
          {products.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      )}
    </div>
  )
}
