import { CATEGORY_ORDER, categoryLabel } from '../utils/categories'

export default function CategoryTabs({ active, onChange }) {
  const tabs = ['all', ...CATEGORY_ORDER]

  return (
    <div className="category-tabs" role="tablist" aria-label="商品分類">
      {tabs.map((code) => (
        <button
          key={code}
          type="button"
          role="tab"
          aria-selected={active === code}
          className={active === code ? 'category-tab is-active' : 'category-tab'}
          onClick={() => onChange(code)}
        >
          {code === 'all' ? '全部' : categoryLabel(code)}
        </button>
      ))}
    </div>
  )
}
