// `/ws/my/orders` 的前端連線 hook——本階段新增，stage5 完全沒有這個檔案。
//
// 教學重點：**斷線重連要用 exponential backoff，不能無腦立刻重連**。如果後端
// 剛好在重啟、或網路暫時不通，「斷線 → 立刻重連 → 又失敗 → 立刻再重連」會在
// 極短時間內狂發大量連線請求，瀏覽器與伺服器都會被無謂的重試淹沒。
// exponential backoff 的作法：第一次斷線等 1 秒重連，失敗再等 2 秒、4 秒、
// 8 秒……每次重連前的等待時間翻倍，直到一個上限（這裡設 16 秒）就不再增加，
// 一旦成功連上就把等待時間重設回 1 秒——這樣「暫時性的網路抖動」很快就能恢復，
// 「後端真的掛了一段時間」也不會讓瀏覽器瘋狂重試打伺服器。
//
// 認證失敗（close code 4401，見 backend/app/routers/ws.py）**不重連**：token
// 失效不會因為多重試幾次就變好，一直重試只是浪費資源，這種情況直接讓呼叫端
// 知道連線失敗、由使用者重新登入即可。
import { useEffect, useRef, useState } from 'react'

const INITIAL_BACKOFF_MS = 1000
const MAX_BACKOFF_MS = 16000
const AUTH_FAILURE_CLOSE_CODE = 4401

function buildWsUrl(path, token) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}${path}?token=${encodeURIComponent(token)}`
}

/**
 * @param {string|null} token JWT；null 代表未登入，不會嘗試連線。
 * @param {(message: object) => void} onMessage 收到伺服器推播事件時呼叫。
 * @returns {{ connectionState: 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'auth-failed' }}
 */
export function useOrdersSocket(token, onMessage) {
  const [connectionState, setConnectionState] = useState('idle')
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  useEffect(() => {
    if (!token) {
      setConnectionState('idle')
      return undefined
    }

    let socket = null
    let reconnectTimer = null
    let backoffMs = INITIAL_BACKOFF_MS
    let cancelled = false

    function connect() {
      if (cancelled) return
      setConnectionState((prev) => (prev === 'idle' ? 'connecting' : prev))
      socket = new WebSocket(buildWsUrl('/ws/my/orders', token))

      socket.onopen = () => {
        backoffMs = INITIAL_BACKOFF_MS // 連上就重設等待時間
        setConnectionState('connected')
      }

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          onMessageRef.current?.(data)
        } catch {
          // 收到非 JSON 內容理論上不該發生（後端只會送 JSON），安靜忽略即可，
          // 不應該讓一則格式異常的訊息讓整個連線掛掉。
        }
      }

      socket.onclose = (event) => {
        if (cancelled) return
        if (event.code === AUTH_FAILURE_CLOSE_CODE) {
          setConnectionState('auth-failed')
          return // 認證失敗不重連，理由見檔案開頭說明
        }
        setConnectionState('reconnecting')
        reconnectTimer = window.setTimeout(() => {
          backoffMs = Math.min(backoffMs * 2, MAX_BACKOFF_MS)
          connect()
        }, backoffMs)
      }
    }

    connect()

    return () => {
      cancelled = true
      if (reconnectTimer) window.clearTimeout(reconnectTimer)
      socket?.close()
    }
  }, [token])

  return { connectionState }
}
