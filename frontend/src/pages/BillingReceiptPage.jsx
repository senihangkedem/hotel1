import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import api from '../api/client'

function formatAmount(value) {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '$0.00'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount)
}

function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

export default function BillingReceiptPage() {
  const { billId } = useParams()
  const [bill, setBill] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    api.get(`/billing/bills/${billId}/`)
      .then((response) => {
        if (active) setBill(response.data)
      })
      .catch((requestError) => {
        if (!active) return
        setError(requestError.response?.status === 403 || requestError.response?.status === 404
          ? 'This receipt is not available to your account.'
          : 'Unable to load this receipt.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [billId])

  if (loading) {
    return <div className="page-shell page-layout"><div className="panel loading-panel">Loading receipt...</div></div>
  }

  if (error || !bill) {
    return (
      <div className="page-shell page-layout">
        <div className="panel error-panel">
          <h1>Receipt unavailable</h1>
          <p>{error || 'This receipt is unavailable.'}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="page-shell page-layout receipt-page-shell">
      <div className="receipt-toolbar no-print">
        <Link to={`/orders/${bill.order}`} className="secondary-button button-link">Back to order</Link>
        <button type="button" className="primary-button" onClick={() => window.print()}>Print receipt</button>
      </div>

      <article className="receipt-sheet">
        <header className="receipt-header">
          <h1>{bill.restaurant_name}</h1>
          {bill.restaurant_address ? <p>{bill.restaurant_address}</p> : null}
          {bill.restaurant_phone ? <p>{bill.restaurant_phone}</p> : null}
        </header>

        <div className="receipt-meta">
          <span>Bill #{bill.id}</span>
          <span>Order #{bill.order}</span>
          {bill.order_table_number ? <span>Table {bill.order_table_number}</span> : null}
          <span>Issued {formatDate(bill.issued_at)}</span>
        </div>

        <div className="receipt-lines">
          <div className="receipt-line receipt-line-heading">
            <strong>Item</strong><strong>Qty</strong><strong>Price</strong><strong>Amount</strong>
          </div>
          {bill.lines.map((line) => (
            <div className="receipt-line" key={line.id}>
              <span>{line.item_name}</span>
              <span>{line.quantity}</span>
              <span>{formatAmount(line.unit_price)}</span>
              <span>{formatAmount(line.subtotal)}</span>
            </div>
          ))}
        </div>

        <div className="receipt-totals">
          <div><span>Subtotal</span><strong>{formatAmount(bill.subtotal)}</strong></div>
          <div><span>Discount</span><strong>-{formatAmount(bill.discount_amount)}</strong></div>
          <div><span>Tax ({bill.tax_rate}%)</span><strong>{formatAmount(bill.tax_amount)}</strong></div>
          <div><span>Service charge ({bill.service_charge_rate}%)</span><strong>{formatAmount(bill.service_charge_amount)}</strong></div>
          <div className="receipt-total"><span>Total</span><strong>{formatAmount(bill.total_amount)}</strong></div>
        </div>

        <footer className="receipt-footer">
          <p>Payment: {bill.payment_method || '—'}</p>
          <p>Status: {bill.payment_status}</p>
          {bill.paid_at ? <p>Paid {formatDate(bill.paid_at)}</p> : null}
            {bill.paid_by_name ? <p>Received by {bill.paid_by_name}</p> : null}
          <p>Thank you!</p>
        </footer>
      </article>
    </div>
  )
}
