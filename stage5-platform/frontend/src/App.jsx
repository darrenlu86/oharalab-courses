import { Route, Routes } from 'react-router-dom'
import Header from './components/Header'
import Footer from './components/Footer'
import Home from './pages/Home'
import Products from './pages/Products'
import ProductDetail from './pages/ProductDetail'
import Cart from './pages/Cart'
import Checkout from './pages/Checkout'
import Pay from './pages/Pay'
import OrderComplete from './pages/OrderComplete'
import Orders from './pages/Orders'
import Login from './pages/Login'
import NotFound from './pages/NotFound'

export default function App() {
  return (
    <div className="app-shell">
      <Header />
      <main className="app-main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/products" element={<Products />} />
          <Route path="/products/:id" element={<ProductDetail />} />
          <Route path="/login" element={<Login />} />
          <Route path="/cart" element={<Cart />} />
          <Route path="/checkout" element={<Checkout />} />
          {/* stage5 新增：結帳兩步流程的第二步，見 pages/Pay.jsx 開頭的說明 */}
          <Route path="/pay/:orderId" element={<Pay />} />
          <Route path="/order-complete/:orderId" element={<OrderComplete />} />
          <Route path="/orders" element={<Orders />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <Footer />
    </div>
  )
}
