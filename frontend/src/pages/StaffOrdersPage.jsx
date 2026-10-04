import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import api, { getWebSocketToken } from '../api/client'
import { useAuth } from '../context/AuthContext'

const STAFF_ORDER_ROLES = new Set(['MANAGER', 'KITCHEN', 'WAITER'])
const STATUS_OPTIONS = ['PENDING', 'CONFIRMED', 'PREPARING', 'READY', 'SERVED', 'COMPLETED', 'CANCELLED']
const PAYMENT_OPTIONS = ['UNPAID', 'PAID']
const defaultWsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
const defaultWsBaseUrl = `${defaultWsProtocol}//${window.location.host}`
const configuredWsUrl = import.meta.env.VITE_WS_BASE_URL || defaultWsBaseUrl
const WS_BASE_URL = configuredWsUrl
  .replace(/^https:/, 'wss:')
  .replace(/^http:/, 'ws:')
  .replace(/\/$/, '')

async function requestStaffOrderData() {
  return Promise.all([
    api.get('/orders/orders/'),
    api.get('/restaurants/restaurants/'),
    api.get('/restaurants/tables/'),
  ])
}

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

export default function StaffOrdersPage() {
  const { user } = useAuth()
  const [orders, setOrders] = useState([])
  const [restaurants, setRestaurants] = useState([])
  const [tables, setTables] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [paymentFilter, setPaymentFilter] = useState('ALL')
  const [search, setSearch] = useState('')
  const [connectionStatus, setConnectionStatus] = useState('offline')
  const socketMapRef = useRef(new Map())
  const reconnectTimersRef = useRef(new Map())
  const reconnectAttemptsRef = useRef(new Map())
  const connectSocketsRef = useRef(null)
  const connectionGenerationRef = useRef(0)
  const pendingConnectionsRef = useRef(new Set())

  const membershipRoles = new Set((user?.staff_memberships || []).map((membership) => membership.role))
  const isAuthorized = user?.is_superuser || ['OWNER', 'SUPERUSER'].includes(user?.role)
    || [...membershipRoles].some((role) => STAFF_ORDER_ROLES.has(role))

  const fetchData = useCallback(async () => {
    try {
      const [ordersResponse, restaurantsResponse, tablesResponse] = await requestStaffOrderData()

      setOrders(Array.isArray(ordersResponse.data) ? ordersResponse.data : [])
      setRestaurants(Array.isArray(restaurantsResponse.data) ? restaurantsResponse.data : [])
      setTables(Array.isArray(tablesResponse.data) ? tablesResponse.data : [])
    } catch (err) {
      const message = err.response?.status === 401
        ? 'Your session has expired. Please log in again.'
        : err.response?.status === 403
          ? 'You do not have permission to view staff orders.'
          : 'Unable to load orders right now.'
      setError(message)
    } finally {
      setLoading(false)
    }
  }, [])

  const mergeOrder = useCallback((nextOrder) => {
    if (!nextOrder || !nextOrder.id) {
      return
    }

    setOrders((currentOrders) => {
      const existingIndex = currentOrders.findIndex((order) => String(order.id) === String(nextOrder.id))
      if (existingIndex >= 0) {
        const nextOrders = [...currentOrders]
        nextOrders[existingIndex] = { ...nextOrders[existingIndex], ...nextOrder }
        return nextOrders
      }

      return [nextOrder, ...currentOrders]
    })
  }, [])

  const handleRealtimeEvent = useCallback(async (payload) => {
    if (!payload || !payload.order_id) {
      return
    }

    try {
      const response = await api.get(`/orders/orders/${payload.order_id}/`)
      mergeOrder(response.data)
    } catch {
      setError('Live order update received, but the latest data could not be loaded.')
    }
  }, [mergeOrder])

  const disconnectSockets = useCallback(() => {
    connectionGenerationRef.current += 1
    pendingConnectionsRef.current.clear()
    reconnectTimersRef.current.forEach((timer) => clearTimeout(timer))
    reconnectTimersRef.current.clear()
    reconnectAttemptsRef.current.clear()

    socketMapRef.current.forEach((socket) => {
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close()
      }
    })
    socketMapRef.current.clear()
  }, [])

  const connectSockets = useCallback(async () => {
    if (!isAuthorized || !Array.isArray(restaurants) || restaurants.length === 0) {
      return
    }
    const generation = connectionGenerationRef.current

    const scheduleReconnect = (restaurantId) => {
      const existingTimer = reconnectTimersRef.current.get(restaurantId)
      if (existingTimer) {
        clearTimeout(existingTimer)
      }

      const attempt = reconnectAttemptsRef.current.get(restaurantId) || 0
      const delay = Math.min(1000 * (2 ** attempt), 30000)
      reconnectAttemptsRef.current.set(restaurantId, attempt + 1)
      setConnectionStatus('reconnecting')
      reconnectTimersRef.current.set(restaurantId, setTimeout(() => {
        reconnectTimersRef.current.delete(restaurantId)
        if (isAuthorized) {
          void connectSocketsRef.current?.()
        }
      }, delay))
    }

    for (const restaurant of restaurants) {
      const restaurantId = String(restaurant.id)
      if (socketMapRef.current.has(restaurantId) || pendingConnectionsRef.current.has(restaurantId)) {
        continue
      }

      pendingConnectionsRef.current.add(restaurantId)
      try {
        const token = await getWebSocketToken()
        if (generation !== connectionGenerationRef.current || !isAuthorized) {
          return
        }
        if (socketMapRef.current.has(restaurantId)) {
          continue
        }
        if (!token) {
          scheduleReconnect(restaurantId)
          continue
        }

        const socket = new WebSocket(`${WS_BASE_URL}/ws/restaurants/${restaurantId}/?token=${encodeURIComponent(token)}`)

        socket.onopen = () => {
          reconnectAttemptsRef.current.delete(restaurantId)
          setConnectionStatus('connected')
          api.get('/orders/orders/')
            .then((response) => {
              setOrders(Array.isArray(response.data) ? response.data : [])
            })
            .catch(() => {
              setError('Live connection restored, but orders could not be refreshed.')
            })
        }

        socket.onmessage = (event) => {
          try {
            const payload = JSON.parse(event.data)
            if (payload?.event) {
              void handleRealtimeEvent(payload)
            }
          } catch {
            setError('A live order event was received in an unexpected format.')
          }
        }

        socket.onerror = () => {
          setConnectionStatus('reconnecting')
        }

        socket.onclose = () => {
          if (socketMapRef.current.get(restaurantId) !== socket) {
            return
          }
          socketMapRef.current.delete(restaurantId)
          scheduleReconnect(restaurantId)
        }

        socketMapRef.current.set(restaurantId, socket)
      } catch {
        if (generation === connectionGenerationRef.current && isAuthorized) {
          scheduleReconnect(restaurantId)
        }
      } finally {
        pendingConnectionsRef.current.delete(restaurantId)
      }
    }
  }, [handleRealtimeEvent, isAuthorized, restaurants])

  useEffect(() => {
    connectSocketsRef.current = connectSockets

    if (!isAuthorized) {
      disconnectSockets()
      return
    }

    let active = true
    requestStaffOrderData()
      .then(([ordersResponse, restaurantsResponse, tablesResponse]) => {
        if (!active) return
        setOrders(Array.isArray(ordersResponse.data) ? ordersResponse.data : [])
        setRestaurants(Array.isArray(restaurantsResponse.data) ? restaurantsResponse.data : [])
        setTables(Array.isArray(tablesResponse.data) ? tablesResponse.data : [])
      })
      .catch((err) => {
        if (!active) return
        const message = err.response?.status === 401
          ? 'Your session has expired. Please log in again.'
          : err.response?.status === 403
            ? 'You do not have permission to view staff orders.'
            : 'Unable to load orders right now.'
        setError(message)
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    void connectSockets()

    return () => {
      active = false
      disconnectSockets()
    }
  }, [connectSockets, disconnectSockets, isAuthorized])

  const restaurantMap = useMemo(
    () => Object.fromEntries(restaurants.map((restaurant) => [String(restaurant.id), restaurant])),
    [restaurants],
  )

  const tableMap = useMemo(
    () => Object.fromEntries(tables.map((table) => [String(table.id), table])),
    [tables],
  )

  const filteredOrders = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase()

    return orders.filter((order) => {
      const matchesStatus = statusFilter === 'ALL' || order.status === statusFilter
      const matchesPayment = paymentFilter === 'ALL' || order.payment_status === paymentFilter
      const matchesSearch = !normalizedSearch
        || String(order.id).includes(normalizedSearch)
        || (order.customer_name || '').toLowerCase().includes(normalizedSearch)
        || (order.customer_phone || '').toLowerCase().includes(normalizedSearch)

      return matchesStatus && matchesPayment && matchesSearch
    })
  }, [orders, paymentFilter, search, statusFilter])

  if (!user) {
    return null
  }

  if (!isAuthorized) {
    return (
      <div className="page-shell page-layout">
        <div className="panel error-panel">
          <h1>Staff orders</h1>
          <p>You do not have permission to view staff orders.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="page-shell page-layout">
      <div className="panel wide-panel staff-dashboard-panel">
        <div className="section-header staff-header">
          <div>
            <p className="eyebrow">Staff</p>
            <h1>Staff Orders</h1>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span className="connection-status" style={{ fontSize: '0.8rem', opacity: 0.85 }}>
              {connectionStatus === 'connected' ? 'Live updates: connected' : connectionStatus === 'reconnecting' ? 'Live updates: reconnecting' : 'Live updates: offline'}
            </span>
            <button
              type="button"
              className="secondary-button"
              onClick={() => {
                setLoading(true)
                setError('')
                fetchData()
              }}
              disabled={loading}
            >
              {loading ? 'Loading...' : 'Refresh'}
            </button>
          </div>
        </div>

        <div className="staff-filters">
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="ALL">All statuses</option>
            {STATUS_OPTIONS.map((status) => (
              <option key={status} value={status}>{status}</option>
            ))}
          </select>

          <select value={paymentFilter} onChange={(event) => setPaymentFilter(event.target.value)}>
            <option value="ALL">All payments</option>
            {PAYMENT_OPTIONS.map((status) => (
              <option key={status} value={status}>{status}</option>
            ))}
          </select>

          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search order #, name, phone"
          />
        </div>

        {error ? (
          <div className="form-error">{error}</div>
        ) : null}

        {loading ? (
          <div className="loading-panel">Loading staff orders...</div>
        ) : filteredOrders.length === 0 ? (
          <div className="empty-state">
            <p>No orders match the current filter.</p>
          </div>
        ) : (
          <div className="staff-order-list">
            {filteredOrders.map((order) => {
              const restaurant = restaurantMap[String(order.restaurant)]
              const table = tableMap[String(order.table)]
              const itemCount = Array.isArray(order.items) ? order.items.length : 0
              const tableLabel = table ? `Table ${table.table_number}` : order.table ? `Table ${order.table}` : 'No table'

              return (
                <div key={order.id} className="staff-order-card">
                  <div className="staff-order-main">
                    <div className="staff-order-header">
                      <strong>Order #{order.id}</strong>
                      <span className="status-pill">{order.status}</span>
                    </div>

                    <div className="staff-order-meta">
                      <span>{restaurant?.name || `Restaurant ${order.restaurant}`}</span>
                      <span>{tableLabel}</span>
                    </div>

                    <div className="staff-order-meta">
                      <span>{order.customer_name || 'Guest customer'}</span>
                      <span>{order.customer_phone || 'No phone'}</span>
                    </div>

                    <div className="staff-order-meta">
                      <span>{itemCount} items</span>
                      <span>{formatPrice(order.total_amount)}</span>
                    </div>

                    <div className="staff-order-meta muted-row">
                      <span>{order.payment_status}</span>
                      <span>{formatDate(order.created_at)}</span>
                    </div>
                  </div>

                  <div className="staff-order-actions">
                    <Link to={`/staff/orders/${order.id}`} className="primary-button button-link small-button">
                      View
                    </Link>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
