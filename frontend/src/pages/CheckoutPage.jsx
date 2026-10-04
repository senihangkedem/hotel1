/* eslint-disable react-hooks/set-state-in-effect */
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useCart } from '../context/CartContext'

function formatPrice(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '$0.00'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(numeric)
}

function getErrorMessage(error) {
  const data = error?.response?.data

  if (!data) {
    return 'Unable to submit the order right now. Please try again.'
  }

  if (typeof data === 'string') {
    return data
  }

  const flatten = (value) => {
    if (Array.isArray(value)) {
      for (const item of value) {
        const nested = flatten(item)
        if (nested) return nested
      }
      return ''
    }

    if (typeof value === 'object') {
      for (const entry of Object.values(value)) {
        const nested = flatten(entry)
        if (nested) return nested
      }
      return ''
    }

    return String(value)
  }

  return flatten(data) || 'Unable to submit the order right now. Please try again.'
}

export default function CheckoutPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const { cart, clearCart, tableSelection } = useCart()

  const [tableOptions, setTableOptions] = useState([])
  const [selectedTableId, setSelectedTableId] = useState('')
  const [customerName, setCustomerName] = useState(user?.username || '')
  const [customerPhone, setCustomerPhone] = useState('')
  const [notes, setNotes] = useState('')
  const [loadingTables, setLoadingTables] = useState(false)
  const [tableNotice, setTableNotice] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const restaurantId = cart.length > 0 ? Number(cart[0].restaurantId) : null
  const restaurantName = cart.length > 0 ? cart[0].restaurantName || 'Restaurant' : 'Restaurant'

  const subtotal = useMemo(
    () => cart.reduce((sum, item) => sum + Number(item.price) * Number(item.quantity), 0),
    [cart],
  )

  useEffect(() => {
    if (!restaurantId) {
      setTableOptions([])
      setSelectedTableId('')
      setTableNotice('')
      return
    }

    const fetchTables = async () => {
      setLoadingTables(true)
      setTableNotice('')

      try {
        const response = await api.get('/restaurants/tables/')
        const tables = Array.isArray(response.data) ? response.data : []
        const validTables = tables.filter(
          (table) => Number(table.restaurant) === restaurantId && table.is_active !== false,
        )

        setTableOptions(validTables)

        const preferredTable = tableSelection && Number(tableSelection.restaurantId) === Number(restaurantId)
          ? validTables.find((table) => Number(table.id) === Number(tableSelection.id))
          : null

        if (preferredTable) {
          setSelectedTableId(String(preferredTable.id))
          setTableNotice('')
        } else if (validTables.length > 0) {
          setSelectedTableId(String(validTables[0].id))
          setTableNotice('')
        } else {
          setSelectedTableId('')
          setTableNotice('No active tables are currently available for this restaurant. You can continue without a table selection.')
        }
      } catch (err) {
        setTableOptions([])
        setSelectedTableId('')

        if (err.response?.status === 401 || err.response?.status === 403) {
          setTableNotice('Table selection is not available for customer checkout in this build. You can continue without a table selection and the restaurant staff can assign one.')
        } else {
          setTableNotice('Unable to load restaurant table options right now. You can continue without a table selection.')
        }
      } finally {
        setLoadingTables(false)
      }
    }

    fetchTables()
  }, [restaurantId, tableSelection])

  if (cart.length === 0) {
    return (
      <div className="page-shell page-layout">
        <div className="panel empty-state">
          <p>Your cart is empty.</p>
          <Link to="/menu" className="primary-button button-link">Return to menu</Link>
        </div>
      </div>
    )
  }

  const handleSubmit = async (event) => {
    event.preventDefault()

    if (cart.length === 0) {
      setError('Your cart is empty.')
      return
    }

    const restaurantMismatch = cart.some((item) => Number(item.restaurantId) !== Number(restaurantId))
    if (restaurantMismatch) {
      setError('Your cart contains items from more than one restaurant. Please review your cart and try again.')
      return
    }

    const payload = {
      restaurant: Number(restaurantId),
      table: selectedTableId ? Number(selectedTableId) : null,
      customer_name: customerName.trim(),
      customer_phone: customerPhone.trim(),
      notes: notes.trim(),
      items: cart.map((item) => ({
        menu_item: Number(item.id),
        quantity: Number(item.quantity),
        notes: '',
      })),
    }

    if (cart.some((item) => Number(item.quantity) <= 0)) {
      setError('Every cart item must have a valid quantity before placing an order.')
      return
    }

    try {
      setSubmitting(true)
      setError('')

      const response = await api.post('/orders/orders/', payload)
      clearCart()
      navigate(`/orders/${response.data.id}`)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="page-shell page-layout">
      <div className="panel wide-panel checkout-panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Checkout</p>
            <h1>{restaurantName}</h1>
          </div>
          <Link to="/menu" className="secondary-button button-link">Back to menu</Link>
        </div>

        <div className="checkout-layout">
          <form className="checkout-form" onSubmit={handleSubmit}>
            <div className="form-section">
              <h2>Customer details</h2>

              <label>
                Customer name
                <input
                  type="text"
                  value={customerName}
                  onChange={(event) => setCustomerName(event.target.value)}
                  placeholder="Optional guest name"
                />
              </label>

              <label>
                Customer phone
                <input
                  type="tel"
                  value={customerPhone}
                  onChange={(event) => setCustomerPhone(event.target.value)}
                  placeholder="Optional phone number"
                />
              </label>
            </div>

            <div className="form-section">
              <h2>Table</h2>

              {loadingTables ? (
                <p className="muted-text">Loading table options...</p>
              ) : tableOptions.length > 0 ? (
                <label>
                  Select a table
                  <select value={selectedTableId} onChange={(event) => setSelectedTableId(event.target.value)}>
                    {tableOptions.map((table) => (
                      <option key={table.id} value={table.id}>
                        Table {table.table_number}
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <p className="muted-text">
                  {tableNotice || 'No table was selected for this order.'}
                </p>
              )}

              {tableNotice ? <p className="muted-text">{tableNotice}</p> : null}
            </div>

            <div className="form-section">
              <h2>Order notes</h2>
              <textarea
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                rows="4"
                placeholder="Optional: No onions, please prepare quickly..."
              />
            </div>

            {error ? <div className="form-error">{error}</div> : null}

            <button type="submit" className="primary-button full-width-button" disabled={submitting}>
              {submitting ? 'Placing order...' : 'Place Order'}
            </button>
          </form>

          <aside className="checkout-summary">
            <h2>Order review</h2>

            <div className="checkout-items">
              {cart.map((item) => (
                <div key={item.id} className="checkout-item">
                  <div>
                    <strong>{item.name}</strong>
                    <span>{item.quantity} x {formatPrice(item.price)}</span>
                  </div>
                  <strong>{formatPrice(Number(item.price) * Number(item.quantity))}</strong>
                </div>
              ))}
            </div>

            <div className="checkout-totals">
              <div>
                <span>Subtotal</span>
                <strong>{formatPrice(subtotal)}</strong>
              </div>
              <div>
                <span>Total</span>
                <strong>{formatPrice(subtotal)}</strong>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </div>
  )
}
