import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const roleCards = {
  OWNER: [
    { title: 'Restaurants', to: '/restaurants' },
    { title: 'Menu', to: '/menu' },
    { title: 'Recipes', to: '/staff/menu' },
    { title: 'Inventory', to: '/inventory' },
    { title: 'Orders', to: '/orders' },
    { title: 'Staff members', to: '/staff/members' },
    { title: 'Billing settings', to: '/staff/billing-settings' },
    { title: 'Analytics', to: '/staff/analytics' },
  ],
  CUSTOMER: [
    { title: 'Browse menu', to: '/menu' },
    { title: 'Orders', to: '/orders' },
    { title: 'Profile', to: '/profile' },
  ],
  SUPERUSER: [
    { title: 'Admin overview', to: '/dashboard' },
    { title: 'Restaurants', to: '/restaurants' },
    { title: 'Orders', to: '/orders' },
    { title: 'Staff members', to: '/staff/members' },
    { title: 'Billing settings', to: '/staff/billing-settings' },
    { title: 'Analytics', to: '/staff/analytics' },
  ],
  MANAGER: [
    { title: 'Restaurants', to: '/restaurants' },
    { title: 'Menu', to: '/menu' },
    { title: 'Recipes', to: '/staff/menu' },
    { title: 'Inventory', to: '/inventory' },
    { title: 'Staff orders', to: '/staff/orders' },
    { title: 'Billing settings', to: '/staff/billing-settings' },
    { title: 'Analytics', to: '/staff/analytics' },
  ],
  KITCHEN: [
    { title: 'Kitchen orders', to: '/staff/orders' },
  ],
  WAITER: [
    { title: 'Restaurants and tables', to: '/restaurants' },
    { title: 'Staff orders', to: '/staff/orders' },
  ],
}

export default function DashboardPage() {
  const { user, logout } = useAuth()
  const roles = new Set((user?.staff_memberships || []).map((membership) => membership.role))
  if (user?.is_superuser) roles.add('SUPERUSER')
  if (['OWNER', 'CUSTOMER', 'SUPERUSER'].includes(user?.role)) {
    roles.add(user.role)
  }
  if (roles.size === 0) roles.add('CUSTOMER')
  const cards = [...new Map(
    [...roles].flatMap((role) => roleCards[role] || []).map((card) => [card.to, card]),
  ).values()]

  return (
    <div className="page-shell">
      <div className="topbar">
        <div>
          <h1>Dashboard</h1>
        </div>
        <div className="user-meta">
          <span>{user?.username}</span>
          <span className="role-badge">{user?.role}</span>
          <button type="button" onClick={logout}>Logout</button>
        </div>
      </div>

      <div className="dashboard-grid">
        {cards.map((card) => (
          <Link key={card.title} to={card.to} className="info-card">
            <h3>{card.title}</h3>
            <p>Open {card.title.toLowerCase()}.</p>
          </Link>
        ))}
      </div>
    </div>
  )
}
