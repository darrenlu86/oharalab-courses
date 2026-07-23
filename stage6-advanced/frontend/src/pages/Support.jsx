// 客服助理頁——本階段新增，stage5 完全沒有這個頁面。用瀏覽器原生的
// `EventSource` 連線 `GET /api/support/stream?question=...`（見
// backend/app/routers/support.py），逐段把回覆文字接起來，做出打字機效果。
//
// **誠實聲明**：這不是真的 AI 客服，是後端規則式 FAQ 比對（完整理由與比對規則
// 見 support.py 開頭的說明）。這頁的重點是示範「SSE 逐字串流」這個 UX 模式
// 本身怎麼實作，不是做出一個聰明的客服機器人。
//
// 為什麼不用 apiFetch()：`apiFetch`（見 api/client.js）是為了一般「一次請求、
// 一次回應」的 REST API 設計的（`fetch()` + `response.json()`），`EventSource`
// 是瀏覽器另一套完全不同的 API，設計上就是為了處理「一次請求、持續收到多個
// 事件」的情境，兩者不適合共用同一個封裝，這頁直接使用原生 `EventSource`。
import { useEffect, useRef, useState } from 'react'

export default function Support() {
  const [question, setQuestion] = useState('')
  const [log, setLog] = useState([]) // [{ role: 'user' | 'assistant', text: string, streaming: boolean }]
  const eventSourceRef = useRef(null)

  useEffect(() => {
    // 離開頁面時把還開著的連線關掉，不要讓它繼續在背景收 event——EventSource
    // 不會因為元件被移除就自動斷線，這是瀏覽器原生 API 常見的「要自己收拾」陷阱。
    return () => {
      eventSourceRef.current?.close()
    }
  }, [])

  const askQuestion = (event) => {
    event.preventDefault()
    const trimmed = question.trim()
    if (!trimmed) return

    eventSourceRef.current?.close()

    setLog((prev) => [...prev, { role: 'user', text: trimmed }, { role: 'assistant', text: '', streaming: true }])
    setQuestion('')

    const source = new EventSource(`/api/support/stream?question=${encodeURIComponent(trimmed)}`)
    eventSourceRef.current = source

    source.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.done) {
        setLog((prev) => prev.map((entry, index) => (index === prev.length - 1 ? { ...entry, streaming: false } : entry)))
        source.close()
        return
      }
      setLog((prev) =>
        prev.map((entry, index) =>
          index === prev.length - 1 ? { ...entry, text: entry.text + data.chunk } : entry,
        ),
      )
    }

    source.onerror = () => {
      // EventSource 內建重連機制（瀏覽器原生行為），但這裡的串流是「針對這一次
      // 提問的一次性回覆」，回覆完就該結束，不需要無限重連——出錯就直接關閉，
      // 讓使用者自己決定要不要重問一次。
      setLog((prev) =>
        prev.map((entry, index) =>
          index === prev.length - 1
            ? { ...entry, text: entry.text || '連線發生問題，請稍後再試一次。', streaming: false }
            : entry,
        ),
      )
      source.close()
    }
  }

  return (
    <div className="container section support-page">
      <h1 className="section__title">客服助理</h1>
      <p className="mock-notice">
        這是規則式 FAQ 比對的示範客服，不是真的 AI；能回答的問題有限（出貨、退貨、庫存、付款、咖啡豆挑選）。
      </p>

      <form className="support-form" onSubmit={askQuestion}>
        <input
          type="text"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="輸入你的問題，例如：多久出貨？"
          aria-label="輸入問題"
        />
        <button type="submit" className="btn btn--primary">
          送出
        </button>
      </form>

      <div className="support-log">
        {log.map((entry, index) => (
          <p
            key={index}
            className={`support-message support-message--${entry.role}${entry.streaming ? ' support-message--typing' : ''}`}
          >
            {entry.text}
          </p>
        ))}
      </div>
    </div>
  )
}
