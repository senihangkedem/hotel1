import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const navByRole = {
  OWNER: [
    { label: 'Dashboard', to: '/dashboard' },
    { label: 'Restaurants', to: '/restaurants' },
    { label: 'Menu', to: '/menu' },
    { label: 'Recipes', to: '/staff/menu' },
    { label: 'Inventory', to: '/inventory' },
    { label: 'Orders', to: '/orders' },
    { label: 'Staff Orders', to: '/staff/orders' },
    { label: 'Billing Settings', to: '/staff/billing-settings' },
    { label: 'Analytics', to: '/staff/analytics' },
    { label: 'Staff Members', to: '/staff/members' },
    { label: 'Profile', to: '/profile' },
  ],
  CUSTOMER: [
    { label: 'Dashboard', to: '/dashboard' },
    { label: 'Menu', to: '/menu' },
    { label: 'Orders', to: '/orders' },
    { label: 'Profile', to: '/profile' },
  ],
  SUPERUSER: [
    { label: 'Dashboard', to: '/dashboard' },
    { label: 'Restaurants', to: '/restaurants' },
    { label: 'Menu', to: '/menu' },
    { label: 'Recipes', to: '/staff/menu' },
    { label: 'Inventory', to: '/inventory' },
    { label: 'Orders', to: '/orders' },
    { label: 'Staff Orders', to: '/staff/orders' },
    { label: 'Billing Settings', to: '/staff/billing-settings' },
    { label: 'Analytics', to: '/staff/analytics' },
    { label: 'Staff Members', to: '/staff/members' },
    { label: 'Profile', to: '/profile' },
  ],
  MANAGER: [
    { label: 'Dashboard', to: '/dashboard' },
    { label: 'Restaurants', to: '/restaurants' },
    { label: 'Menu', to: '/menu' },
    { label: 'Recipes', to: '/staff/menu' },
    { label: 'Inventory', to: '/inventory' },
    { label: 'Staff Orders', to: '/staff/orders' },
    { label: 'Billing Settings', to: '/staff/billing-settings' },
    { label: 'Analytics', to: '/staff/analytics' },
    { label: 'Profile', to: '/profile' },
  ],
  KITCHEN: [
    { label: 'Dashboard', to: '/dashboard' },
    { label: 'Staff Orders', to: '/staff/orders' },
  ],
  WAITER: [
    { label: 'Dashboard', to: '/dashboard' },
    { label: 'Restaurants', to: '/restaurants' },
    { label: 'Staff Orders', to: '/staff/orders' },
    { label: 'Profile', to: '/profile' },
  ],
}

export default function DashboardLayout() {
  const { user, logout } = useAuth()
  const roles = new Set((user?.staff_memberships || []).map((membership) => membership.role))
  if (user?.is_superuser) roles.add('SUPERUSER')
  if (['OWNER', 'CUSTOMER', 'SUPERUSER'].includes(user?.role)) {
    roles.add(user.role)
  }
  if (roles.size === 0) roles.add('CUSTOMER')
  const navItems = [...new Map(
    [...roles].flatMap((role) => navByRole[role] || []).map((item) => [item.to, item]),
  ).values()]

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">Restaurant SaaS</div>
        <nav>
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="content-area">
        <header className="topbar">
          <div>
            <strong>{user?.username}</strong>
            <span className="role-badge">{user?.role}</span>
          </div>
          <button type="button" onClick={logout}>Logout</button>
        </header>
        <Outlet />
      </main>
    </div>
  )
}
