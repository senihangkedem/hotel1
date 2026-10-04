import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import api from '../api/client'

function formatPrice(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '$0.00'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(numeric)
}

function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

export default function OrderDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [order, setOrder] = useState(null)
  const [bill, setBill] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchOrder = async () => {
      try {
        setLoading(true)
        setError('')
        const response = await api.get(`/orders/orders/${id}/`)
        setOrder(response.data)
        api.get('/billing/bills/', { params: { order: id } })
          .then((billResponse) => {
            const bills = Array.isArray(billResponse.data) ? billResponse.data : []
            setBill(bills[0] || null)
          })
          .catch(() => {})
      } catch (err) {
        if (err.response?.status === 403 || err.response?.status === 404) {
          setError('This order is not available to your account.')
        } else {
          setError('Unable to load this order right now.')
        }
      } finally {
        setLoading(false)
      }
    }

    fetchOrder()
  }, [id])

  if (loading) {
    return (
      <div className="page-shell page-layout">
        <div className="panel loading-panel">Loading order...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="page-shell page-layout">
        <div className="panel error-panel">
          <h1>Order unavailable</h1>
          <p>{error}</p>
          <button type="button" className="primary-button" onClick={() => navigate('/orders')}>Back to orders</button>
        </div>
      </div>
    )
  }

  if (!order) {
    return null
  }

  const restaurantLabel = order.restaurant_name
    || (typeof order.restaurant === 'object' && order.restaurant?.name ? order.restaurant.name : null)
    || (order.restaurant ? `Restaurant #${order.restaurant}` : 'Restaurant')

  const tableLabel =
    (typeof order.table === 'object' && order.table?.table_number !== undefined)
      ? `Table ${order.table.table_number}`
      : order.table
        ? `Table ${order.table}`
        : 'Not assigned'

  return (
    <div className="page-shell page-layout">
      <div className="panel wide-panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Order</p>
            <h1>#{order.id}</h1>
          </div>
          <Link to="/orders" className="secondary-button button-link">Back to orders</Link>
        </div>

        <div className="order-detail-grid">
          <div className="detail-card">
            <h2>Summary</h2>
            <div className="detail-row"><span>Restaurant</span><strong>{restaurantLabel}</strong></div>
            <div className="detail-row"><span>Table</span><strong>{tableLabel}</strong></div>
            <div className="detail-row"><span>Status</span><strong>{order.status}</strong></div>
            <div className="detail-row"><span>Payment</span><strong>{order.payment_status}</strong></div>
            <div className="detail-row"><span>Total</span><strong>{formatPrice(order.total_amount)}</strong></div>
            <div className="detail-row"><span>Created</span><strong>{formatDate(order.created_at)}</strong></div>
          </div>

          <div className="detail-card">
            <h2>Customer details</h2>
            <div className="detail-row"><span>Name</span><strong>{order.customer_name || 'Guest'}</strong></div>
            <div className="detail-row"><span>Phone</span><strong>{order.customer_phone || '—'}</strong></div>
            <div className="detail-row"><span>Notes</span><strong>{order.notes || '—'}</strong></div>
          </div>
        </div>

        {bill ? (
          <div className="detail-card customer-bill-summary">
            <div className="section-header">
              <h2>Bill</h2>
              <Link to={`/billing/${bill.id}/receipt`} className="secondary-button button-link small-button">View receipt</Link>
            </div>
            <div className="detail-row"><span>Payment status</span><strong>{bill.payment_status}</strong></div>
            <div className="detail-row"><span>Bill total</span><strong>{formatPrice(bill.total_amount)}</strong></div>
          </div>
        ) : null}

        <div className="detail-card">
          <h2>Items</h2>
          <div className="checkout-items">
            {order.items?.map((item) => (
              <div key={item.id} className="checkout-item">
                <div>
                  <strong>{item.menu_item_name || item.menu_item || 'Menu item'}</strong>
                  <span>{item.quantity} x {formatPrice(item.unit_price || 0)}</span>
                </div>
                <strong>{formatPrice(item.subtotal || Number(item.unit_price || 0) * Number(item.quantity || 0))}</strong>
              </div>
            )) || <p>No items available.</p>}
          </div>
        </div>
      </div>
    </div>
  )
}
