// 庫存徽章三態：這是本階段「元件依資料狀態切換顯示」的最小示範。
// 門檻訂在「<= 5 件」算低庫存，是教學上刻意抓的一個簡單整數門檻，
// 真實產品通常會依商品週轉率、備貨前置時間動態決定這個數字，不是寫死的 5。
const LOW_STOCK_THRESHOLD = 5

export default function StockBadge({ stock }) {
  if (stock <= 0) {
    return (
      <span className="stock-badge stock-badge--out" data-testid="stock-badge">
        補貨中
      </span>
    )
  }
  if (stock <= LOW_STOCK_THRESHOLD) {
    return (
      <span className="stock-badge stock-badge--low" data-testid="stock-badge">
        僅剩 {stock} 件
      </span>
    )
  }
  return (
    <span className="stock-badge stock-badge--in" data-testid="stock-badge">
      現貨供應
    </span>
  )
}
