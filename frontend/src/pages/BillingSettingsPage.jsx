import { useEffect, useState } from 'react'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

function getErrorMessage(error) {
  const data = error.response?.data
  if (typeof data === 'string') return data
  if (data && typeof data === 'object') return Object.values(data).flat().join(' ')
  return 'Unable to update billing settings.'
}

export default function BillingSettingsPage() {
  const { user } = useAuth()
  const [restaurants, setRestaurants] = useState([])
  const [restaurantId, setRestaurantId] = useState('')
  const [rates, setRates] = useState({ tax_rate: '0.00', service_charge_rate: '0.00' })
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
    api.get('/restaurants/restaurants/')
      .then((response) => {
        if (!active) return
        const list = Array.isArray(response.data) ? response.data : []
        setRestaurants(list)
        setRestaurantId((current) => current || String(list[0]?.id || ''))
      })
      .catch((loadError) => {
        if (active) setError(getErrorMessage(loadError))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [canManage])

  useEffect(() => {
    if (!canManage || !restaurantId) return undefined
    let active = true
    api.get(`/billing/settings/${restaurantId}/`)
      .then((response) => {
        if (active) {
          setRates({
            tax_rate: response.data.tax_rate,
            service_charge_rate: response.data.service_charge_rate,
          })
        }
      })
      .catch((loadError) => {
        if (active) setError(getErrorMessage(loadError))
      })
    return () => { active = false }
  }, [canManage, restaurantId])

  const saveSettings = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      const response = await api.patch(`/billing/settings/${restaurantId}/`, rates)
      setRates({
        tax_rate: response.data.tax_rate,
        service_charge_rate: response.data.service_charge_rate,
      })
      setSuccess('Billing settings saved. Existing bills keep their issued rates.')
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
          <h1>Billing settings</h1>
          <p>Only restaurant owners and managers can configure billing rates.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="page-shell page-layout">
      <div className="panel billing-settings-panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Point of sale</p>
            <h1>Billing settings</h1>
          </div>
        </div>

        {error ? <div className="form-error">{error}</div> : null}
        {success ? <div className="success-banner">{success}</div> : null}
        {loading ? <p className="muted-text">Loading restaurants...</p> : null}

        {restaurants.length > 1 ? (
          <label className="billing-setting-field">
            Restaurant
            <select value={restaurantId} onChange={(event) => setRestaurantId(event.target.value)}>
              {restaurants.map((restaurant) => (
                <option key={restaurant.id} value={restaurant.id}>{restaurant.name}</option>
              ))}
            </select>
          </label>
        ) : restaurants.length === 1 ? (
          <p className="muted-text">{restaurants[0].name}</p>
        ) : null}

        <form className="billing-settings-form" onSubmit={saveSettings}>
          <label className="billing-setting-field">
            Tax rate (%)
            <input
              type="number"
              min="0"
              max="100"
              step="0.01"
              value={rates.tax_rate}
              onChange={(event) => setRates((current) => ({ ...current, tax_rate: event.target.value }))}
              required
            />
          </label>
          <label className="billing-setting-field">
            Service charge (%)
            <input
              type="number"
              min="0"
              max="100"
              step="0.01"
              value={rates.service_charge_rate}
              onChange={(event) => setRates((current) => ({ ...current, service_charge_rate: event.target.value }))}
              required
            />
          </label>
          <button type="submit" className="primary-button" disabled={saving || !restaurantId}>
            {saving ? 'Saving...' : 'Save rates'}
          </button>
        </form>
      </div>
    </div>
  )
}