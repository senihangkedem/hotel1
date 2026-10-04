import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/client'

function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function formatPrice(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '$0.00'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(numeric)
}

export default function OrdersPage() {
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchOrders = async () => {
      try {
        setLoading(true)
        setError('')
        const response = await api.get('/orders/orders/')
        setOrders(Array.isArray(response.data) ? response.data : [])
      } catch (err) {
        setError(err.response?.status === 401 ? 'Please log in again to view your orders.' : 'Unable to load your orders right now.')
      } finally {
        setLoading(false)
      }
    }

    fetchOrders()
  }, [])

  if (loading) {
    return (
      <div className="page-shell page-layout">
        <div className="panel loading-panel">Loading orders...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="page-shell page-layout">
        <div className="panel error-panel">
          <h1>Orders</h1>
          <p>{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="page-shell page-layout">
      <div className="panel wide-panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Orders</p>
            <h1>Your orders</h1>
          </div>
        </div>

        {orders.length === 0 ? (
          <div className="empty-state">
            <p>You have not placed any orders yet.</p>
          </div>
        ) : (
          <div className="orders-list">
            {orders.map((order) => (
              <Link key={order.id} to={`/orders/${order.id}`} className="order-card">
                <div className="order-card-header">
                  <strong>#{order.id}</strong>
                  <span className="status-pill">{order.status}</span>
                </div>
                <div className="order-card-meta">
                  <span>{order.restaurant_name || order.restaurant || 'Restaurant'}</span>
                  <span>{formatPrice(order.total_amount)}</span>
                </div>
                <div className="order-card-meta muted-row">
                  <span>{order.payment_status}</span>
                  <span>{formatDate(order.created_at)}</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
