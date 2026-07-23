// 通用數量選擇器：ProductDetail（選購買幾件）跟 Cart（改購物車內數量）共用同一個元件，
// 上限一律是呼叫端傳進來的 max（通常是庫存數），不在這裡寫死任何商業邏輯。
//
// `disabled`：新增給 Cart 頁使用——商品被下架後，這個品項不應該還能調整數量
// （見 pages/Cart.jsx 對 `is_active === false` 的判斷），預設 false 不影響
// ProductDetail 既有的呼叫方式。
export default function QuantityStepper({ value, min = 1, max, onChange, disabled = false }) {
  const decrease = () => {
    if (!disabled && value > min) onChange(value - 1)
  }
  const increase = () => {
    if (!disabled && value < max) onChange(value + 1)
  }

  return (
    <div className="quantity-stepper">
      <button
        type="button"
        className="quantity-stepper__btn"
        onClick={decrease}
        disabled={disabled || value <= min}
        aria-label="減少數量"
      >
        −
      </button>
      <span className="quantity-stepper__value" data-testid="quantity-value">
        {value}
      </span>
      <button
        type="button"
        className="quantity-stepper__btn"
        onClick={increase}
        disabled={disabled || value >= max}
        aria-label="增加數量"
      >
        ＋
      </button>
    </div>
  )
}
