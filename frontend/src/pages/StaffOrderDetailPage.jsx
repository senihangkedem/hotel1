import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

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

export default function StaffOrderDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [order, setOrder] = useState(null)
  const [bill, setBill] = useState(null)
  const [loading, setLoading] = useState(true)
  const [billLoading, setBillLoading] = useState(true)
  const [transitioning, setTransitioning] = useState(false)
  const [billingBusy, setBillingBusy] = useState(false)
  const [error, setError] = useState('')
  const [transitionError, setTransitionError] = useState('')
  const [billingError, setBillingError] = useState('')
  const [discountType, setDiscountType] = useState('NONE')
  const [discountValue, setDiscountValue] = useState('0.00')
  const [paymentMethod, setPaymentMethod] = useState('CASH')

  const canTransition = user?.is_superuser
    || user?.role === 'OWNER'
    || user?.staff_memberships?.some((membership) => membership.role === 'MANAGER')
  const canManageBilling = canTransition
  const canViewBilling = canManageBilling
    || user?.staff_memberships?.some((membership) => membership.role === 'WAITER')

  const handleTransition = async (nextStatus) => {
    setTransitioning(true)
    setTransitionError('')
    try {
      const response = await api.post(`/orders/orders/${id}/transition/`, { status: nextStatus })
      setOrder(response.data)
    } catch (transitionRequestError) {
      const data = transitionRequestError.response?.data
      setTransitionError(typeof data === 'string' ? data : Object.values(data || {}).flat().join(' ') || 'Unable to update this order.')
    } finally {
      setTransitioning(false)
    }
  }

  const nextStatuses = {
    PENDING: ['CONFIRMED', 'CANCELLED'],
    CONFIRMED: ['PREPARING', 'CANCELLED'],
    PREPARING: ['READY', 'CANCELLED'],
    READY: ['SERVED'],
    SERVED: ['COMPLETED'],
  }

  const createBill = async () => {
    setBillingBusy(true)
    setBillingError('')
    try {
      const response = await api.post('/billing/bills/', {
        order: Number(id),
        discount_type: discountType,
        discount_value: discountType === 'NONE' ? '0.00' : discountValue,
      })
      setBill(response.data)
      setDiscountType(response.data.discount_type)
      setDiscountValue(response.data.discount_value)
    } catch (billError) {
      const data = billError.response?.data
      setBillingError(typeof data === 'string' ? data : Object.values(data || {}).flat().join(' ') || 'Unable to generate the bill.')
    } finally {
      setBillingBusy(false)
    }
  }

  const updateBillDiscount = async () => {
    if (!bill) return
    setBillingBusy(true)
    setBillingError('')
    try {
      const response = await api.patch(`/billing/bills/${bill.id}/`, {
        discount_type: discountType,
        discount_value: discountType === 'NONE' ? '0.00' : discountValue,
      })
      setBill(response.data)
    } catch (billError) {
      const data = billError.response?.data
      setBillingError(typeof data === 'string' ? data : Object.values(data || {}).flat().join(' ') || 'Unable to update the discount.')
    } finally {
      setBillingBusy(false)
    }
  }

  const markBillPaid = async () => {
    if (!bill) return
    setBillingBusy(true)
    setBillingError('')
    try {
      const response = await api.post(`/billing/bills/${bill.id}/pay/`, { payment_method: paymentMethod })
      setBill(response.data)
      setOrder((current) => ({ ...current, payment_status: response.data.payment_status }))
    } catch (paymentError) {
      const data = paymentError.response?.data
      setBillingError(typeof data === 'string' ? data : Object.values(data || {}).flat().join(' ') || 'Unable to record payment.')
    } finally {
      setBillingBusy(false)
    }
  }

  useEffect(() => {
    let active = true
    api.get(`/orders/orders/${id}/`)
      .then((response) => {
        if (!active) return
        setOrder(response.data)
        if (!canViewBilling) {
          setBillLoading(false)
          return
        }
        api.get('/billing/bills/', { params: { order: id } })
          .then((billResponse) => {
            if (!active) return
            const currentBill = Array.isArray(billResponse.data) ? billResponse.data[0] : null
            setBill(currentBill || null)
            if (currentBill) {
              setDiscountType(currentBill.discount_type)
              setDiscountValue(currentBill.discount_value)
            }
          })
          .catch((billError) => {
            if (active && billError.response?.status !== 404) {
              const data = billError.response?.data
              setBillingError(typeof data === 'string' ? data : Object.values(data || {}).flat().join(' ') || 'Unable to load billing details.')
            }
          })
          .finally(() => {
            if (active) setBillLoading(false)
          })
      })
      .catch((err) => {
        if (!active) return
        if (err.response?.status === 401) {
          setError('Your session has expired. Please log in again.')
        } else if (err.response?.status === 403) {
          setError('You do not have permission to view this order.')
        } else if (err.response?.status === 404) {
          setError('This order is unavailable.')
        } else {
          setError('Unable to load this order right now.')
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => { active = false }
  }, [id, canViewBilling])

  if (loading) {
    return (
      <div className="page-shell page-layout">
        <div className="panel loading-panel">Loading order...</div>
      </div>
    )
  }

  if (error && !order) {
    return (
      <div className="page-shell page-layout">
        <div className="panel error-panel">
          <h1>Order unavailable</h1>
          <p>{error}</p>
          <button type="button" className="primary-button" onClick={() => navigate('/staff/orders')}>Back to staff orders</button>
        </div>
      </div>
    )
  }

  if (!order) {
    return null
  }

  return (
    <div className="page-shell page-layout">
      <div className="panel wide-panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Staff</p>
            <h1>Order #{order.id}</h1>
          </div>
          <Link to="/staff/orders" className="secondary-button button-link">Back to dashboard</Link>
        </div>

        {error ? <div className="form-error">{error}</div> : null}

        <div className="detail-section-grid">
          <div className="detail-card">
            <h2>Order details</h2>
            <div className="detail-row"><span>Restaurant</span><strong>{order.restaurant_name || order.restaurant || 'Restaurant'}</strong></div>
            <div className="detail-row"><span>Table</span><strong>{order.table ? `Table ${order.table}` : 'Not assigned'}</strong></div>
            <div className="detail-row"><span>Customer name</span><strong>{order.customer_name || 'Guest'}</strong></div>
            <div className="detail-row"><span>Customer phone</span><strong>{order.customer_phone || '—'}</strong></div>
            <div className="detail-row"><span>Payment</span><strong>{order.payment_status}</strong></div>
            <div className="detail-row"><span>Total</span><strong>{formatPrice(order.total_amount)}</strong></div>
            <div className="detail-row"><span>Created</span><strong>{formatDate(order.created_at)}</strong></div>
            <div className="detail-row"><span>Updated</span><strong>{formatDate(order.updated_at)}</strong></div>
          </div>

          <div className="detail-card">
            <h2>Order status</h2>
            <div className="detail-row"><span>Status</span><strong>{order.status}</strong></div>
            <div className="detail-row"><span>Notes</span><strong>{order.notes || '—'}</strong></div>
            {canTransition && nextStatuses[order.status]?.length ? (
              <div className="order-transition-actions">
                {nextStatuses[order.status].map((nextStatus) => (
                  <button
                    key={nextStatus}
                    type="button"
                    className={nextStatus === 'CANCELLED' ? 'secondary-button' : 'primary-button'}
                    disabled={transitioning}
                    onClick={() => handleTransition(nextStatus)}
                  >
                    {transitioning ? 'Updating...' : `Mark ${nextStatus.toLowerCase()}`}
                  </button>
                ))}
              </div>
            ) : null}
            {transitionError ? <div className="form-error">{transitionError}</div> : null}
            {order.status === 'CONFIRMED' ? (
              <p className="muted-text">Starting preparation deducts recipe quantities from inventory.</p>
            ) : null}
          </div>
        </div>

        {canViewBilling ? (
          <section className="detail-card billing-order-panel">
            <div className="section-header">
              <div>
                <p className="eyebrow">Point of sale</p>
                <h2>Billing</h2>
              </div>
              {bill ? (
                <Link to={`/billing/${bill.id}/receipt`} className="secondary-button button-link small-button">
                  View receipt
                </Link>
              ) : null}
            </div>

            {billingError ? <div className="form-error">{billingError}</div> : null}
            {billLoading ? (
              <p className="muted-text">Checking bill...</p>
            ) : bill ? (
              <>
                <div className="detail-row"><span>Subtotal</span><strong>{formatPrice(bill.subtotal)}</strong></div>
                <div className="detail-row"><span>Discount</span><strong>-{formatPrice(bill.discount_amount)}</strong></div>
                <div className="detail-row"><span>Tax ({bill.tax_rate}%)</span><strong>{formatPrice(bill.tax_amount)}</strong></div>
                <div className="detail-row"><span>Service charge ({bill.service_charge_rate}%)</span><strong>{formatPrice(bill.service_charge_amount)}</strong></div>
                <div className="detail-row"><span>Total</span><strong>{formatPrice(bill.total_amount)}</strong></div>
                <div className="detail-row"><span>Payment</span><strong>{bill.payment_status}{bill.payment_method ? ` · ${bill.payment_method}` : ''}</strong></div>

                {bill.payment_status === 'UNPAID' && canManageBilling ? (
                  <>
                    <div className="billing-edit-row">
                      <label>
                        Discount
                        <select value={discountType} onChange={(event) => setDiscountType(event.target.value)}>
                          <option value="NONE">None</option>
                          <option value="PERCENTAGE">Percentage</option>
                          <option value="FIXED">Fixed amount</option>
                        </select>
                      </label>
                      {discountType !== 'NONE' ? (
                        <label>
                          {discountType === 'PERCENTAGE' ? 'Percent' : 'Amount'}
                          <input type="number" min="0" step="0.01" max={discountType === 'PERCENTAGE' ? '100' : undefined} value={discountValue} onChange={(event) => setDiscountValue(event.target.value)} />
                        </label>
                      ) : null}
                      <button type="button" className="secondary-button small-button" disabled={billingBusy} onClick={updateBillDiscount}>
                        Save discount
                      </button>
                    </div>
                    <div className="billing-edit-row">
                      <label>
                        Payment method
                        <select value={paymentMethod} onChange={(event) => setPaymentMethod(event.target.value)}>
                          <option value="CASH">Cash</option>
                          <option value="CARD">Card</option>
                          <option value="BANK_TRANSFER">Bank transfer</option>
                          <option value="QR">QR</option>
                          <option value="OTHER">Other</option>
                        </select>
                      </label>
                      <button type="button" className="primary-button small-button" disabled={billingBusy} onClick={markBillPaid}>
                        {billingBusy ? 'Recording...' : 'Mark paid'}
                      </button>
                    </div>
                  </>
                ) : null}
              </>
            ) : canManageBilling ? (
              <>
                <p className="muted-text">Tax and service charge use the restaurant's configured rates. Billing does not change inventory.</p>
                <div className="billing-edit-row">
                  <label>
                    Discount
                    <select value={discountType} onChange={(event) => setDiscountType(event.target.value)}>
                      <option value="NONE">None</option>
                      <option value="PERCENTAGE">Percentage</option>
                      <option value="FIXED">Fixed amount</option>
                    </select>
                  </label>
                  {discountType !== 'NONE' ? (
                    <label>
                      {discountType === 'PERCENTAGE' ? 'Percent' : 'Amount'}
                      <input type="number" min="0" step="0.01" max={discountType === 'PERCENTAGE' ? '100' : undefined} value={discountValue} onChange={(event) => setDiscountValue(event.target.value)} />
                    </label>
                  ) : null}
                  <button type="button" className="primary-button small-button" disabled={billingBusy} onClick={createBill}>
                    {billingBusy ? 'Generating...' : 'Generate bill'}
                  </button>
                </div>
              </>
            ) : (
              <p className="muted-text">No bill has been issued for this order.</p>
            )}
          </section>
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
