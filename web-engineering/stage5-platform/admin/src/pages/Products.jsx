import { useEffect, useState } from 'react'
import { apiFetch, ApiError } from '../api/client'
import { formatCurrency } from '../utils/formatCurrency'

const CATEGORY_LABEL = {
  beans: '咖啡豆',
  drip: '掛耳包',
  gear: '沖煮器具',
  cups: '杯具',
  gift: '禮盒',
}

const EMPTY_NEW_PRODUCT = {
  name: '',
  description: '',
  price: '',
  stock: '',
  category: 'beans',
  image_url: '/images/p1.svg',
}

// 商品管理——列表／新增／編輯／上下架。刻意沒有「刪除」按鈕：後端
// `PATCH /api/admin/products/{id}` 只接受局部更新（見
// backend/app/db/database.py `update_product()`），沒有對應的 DELETE 端點，
// 這是資料保護的教學點（理由見 backend/app/routers/admin.py 開頭的說明）。
export default function Products() {
  const [products, setProducts] = useState([])
  const [status, setStatus] = useState('loading')
  const [actionError, setActionError] = useState('')
  const [editingId, setEditingId] = useState(null)
  const [editDraft, setEditDraft] = useState({ price: '', stock: '' })
  const [showNewForm, setShowNewForm] = useState(false)
  const [newProduct, setNewProduct] = useState(EMPTY_NEW_PRODUCT)
  const [creating, setCreating] = useState(false)

  const loadProducts = () => {
    setStatus('loading')
    apiFetch('/admin/products')
      .then((data) => {
        setProducts(data.items)
        setStatus('ready')
      })
      .catch(() => setStatus('error'))
  }

  useEffect(loadProducts, [])

  const startEdit = (product) => {
    setEditingId(product.id)
    setEditDraft({ price: String(product.price), stock: String(product.stock) })
    setActionError('')
  }

  const saveEdit = async (productId) => {
    setActionError('')
    try {
      const updated = await apiFetch(`/admin/products/${productId}`, {
        method: 'PATCH',
        body: JSON.stringify({ price: Number(editDraft.price), stock: Number(editDraft.stock) }),
      })
      setProducts((prev) => prev.map((product) => (product.id === productId ? updated : product)))
      setEditingId(null)
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : '更新商品失敗')
    }
  }

  const toggleActive = async (product) => {
    setActionError('')
    try {
      const updated = await apiFetch(`/admin/products/${product.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: !product.is_active }),
      })
      setProducts((prev) => prev.map((item) => (item.id === product.id ? updated : item)))
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : '更新上下架狀態失敗')
    }
  }

  const handleCreate = async (event) => {
    event.preventDefault()
    setActionError('')
    setCreating(true)
    try {
      const created = await apiFetch('/admin/products', {
        method: 'POST',
        body: JSON.stringify({
          ...newProduct,
          price: Number(newProduct.price),
          stock: Number(newProduct.stock),
        }),
      })
      setProducts((prev) => [...prev, created])
      setNewProduct(EMPTY_NEW_PRODUCT)
      setShowNewForm(false)
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : '新增商品失敗')
    } finally {
      setCreating(false)
    }
  }

  if (status === 'loading') {
    return <p className="admin-empty">商品讀取中...</p>
  }

  if (status === 'error') {
    return <p className="admin-empty">商品讀取失敗，請確認已登入且後端伺服器正常運作。</p>
  }

  return (
    <div>
      <div className="admin-page-header">
        <h1 className="admin-page-title">商品管理</h1>
        <button type="button" className="admin-btn admin-btn--primary" onClick={() => setShowNewForm((v) => !v)}>
          {showNewForm ? '取消新增' : '新增商品'}
        </button>
      </div>

      {actionError && (
        <p className="admin-form-error" role="alert" data-testid="products-action-error">
          {actionError}
        </p>
      )}

      {showNewForm && (
        <form className="admin-form" onSubmit={handleCreate}>
          <div className="admin-form-grid">
            <div className="admin-form-field">
              <label htmlFor="new-name">名稱</label>
              <input
                id="new-name"
                required
                value={newProduct.name}
                onChange={(event) => setNewProduct((prev) => ({ ...prev, name: event.target.value }))}
              />
            </div>
            <div className="admin-form-field">
              <label htmlFor="new-category">分類</label>
              <select
                id="new-category"
                value={newProduct.category}
                onChange={(event) => setNewProduct((prev) => ({ ...prev, category: event.target.value }))}
              >
                {Object.entries(CATEGORY_LABEL).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="admin-form-field">
              <label htmlFor="new-price">價格（新台幣元）</label>
              <input
                id="new-price"
                type="number"
                min="1"
                required
                value={newProduct.price}
                onChange={(event) => setNewProduct((prev) => ({ ...prev, price: event.target.value }))}
              />
            </div>
            <div className="admin-form-field">
              <label htmlFor="new-stock">庫存</label>
              <input
                id="new-stock"
                type="number"
                min="0"
                required
                value={newProduct.stock}
                onChange={(event) => setNewProduct((prev) => ({ ...prev, stock: event.target.value }))}
              />
            </div>
            <div className="admin-form-field admin-form-field--wide">
              <label htmlFor="new-description">一句話描述</label>
              <input
                id="new-description"
                required
                value={newProduct.description}
                onChange={(event) => setNewProduct((prev) => ({ ...prev, description: event.target.value }))}
              />
            </div>
          </div>
          <button type="submit" className="admin-btn admin-btn--primary" disabled={creating}>
            {creating ? '新增中...' : '確認新增'}
          </button>
        </form>
      )}

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>編號</th>
              <th>名稱</th>
              <th>分類</th>
              <th>價格</th>
              <th>庫存</th>
              <th>狀態</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {products.map((product) => (
              <tr key={product.id}>
                <td>{product.id}</td>
                <td>{product.name}</td>
                <td>{CATEGORY_LABEL[product.category] ?? product.category}</td>
                <td>
                  {editingId === product.id ? (
                    <input
                      type="number"
                      min="1"
                      value={editDraft.price}
                      onChange={(event) => setEditDraft((prev) => ({ ...prev, price: event.target.value }))}
                      className="admin-inline-input"
                    />
                  ) : (
                    formatCurrency(product.price)
                  )}
                </td>
                <td>
                  {editingId === product.id ? (
                    <input
                      type="number"
                      min="0"
                      value={editDraft.stock}
                      onChange={(event) => setEditDraft((prev) => ({ ...prev, stock: event.target.value }))}
                      className="admin-inline-input"
                    />
                  ) : (
                    product.stock
                  )}
                </td>
                <td>
                  <span className={product.is_active ? 'admin-badge admin-badge--on' : 'admin-badge admin-badge--off'}>
                    {product.is_active ? '上架中' : '已下架'}
                  </span>
                </td>
                <td className="admin-table__actions">
                  {editingId === product.id ? (
                    <>
                      <button type="button" className="admin-btn admin-btn--small" onClick={() => saveEdit(product.id)}>
                        儲存
                      </button>
                      <button
                        type="button"
                        className="admin-btn admin-btn--ghost admin-btn--small"
                        onClick={() => setEditingId(null)}
                      >
                        取消
                      </button>
                    </>
                  ) : (
                    <>
                      <button type="button" className="admin-btn admin-btn--small" onClick={() => startEdit(product)}>
                        編輯
                      </button>
                      <button
                        type="button"
                        className="admin-btn admin-btn--ghost admin-btn--small"
                        onClick={() => toggleActive(product)}
                      >
                        {product.is_active ? '下架' : '上架'}
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
