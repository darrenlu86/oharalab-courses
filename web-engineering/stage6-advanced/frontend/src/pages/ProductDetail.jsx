import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import StockBadge from '../components/StockBadge'
import PriceTag from '../components/PriceTag'
import QuantityStepper from '../components/QuantityStepper'
import { useCart } from '../context/CartContext'
import { useAuth } from '../context/AuthContext'
import { apiFetch, ApiError } from '../api/client'
import { categoryLabel } from '../utils/categories'

// 跟 stage3 的差異：商品用 GET /api/products/:id 向後端要，「找不到商品」現在是
// 後端真的回了 404（見 backend/app/routers/products.py），不是本地陣列 `.find()`
// 找不到而已；加入購物車也從「在瀏覽器記憶體裡直接改 state」變成「打 API、
// 等後端確認庫存真的夠才成功」——庫存不足時（例如兩個人幾乎同時搶購同一件
// 僅剩 3 件的商品）後端會回 409，這裡要接住並顯示錯誤，這是 stage3 純前端
// demo 完全不會遇到的情境（stage3 README「與上一階段的差異」已經點出這個限制，
// 這裡就是實際把它解決掉的地方）。
export default function ProductDetail() {
  const { id } = useParams()
  const { addItem } = useCart()
  const { isAuthenticated } = useAuth()
  const [product, setProduct] = useState(null)
  const [status, setStatus] = useState('loading') // 'loading' | 'ready' | 'not-found' | 'error'
  const [quantity, setQuantity] = useState(1)
  const [justAdded, setJustAdded] = useState(false)
  const [addError, setAddError] = useState('')

  useEffect(() => {
    let cancelled = false
    setStatus('loading')
    setJustAdded(false)
    setAddError('')
    apiFetch(`/products/${id}`)
      .then((data) => {
        if (!cancelled) {
          setProduct(data)
          setQuantity(1)
          setStatus('ready')
        }
      })
      .catch((err) => {
        if (cancelled) return
        setStatus(err instanceof ApiError && err.status === 404 ? 'not-found' : 'error')
      })
    return () => {
      cancelled = true
    }
  }, [id])

  if (status === 'loading') {
    return (
      <div className="container section">
        <p className="empty-state">商品讀取中...</p>
      </div>
    )
  }

  if (status === 'not-found') {
    return (
      <div className="container section">
        <p className="empty-state">
          找不到這個商品。<Link to="/products">回到商品列表</Link>
        </p>
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div className="container section">
        <p className="empty-state">商品讀取失敗，請確認後端伺服器是否已啟動。</p>
      </div>
    )
  }

  const outOfStock = product.stock <= 0

  const handleAddToCart = async () => {
    setAddError('')
    try {
      await addItem(product.id, quantity)
      // 未登入時 addItem 會直接導去 /login，不會走到這裡；只有登入狀態下
      // 呼叫成功才需要顯示「已加入購物車」的提示。
      if (isAuthenticated) {
        setJustAdded(true)
      }
    } catch (err) {
      // 常見情境：庫存在你瀏覽這頁的期間被別人買走了，後端回 409。
      setAddError(err instanceof ApiError ? err.message : '加入購物車失敗，請稍後再試')
    }
  }

  return (
    <div className="container section product-detail">
      <Link to="/products" className="back-link">
        ← 回商品列表
      </Link>

      <div className="product-detail__grid">
        <img src={product.image_url} alt={product.name} className="product-detail__image" />

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

          {addError && (
            <p className="form-error" role="alert" data-testid="add-to-cart-error">
              {addError}
            </p>
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
