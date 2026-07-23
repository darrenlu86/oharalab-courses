import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="container section">
      <h1 className="section__title">404 — 找不到這個頁面</h1>
      <p>
        你要找的頁面不存在，<Link to="/">回首頁</Link>看看吧。
      </p>
    </div>
  )
}
