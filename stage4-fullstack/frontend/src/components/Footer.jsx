export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="container site-footer__inner">
        <p>BrewGo 沖沖咖啡 — 每天沖一杯好咖啡</p>
        <p className="site-footer__note">
          本站為網站工程課程教學範例（stage4 互動式動態網頁·後端），商品、會員與訂單資料存在真正的後端與
          SQLite 資料庫裡，但沒有真實金流，訂單成立後不會實際出貨。
        </p>
      </div>
    </footer>
  )
}
