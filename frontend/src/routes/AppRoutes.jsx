import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import DashboardLayout from '../layouts/DashboardLayout'
import DashboardPage from '../pages/DashboardPage'
import LoginPage from '../pages/LoginPage'
import MenuPage from '../pages/MenuPage'
import OrdersPage from '../pages/OrdersPage'
import OrderDetailPage from '../pages/OrderDetailPage'
import StaffOrdersPage from '../pages/StaffOrdersPage'
import StaffOrderDetailPage from '../pages/StaffOrderDetailPage'
import StaffMembersPage from '../pages/StaffMembersPage'
import StaffMenuPage from '../pages/StaffMenuPage'
import InventoryPage from '../pages/InventoryPage'
import BillingSettingsPage from '../pages/BillingSettingsPage'
import BillingReceiptPage from '../pages/BillingReceiptPage'
import AnalyticsPage from '../pages/AnalyticsPage'
import ProfilePage from '../pages/ProfilePage'
import RestaurantListPage from '../pages/RestaurantListPage'
import RestaurantMenuPage from '../pages/RestaurantMenuPage'
import RestaurantTablePage from '../pages/RestaurantTablePage'
import CartPage from '../pages/CartPage'
import CheckoutPage from '../pages/CheckoutPage'
import { useAuth } from '../context/AuthContext'

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return <div className="page-shell">Loading your session...</div>
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  return children
}

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/restaurants" element={<RestaurantListPage />} />
        <Route path="/restaurants/:restaurantId/menu/:tableId?" element={<RestaurantMenuPage />} />
        <Route path="/restaurants/:restaurantId/tables" element={<RestaurantTablePage />} />
        <Route path="/menu" element={<MenuPage />} />
        <Route path="/cart" element={<CartPage />} />
        <Route path="/checkout" element={<CheckoutPage />} />
        <Route path="/orders" element={<OrdersPage />} />
        <Route path="/orders/:id" element={<OrderDetailPage />} />
        <Route path="/staff/orders" element={<StaffOrdersPage />} />
        <Route path="/staff/orders/:id" element={<StaffOrderDetailPage />} />
        <Route path="/staff/members" element={<StaffMembersPage />} />
        <Route path="/staff/menu" element={<StaffMenuPage />} />
        <Route path="/inventory" element={<InventoryPage />} />
        <Route path="/staff/billing-settings" element={<BillingSettingsPage />} />
        <Route path="/billing/:billId/receipt" element={<BillingReceiptPage />} />
        <Route path="/staff/analytics" element={<AnalyticsPage />} />
        <Route path="/profile" element={<ProfilePage />} />
      </Route>

      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
