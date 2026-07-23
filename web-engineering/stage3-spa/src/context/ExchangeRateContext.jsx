import { createContext, useContext } from 'react'
import { useExchangeRate } from '../hooks/useExchangeRate'

// 為什麼多包一層 Context，而不是讓每個 PriceTag 各自呼叫 useExchangeRate：
// 商品列表頁一次會渲染 12 張 ProductCard，如果每張卡片各自呼叫一次 useExchangeRate，
// 就會同時打 12 次外部 API（瀏覽器頂多還會因為快取/去重把它們合併，但這是碰運氣，不是設計）。
// 把 hook 呼叫「提升」到 Provider 只執行一次、結果透過 Context 分享給所有子元件，
// 才是「全站共享一份第三方資料」該有的做法 —— 這跟 CartContext 的設計理由是同一套邏輯。

const ExchangeRateContext = createContext(null)

export function ExchangeRateProvider({ children }) {
  const exchangeRate = useExchangeRate()
  return (
    <ExchangeRateContext.Provider value={exchangeRate}>{children}</ExchangeRateContext.Provider>
  )
}

export function useExchangeRateContext() {
  const context = useContext(ExchangeRateContext)
  if (!context) {
    throw new Error('useExchangeRateContext 必須在 <ExchangeRateProvider> 內使用')
  }
  return context
}
