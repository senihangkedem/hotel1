import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import QRCode from 'react-qr-code'
import api from '../api/client'

export default function RestaurantTablePage() {
  const { restaurantId } = useParams()
  const [restaurant, setRestaurant] = useState(null)
  const [tables, setTables] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchRestaurantTables = async () => {
      if (!restaurantId) {
        setError('Restaurant details are unavailable.')
        setLoading(false)
        return
      }

      try {
        setLoading(true)
        setError('')

        const [restaurantResponse, tablesResponse] = await Promise.all([
          api.get('/restaurants/restaurants/'),
          api.get('/restaurants/tables/'),
        ])

        const restaurants = Array.isArray(restaurantResponse.data) ? restaurantResponse.data : []
        const allTables = Array.isArray(tablesResponse.data) ? tablesResponse.data : []
        const selectedRestaurant = restaurants.find(
          (item) => Number(item.id) === Number(restaurantId),
        )

        if (!selectedRestaurant) {
          setRestaurant(null)
          setTables([])
          setError('This restaurant is not available.')
          return
        }

        setRestaurant(selectedRestaurant)
        setTables(
          allTables.filter(
            (table) => Number(table.restaurant) === Number(restaurantId) && table.is_active !== false,
          ),
        )
      } catch (err) {
        const message = err.response?.status === 403
          ? 'You do not have access to this restaurant.'
          : 'Unable to load table QR codes right now.'
        setError(message)
      } finally {
        setLoading(false)
      }
    }

    fetchRestaurantTables()
  }, [restaurantId])

  if (loading) {
    return (
      <div className="page-shell page-layout">
        <div className="panel loading-panel">Loading table QR codes...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="page-shell page-layout">
        <div className="panel error-panel">
          <h1>{restaurant?.name || 'Restaurant tables'}</h1>
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
            <p className="eyebrow">Table QR</p>
            <h1>{restaurant?.name || 'Restaurant tables'}</h1>
          </div>
        </div>

        {tables.length === 0 ? (
          <div className="empty-state">
            <p>No active tables are available for this restaurant yet.</p>
          </div>
        ) : (
          <div className="table-qr-grid">
            {tables.map((table) => {
              const qrValue = `${window.location.origin}/restaurants/${restaurantId}/menu/${table.id}`

              return (
                <div key={table.id} className="table-qr-card">
                  <div className="qr-code-wrap">
                    <QRCode value={qrValue} size={160} />
                  </div>

                  <div className="table-qr-meta">
                    <strong>Table {table.table_number}</strong>
                    <span>Capacity: {table.capacity}</span>
                  </div>

                  <a
                    href={qrValue}
                    target="_blank"
                    rel="noreferrer"
                    className="secondary-button small-button button-link"
                  >
                    Open menu link
                  </a>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}