import { useEffect, useMemo, useState } from 'react'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

const UNIT_OPTIONS = ['kg', 'g', 'litre', 'ml', 'piece']
const MOVEMENT_OPTIONS = ['IN', 'OUT', 'ADJUSTMENT']

function getErrorMessage(error) {
  const data = error.response?.data
  if (typeof data === 'string') return data
  if (data && typeof data === 'object') return Object.values(data).flat().join(' ')
  return 'Unable to complete the inventory request.'
}

function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

export default function InventoryPage() {
  const { user } = useAuth()
  const [restaurants, setRestaurants] = useState([])
  const [restaurantId, setRestaurantId] = useState('')
  const [items, setItems] = useState([])
  const [transactions, setTransactions] = useState([])
  const [itemForm, setItemForm] = useState({ name: '', unit: 'kg', starting_quantity: '' })
  const [movementForm, setMovementForm] = useState({ inventory_item: '', transaction_type: 'IN', quantity: '' })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const canManage = user?.is_superuser
    || user?.role === 'OWNER'
    || user?.staff_memberships?.some((membership) => membership.role === 'MANAGER')

  useEffect(() => {
    if (!canManage) return undefined
    let active = true
    Promise.all([
      api.get('/restaurants/restaurants/'),
      api.get('/inventory/items/'),
      api.get('/inventory/transactions/'),
    ])
      .then(([restaurantResponse, itemResponse, transactionResponse]) => {
        if (!active) return
        const restaurantList = Array.isArray(restaurantResponse.data) ? restaurantResponse.data : []
        const itemList = Array.isArray(itemResponse.data) ? itemResponse.data : []
        setRestaurants(restaurantList)
        setRestaurantId((current) => current || String(restaurantList[0]?.id || ''))
        setItems(itemList)
        setTransactions(Array.isArray(transactionResponse.data) ? transactionResponse.data : [])
        setMovementForm((current) => ({
          ...current,
          inventory_item: current.inventory_item || String(itemList[0]?.id || ''),
        }))
      })
      .catch((loadError) => {
        if (active) setError(getErrorMessage(loadError))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [canManage])

  const visibleItems = useMemo(
    () => items.filter((item) => Number(item.restaurant) === Number(restaurantId)),
    [items, restaurantId],
  )
  const visibleTransactions = useMemo(() => {
    const itemIds = new Set(visibleItems.map((item) => item.id))
    return transactions.filter((transaction) => itemIds.has(transaction.inventory_item))
  }, [transactions, visibleItems])

  const reloadInventory = async () => {
    const [itemResponse, transactionResponse] = await Promise.all([
      api.get('/inventory/items/'),
      api.get('/inventory/transactions/'),
    ])
    setItems(Array.isArray(itemResponse.data) ? itemResponse.data : [])
    setTransactions(Array.isArray(transactionResponse.data) ? transactionResponse.data : [])
  }

  const createItem = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      await api.post('/inventory/items/', {
        restaurant: Number(restaurantId),
        name: itemForm.name,
        unit: itemForm.unit,
        starting_quantity: itemForm.starting_quantity || '0',
      })
      setItemForm({ name: '', unit: 'kg', starting_quantity: '' })
      setSuccess('Inventory item added.')
      await reloadInventory()
    } catch (saveError) {
      setError(getErrorMessage(saveError))
    } finally {
      setSaving(false)
    }
  }

  const createMovement = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      await api.post('/inventory/transactions/', {
        inventory_item: Number(movementForm.inventory_item),
        transaction_type: movementForm.transaction_type,
        quantity: movementForm.quantity,
      })
      setMovementForm((current) => ({ ...current, quantity: '' }))
      setSuccess('Stock movement recorded.')
      await reloadInventory()
    } catch (saveError) {
      setError(getErrorMessage(saveError))
    } finally {
      setSaving(false)
    }
  }

  if (!canManage) {
    return (
      <div className="page-shell page-layout">
        <div className="panel error-panel">
          <h1>Inventory</h1>
          <p>Inventory management is limited to restaurant owners and managers.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="page-shell page-layout">
      <div className="panel wide-panel staff-workspace-panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Stock control</p>
            <h1>Inventory</h1>
          </div>
          {restaurants.length > 1 ? (
            <label className="workspace-restaurant-select">
              Restaurant
              <select value={restaurantId} onChange={(event) => setRestaurantId(event.target.value)}>
                {restaurants.map((restaurant) => (
                  <option key={restaurant.id} value={restaurant.id}>{restaurant.name}</option>
                ))}
              </select>
            </label>
          ) : null}
        </div>

        {error ? <div className="form-error">{error}</div> : null}
        {success ? <div className="success-banner">{success}</div> : null}

        <div className="inventory-forms">
          <form className="inventory-form" onSubmit={createItem}>
            <h2>Add stock item</h2>
            <label>
              Name
              <input value={itemForm.name} onChange={(event) => setItemForm({ ...itemForm, name: event.target.value })} required />
            </label>
            <label>
              Unit
              <select value={itemForm.unit} onChange={(event) => setItemForm({ ...itemForm, unit: event.target.value })}>
                {UNIT_OPTIONS.map((unit) => <option key={unit} value={unit}>{unit}</option>)}
              </select>
            </label>
            <label>
              Opening quantity
              <input type="number" min="0" step="0.000001" value={itemForm.starting_quantity} onChange={(event) => setItemForm({ ...itemForm, starting_quantity: event.target.value })} />
            </label>
            <button type="submit" className="primary-button" disabled={saving || !restaurantId}>Add item</button>
          </form>

          <form className="inventory-form" onSubmit={createMovement}>
            <h2>Record stock movement</h2>
            <label>
              Item
              <select value={movementForm.inventory_item} onChange={(event) => setMovementForm({ ...movementForm, inventory_item: event.target.value })} required>
                {visibleItems.map((item) => <option key={item.id} value={item.id}>{item.name} ({item.unit})</option>)}
              </select>
            </label>
            <label>
              Type
              <select value={movementForm.transaction_type} onChange={(event) => setMovementForm({ ...movementForm, transaction_type: event.target.value })}>
                {MOVEMENT_OPTIONS.map((type) => <option key={type} value={type}>{type}</option>)}
              </select>
            </label>
            <label>
              Quantity {movementForm.transaction_type === 'ADJUSTMENT' ? '(signed)' : '(positive)'}
              <input type="number" step="0.000001" min={movementForm.transaction_type === 'ADJUSTMENT' ? undefined : '0.000001'} value={movementForm.quantity} onChange={(event) => setMovementForm({ ...movementForm, quantity: event.target.value })} required />
            </label>
            <button type="submit" className="primary-button" disabled={saving || visibleItems.length === 0}>Record movement</button>
          </form>
        </div>

        <section className="inventory-section">
          <h2>On hand</h2>
          {loading ? <div className="loading-panel">Loading inventory...</div> : visibleItems.length === 0 ? (
            <div className="empty-state"><p>No inventory items for this restaurant.</p></div>
          ) : (
            <div className="inventory-item-list">
              {visibleItems.map((item) => (
                <div className="inventory-item-row" key={item.id}>
                  <strong>{item.name}</strong>
                  <span>{item.quantity_on_hand} {item.unit}</span>
                  <span className={item.is_active ? 'status-text available' : 'status-text unavailable'}>
                    {item.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="inventory-section">
          <h2>Stock ledger</h2>
          <div className="staff-table-wrap">
            <table className="staff-table inventory-ledger-table">
              <thead>
                <tr>
                  <th>Item</th>
                  <th>Quantity</th>
                  <th>Type</th>
                  <th>Source</th>
                  <th>Order</th>
                  <th>User</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {visibleTransactions.map((transaction) => (
                  <tr key={transaction.id}>
                    <td>{transaction.inventory_item_name}</td>
                    <td>{transaction.quantity} {transaction.inventory_unit}</td>
                    <td>{transaction.transaction_type}</td>
                    <td>{transaction.source}</td>
                    <td>{transaction.order_id ? `#${transaction.order_id}` : '—'}</td>
                    <td>{transaction.username || 'System'}</td>
                    <td>{formatDate(transaction.created_at)}</td>
                  </tr>
                ))}
                {!loading && visibleTransactions.length === 0 ? (
                  <tr><td colSpan="7" className="muted-text">No stock movements have been recorded.</td></tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  )
}