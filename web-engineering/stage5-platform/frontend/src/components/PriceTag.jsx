import { useState } from 'react'
import { formatCurrency, formatForeignCurrency } from '../utils/formatCurrency'
import { useExchangeRateContext } from '../context/ExchangeRateContext'

const CURRENCY_OPTIONS = [
  { code: 'TWD', label: 'NT$' },
  { code: 'USD', label: 'USD' },
  { code: 'JPY', label: 'JPY' },
]

// 外幣參考價只是「參考」：用 TWD 價格乘上目前拿到的匯率換算出來，
// 不是真的用外幣結帳（結帳全程只有 NT$，見 Checkout 頁）。
export default function PriceTag({ price }) {
  const [selected, setSelected] = useState('TWD')
  const { status, rates, isFallback } = useExchangeRateContext()

  const foreignValue = selected === 'TWD' ? null : price * rates[selected]

  return (
    <div className="price-tag">
      <div className="price-tag__row">
        <span className="price-tag__amount">{formatCurrency(price)}</span>
        <div className="price-tag__toggle" role="group" aria-label="切換參考幣別">
          {CURRENCY_OPTIONS.map((option) => (
            <button
              key={option.code}
              type="button"
              className={
                selected === option.code ? 'price-tag__toggle-btn is-active' : 'price-tag__toggle-btn'
              }
              onClick={() => setSelected(option.code)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {selected !== 'TWD' && (
        <p className="price-tag__foreign" data-testid="price-tag-foreign">
          {status === 'loading' && '匯率讀取中...'}
          {status !== 'loading' && (
            <>
              約 {formatForeignCurrency(foreignValue, selected)}
              {isFallback && <span className="price-tag__fallback-note">（離線參考匯率）</span>}
            </>
          )}
        </p>
      )}
    </div>
  )
}
