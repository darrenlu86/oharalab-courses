import { Navigate, Route, Routes } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import { useAdminAuth } from './context/AdminAuthContext'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Products from './pages/Products'
import Orders from './pages/Orders'
import Members from './pages/Members'

// 路由層級的登入保護——跟前台不同，前台完全沒有這種「整頁擋掉」的寫法（前台
// 只有個別 API 需要登入，未登入時各頁自己決定要顯示什麼）。後台的教學立場是
// 「沒登入／不是管理員，直接看不到任何後台畫面」，理由：後台顯示的是全站營運
// 資料（營收、所有會員清單），這類頁面比較適合用「整頁擋」而不是「單支 API
// 擋」，多一層縱深防禦，即使某個頁面元件不小心忘記處理 401，使用者也看不到
// 畫面本身（當然，真正擋住資料外洩的還是後端的 require_admin，見
// backend/app/deps.py，前端這層永遠只是體驗優化，不是安全邊界）。
function ProtectedLayout({ children }) {
  const { isAuthenticated, isChecking } = useAdminAuth()

  if (isChecking) {
    return (
      <div className="admin-loading">
        <p>驗證登入狀態中...</p>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return (
    <div className="admin-shell">
      <Sidebar />
      <main className="admin-main">{children}</main>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <ProtectedLayout>
            <Dashboard />
          </ProtectedLayout>
        }
      />
      <Route
        path="/products"
        element={
          <ProtectedLayout>
            <Products />
          </ProtectedLayout>
        }
      />
      <Route
        path="/orders"
        element={
          <ProtectedLayout>
            <Orders />
          </ProtectedLayout>
        }
      />
      <Route
        path="/members"
        element={
          <ProtectedLayout>
            <Members />
          </ProtectedLayout>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
