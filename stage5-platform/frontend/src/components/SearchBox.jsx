export default function SearchBox({ value, onChange, placeholder = '搜尋商品名稱...' }) {
  return (
    <div className="search-box">
      <label htmlFor="product-search" className="visually-hidden">
        搜尋商品
      </label>
      <input
        id="product-search"
        type="search"
        className="search-box__input"
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  )
}
