import { useEffect, useMemo, useState } from 'react'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

const PERIODS = [
  { value: 'today', label: 'Today' },
  { value: 'yesterday', label: 'Yesterday' },
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
  { value: 'custom', label: 'Custom range' },
]

function formatCurrency(value, currency = 'USD') {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '$0.00'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    maximumFractionDigits: 2,
  }).format(amount)
}

function formatDay(value) {
  const date = new Date(`${value}T00:00:00`)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function requestDashboard(restaurantId, period, startDate, endDate) {
  const params = { restaurant: restaurantId, period }
  if (period === 'custom') {
    params.start = startDate
    params.end = endDate
  }
  return api.get('/analytics/dashboard/', { params })
}

export default function AnalyticsPage() {
  const { user } = useAuth()
  const [restaurants, setRestaurants] = useState([])
  const [restaurantId, setRestaurantId] = useState('')
  const [period, setPeriod] = useState('7d')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [dashboard, setDashboard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const canView = user?.is_superuser
    || user?.role === 'OWNER'
    || user?.staff_memberships?.some((membership) => membership.role === 'MANAGER')

  useEffect(() => {
    if (!canView) return undefined
    let active = true
    api.get('/restaurants/restaurants/')
      .then((response) => {
        if (!active) return
        const list = Array.isArray(response.data) ? response.data : []
        setRestaurants(list)
        if (list.length === 0) {
          setError('No restaurant is available for analytics.')
          setLoading(false)
        } else {
          setRestaurantId((current) => current || String(list[0].id))
        }
      })
      .catch((loadError) => {
        if (!active) return
        setError(loadError.response?.status === 403
          ? 'You do not have permission to view restaurant analytics.'
          : 'Unable to load restaurants.')
        setLoading(false)
      })
    return () => { active = false }
  }, [canView])

  useEffect(() => {
    if (!canView || !restaurantId || (period === 'custom' && (!startDate || !endDate))) return undefined
    let active = true
    requestDashboard(restaurantId, period, startDate, endDate)
      .then((response) => {
        if (active) {
          setDashboard(response.data)
          setError('')
        }
      })
      .catch((loadError) => {
        if (!active) return
        setDashboard(null)
        setError(loadError.response?.status === 403 || loadError.response?.status === 404
          ? 'Analytics are not available for this restaurant.'
          : Object.values(loadError.response?.data || {}).flat().join(' ') || 'Unable to load analytics.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [canView, restaurantId, period, startDate, endDate])

  const chartMax = useMemo(() => {
    const amounts = (dashboard?.revenue_trend || []).map((point) => Number(point.revenue) || 0)
    return Math.max(...amounts, 0)
  }, [dashboard])

  const changeFilter = (setter, value) => {
    setLoading(true)
    setDashboard(null)
    setError('')
    setter(value)
  }

  const retry = () => {
    if (!restaurantId || (period === 'custom' && (!startDate || !endDate))) return
    setLoading(true)
    setError('')
    requestDashboard(restaurantId, period, startDate, endDate)
      .then((response) => setDashboard(response.data))
      .catch((loadError) => setError(Object.values(loadError.response?.data || {}).flat().join(' ') || 'Unable to load analytics.'))
      .finally(() => setLoading(false))
  }

  if (!canView) {
    return (
      <div className="page-shell page-layout">
        <div className="panel error-panel">
          <h1>Analytics</h1>
          <p>Business analytics are limited to restaurant owners and managers.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="page-shell page-layout">
      <div className="panel wide-panel analytics-panel">
        <div className="section-header analytics-header">
          <div>
            <p className="eyebrow">Business</p>
            <h1>Analytics</h1>
          </div>
          <div className="analytics-filters">
            {restaurants.length > 1 ? (
              <label>
                Restaurant
                <select value={restaurantId} onChange={(event) => changeFilter(setRestaurantId, event.target.value)}>
                  {restaurants.map((restaurant) => (
                    <option key={restaurant.id} value={restaurant.id}>{restaurant.name}</option>
                  ))}
                </select>
              </label>
            ) : null}
            <label>
              Period
              <select value={period} onChange={(event) => changeFilter(setPeriod, event.target.value)}>
                {PERIODS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
          </div>
        </div>

        {period === 'custom' ? (
          <div className="analytics-custom-range">
            <label>From <input type="date" value={startDate} onChange={(event) => changeFilter(setStartDate, event.target.value)} /></label>
            <label>To <input type="date" value={endDate} onChange={(event) => changeFilter(setEndDate, event.target.value)} /></label>
          </div>
        ) : null}

        {period === 'custom' && (!startDate || !endDate) ? (
          <p className="muted-text">Choose a start and end date to load analytics.</p>
        ) : null}

        {error ? (
          <div className="analytics-error">
            <p>{error}</p>
            <button type="button" className="secondary-button small-button" onClick={retry}>Retry</button>
          </div>
        ) : null}

        {loading && !dashboard && (period !== 'custom' || (startDate && endDate)) ? (
          <div className="loading-panel">Loading analytics...</div>
        ) : null}

        {!loading && !error && dashboard && dashboard.metrics.total_orders === 0 ? (
          <div className="empty-state"><p>No order data available for this period.</p></div>
        ) : null}

        {!error && dashboard && dashboard.metrics.total_orders > 0 ? (
          <>
            <section className="analytics-metrics" aria-label="Business summary">
              <article className="analytics-metric analytics-metric-revenue">
                <span>Collected revenue</span>
                <strong>{formatCurrency(dashboard.metrics.collected_revenue, dashboard.currency)}</strong>
              </article>
              <article className="analytics-metric">
                <span>Orders</span>
                <strong>{dashboard.metrics.total_orders}</strong>
              </article>
              <article className="analytics-metric">
                <span>Average paid bill</span>
                <strong>{formatCurrency(dashboard.metrics.average_paid_bill_value, dashboard.currency)}</strong>
              </article>
            </section>

            <div className="analytics-grid">
              <section className="analytics-section analytics-revenue-section">
                <div className="analytics-section-heading">
                  <div><p className="eyebrow">Paid bills by payment date</p><h2>Revenue trend</h2></div>
                  <span>{dashboard.period.start} to {dashboard.period.end}</span>
                </div>
                {chartMax <= 0 ? (
                  <div className="analytics-no-revenue">No paid revenue recorded for this period.</div>
                ) : (
                  <div className="revenue-chart" role="img" aria-label="Collected revenue by day">
                    {dashboard.revenue_trend.map((point) => {
                      const value = Number(point.revenue) || 0
                      const height = chartMax > 0 ? Math.max((value / chartMax) * 100, value > 0 ? 3 : 0) : 0
                      return (
                        <div className="revenue-chart-column" key={point.date} title={`${point.date}: ${formatCurrency(value, dashboard.currency)}`}>
                          <span className="revenue-chart-value">{value > 0 ? formatCurrency(value, dashboard.currency) : ''}</span>
                          <div className="revenue-chart-track"><div className="revenue-chart-bar" style={{ height: `${height}%` }} /></div>
                          <span className="revenue-chart-label">{formatDay(point.date)}</span>
                        </div>
                      )
                    })}
                  </div>
                )}
              </section>

              <section className="analytics-section">
                <p className="eyebrow">All orders created in period</p>
                <h2>Order status</h2>
                <div className="analytics-status-list">
                  {dashboard.order_status_distribution.map((item) => (
                    <div className="analytics-status-row" key={item.status}>
                      <span>{item.status}</span><strong>{item.count}</strong>
                    </div>
                  ))}
                </div>
                <div className="analytics-small-stats">
                  <span>Paid orders <strong>{dashboard.metrics.paid_orders}</strong></span>
                  <span>Unpaid orders <strong>{dashboard.metrics.unpaid_orders}</strong></span>
                </div>
              </section>

              <section className="analytics-section">
                <p className="eyebrow">Non-cancelled order items</p>
                <h2>Popular items</h2>
                {dashboard.popular_items.length === 0 ? (
                  <p className="muted-text">No item sales available for this period.</p>
                ) : (
                  <div className="staff-table-wrap">
                    <table className="staff-table analytics-table">
                      <thead><tr><th>Item</th><th>Qty sold</th><th>Item revenue</th></tr></thead>
                      <tbody>
                        {dashboard.popular_items.map((item) => (
                          <tr key={item.menu_item_id}>
                            <td>{item.name}</td>
                            <td>{item.quantity_sold}</td>
                            <td>{formatCurrency(item.item_revenue, dashboard.currency)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              <section className="analytics-section">
                <p className="eyebrow">Issued in period</p>
                <h2>Payment summary</h2>
                <div className="analytics-status-row"><span>Paid bills</span><strong>{dashboard.metrics.paid_bill_count}</strong></div>
                <div className="analytics-status-row"><span>Collected</span><strong>{formatCurrency(dashboard.metrics.collected_revenue, dashboard.currency)}</strong></div>
                <div className="analytics-status-row"><span>Unpaid bills</span><strong>{dashboard.metrics.unpaid_bill_count}</strong></div>
                <div className="analytics-status-row"><span>Unpaid amount</span><strong>{formatCurrency(dashboard.metrics.unpaid_bill_amount, dashboard.currency)}</strong></div>
                <div className="analytics-payment-methods">
                  {dashboard.payment_methods.map((method) => (
                    <div className="analytics-status-row" key={method.method}>
                      <span>{method.method} ({method.count})</span>
                      <strong>{formatCurrency(method.amount, dashboard.currency)}</strong>
                    </div>
                  ))}
                </div>
              </section>

              <section className="analytics-section analytics-inventory-section">
                <p className="eyebrow">Recipe ledger</p>
                <h2>Inventory activity</h2>
                <p className="analytics-inventory-count">{dashboard.inventory.active_item_count} active inventory items</p>
                {dashboard.inventory_order_usage.length === 0 ? (
                  <p className="muted-text">No order-related stock usage recorded for this period.</p>
                ) : (
                  <div className="staff-table-wrap">
                    <table className="staff-table analytics-table">
                      <thead><tr><th>Item</th><th>Net order usage</th></tr></thead>
                      <tbody>
                        {dashboard.inventory_order_usage.map((item) => (
                          <tr key={item.inventory_item_id}><td>{item.name}</td><td>{item.quantity_used} {item.unit}</td></tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}
