import { useEffect, useState } from 'react'

// 第三方 API：open.er-api.com（immune-key 公開匯率 API，不需註冊、不需金鑰）。
// 文件：https://www.exchangerate-api.com/docs/free
// 呼叫端點：https://open.er-api.com/v6/latest/TWD（base=TWD，回傳 TWD 兌各國幣別的匯率）
//
// 離線／API 掛掉時的預設參考匯率：
// 這組數字不是隨手編的，是 2026-07-23 用 curl 實際打過一次上面那支 API 記錄下來的真實回應
// （time_last_update_utc: "Thu, 23 Jul 2026 00:02:31 +0000"，rates.USD=0.030855、rates.JPY=5.030669）。
// 拿真實抓到的一組快照當離線 fallback，比自己亂編數字更貼近現實，但仍然只是「某個時間點的快照」，
// 之後匯率一定會變動 —— 這就是為什麼畫面上一定要標示「離線參考匯率」，不能讓使用者誤以為是即時匯率。
export const FALLBACK_RATES = {
  USD: 0.030855,
  JPY: 5.030669,
}

const EXCHANGE_RATE_API_URL = 'https://open.er-api.com/v6/latest/TWD'

export function useExchangeRate() {
  const [status, setStatus] = useState('loading') // 'loading' | 'success' | 'error'
  const [rates, setRates] = useState(FALLBACK_RATES)

  useEffect(() => {
    let cancelled = false

    async function fetchRates() {
      try {
        const response = await fetch(EXCHANGE_RATE_API_URL)
        if (!response.ok) {
          throw new Error(`匯率 API 回傳非 2xx 狀態：${response.status}`)
        }
        const data = await response.json()
        const usd = data?.rates?.USD
        const jpy = data?.rates?.JPY
        if (typeof usd !== 'number' || typeof jpy !== 'number') {
          throw new Error('匯率 API 回應格式不符預期（缺少 rates.USD 或 rates.JPY）')
        }
        if (cancelled) return
        setRates({ USD: usd, JPY: jpy })
        setStatus('success')
      } catch (error) {
        // 三態教學的核心：不管是斷網、API 掛掉、還是回應格式跑掉，
        // 一律 fallback 回內建匯率，讓「看外幣參考價」這個小功能安靜地降級，
        // 不影響網站其他功能（商品列表、購物車、結帳完全不依賴這支 API）。
        console.warn('匯率 API 呼叫失敗，改用離線參考匯率', error)
        if (cancelled) return
        setRates(FALLBACK_RATES)
        setStatus('error')
      }
    }

    fetchRates()

    return () => {
      cancelled = true
    }
  }, [])

  return {
    status,
    rates,
    isFallback: status === 'error',
  }
}
