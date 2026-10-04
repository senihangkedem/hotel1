import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/client'

export default function RestaurantListPage() {
  const [restaurants, setRestaurants] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchRestaurants = async () => {
      try {
        setLoading(true)
        setError('')
        const response = await api.get('/restaurants/restaurants/')
        const data = Array.isArray(response.data) ? response.data : []
        setRestaurants(data.filter((restaurant) => restaurant && restaurant.is_active !== false))
      } catch (err) {
        const message = err.response?.status === 404
          ? 'Restaurant list is not available right now.'
          : 'Unable to load restaurants right now.'
        setError(message)
      } finally {
        setLoading(false)
      }
    }

    fetchRestaurants()
  }, [])

  if (loading) {
    return (
      <div className="page-shell page-layout">
        <div className="panel loading-panel">Loading restaurants...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="page-shell page-layout">
        <div className="panel error-panel">
          <h1>Restaurants</h1>
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
            <p className="eyebrow">Browse</p>
            <h1>Restaurants</h1>
          </div>
        </div>

        {restaurants.length === 0 ? (
          <div className="empty-state">
            <p>No restaurants are available right now.</p>
          </div>
        ) : (
          <div className="restaurant-grid">
            {restaurants.map((restaurant) => (
              <div key={restaurant.id} className="restaurant-card">
                <div className="restaurant-card-image">
                  {restaurant.logo ? (
                    <img src={restaurant.logo} alt={restaurant.name} onError={(event) => {
                      event.currentTarget.style.display = 'none'
                      event.currentTarget.parentElement?.classList.add('placeholder-visible')
                    }} />
                  ) : (
                    <div className="restaurant-placeholder">Logo</div>
                  )}
                </div>
                <div className="restaurant-card-body">
                  <h3>{restaurant.name}</h3>
                  <p>{restaurant.description || 'Fresh food and great service.'}</p>
                  <div className="restaurant-meta">
                    <span>{restaurant.address || 'Address available on site'}</span>
                  </div>
                  <div className="restaurant-card-actions">
                    <Link to={`/restaurants/${restaurant.id}/menu`} className="link-like">View menu →</Link>
                    <Link to={`/restaurants/${restaurant.id}/tables`} className="secondary-button small-button button-link">Table QR</Link>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
