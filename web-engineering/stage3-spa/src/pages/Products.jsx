import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import ProductCard from '../components/ProductCard'
import CategoryTabs from '../components/CategoryTabs'
import SearchBox from '../components/SearchBox'
import products from '../data/products.json'

// 分類用 URL query string（?category=beans）記錄，是刻意的設計：
// 這樣「分類快速入口」的連結（Home 頁）可以直接分享／加書籤／重新整理都還在同一個分類，
// 搜尋關鍵字則用元件內部 state 就好，因為教學上不需要讓搜尋字串也能被分享連結還原。
export default function Products() {
  const [searchParams, setSearchParams] = useSearchParams()
  const category = searchParams.get('category') ?? 'all'
  const [keyword, setKeyword] = useState('')

  const filtered = useMemo(() => {
    const normalizedKeyword = keyword.trim().toLowerCase()
    return products.filter((product) => {
      const matchesCategory = category === 'all' || product.category === category
      const matchesKeyword =
        normalizedKeyword === '' || product.name.toLowerCase().includes(normalizedKeyword)
      return matchesCategory && matchesKeyword
    })
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

      {filtered.length === 0 ? (
        <p className="empty-state">沒有符合條件的商品，換個分類或關鍵字試試。</p>
      ) : (
        <div className="product-grid">
          {filtered.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      )}
    </div>
  )
}
