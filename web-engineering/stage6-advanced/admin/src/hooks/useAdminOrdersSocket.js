// `/ws/admin/orders` 的後台連線 hook——跟 frontend/src/hooks/useOrdersSocket.js
// 是同一套 exponential backoff 重連設計（完整理由見那支檔案的開頭說明，這裡
// 不重複展開）。唯一的差異：後台連線失敗有兩種「不該重連」的 close code——
// 4401（未登入）與 4403（登入了但不是 admin，見 backend/app/routers/ws.py），
// 兩者都應該讓使用者知道連線失敗、不要一直悄悄重試。
import { useEffect, useRef, useState } from 'react'

const INITIAL_BACKOFF_MS = 1000
const MAX_BACKOFF_MS = 16000
const AUTH_FAILURE_CLOSE_CODE = 4401
const FORBIDDEN_CLOSE_CODE = 4403

function buildWsUrl(path, token) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}${path}?token=${encodeURIComponent(token)}`
}

/**
 * @param {string|null} token JWT；null 代表未登入，不會嘗試連線。
 * @param {(message: object) => void} onMessage 收到伺服器推播事件時呼叫。
 */
export function useAdminOrdersSocket(token, onMessage) {
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
      socket = new WebSocket(buildWsUrl('/ws/admin/orders', token))

      socket.onopen = () => {
        backoffMs = INITIAL_BACKOFF_MS
        setConnectionState('connected')
      }

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          onMessageRef.current?.(data)
        } catch {
          // 忽略格式異常的訊息，理由跟前台版本一致
        }
      }

      socket.onclose = (event) => {
        if (cancelled) return
        if (event.code === AUTH_FAILURE_CLOSE_CODE || event.code === FORBIDDEN_CLOSE_CODE) {
          setConnectionState('auth-failed')
          return
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
