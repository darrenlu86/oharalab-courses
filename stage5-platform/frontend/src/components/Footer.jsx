export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="container site-footer__inner">
        <p>BrewGo 沖沖咖啡 — 每天沖一杯好咖啡</p>
        <p className="site-footer__note">
          本站為網站工程課程教學範例（stage5 完整應用系統·前台＋後台），商品、會員、訂單與付款資料存在真正的
          後端與 SQLite 資料庫裡，但付款是自建的模擬金流，不會有任何真實金錢往來，訂單成立後也不會實際出貨。
        </p>
      </div>
    </footer>
  )
}
