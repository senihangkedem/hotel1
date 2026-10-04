/* eslint-disable react-hooks/set-state-in-effect */
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import MenuItemCard from '../components/MenuItemCard'
import CartDrawer from '../components/CartDrawer'
import api from '../api/client'
import { useCart } from '../context/CartContext'

const EMPTY_CART_MESSAGE = 'Your cart contains items from another restaurant.'

export default function RestaurantMenuPage() {
  const { restaurantId } = useParams()
  const { tableId } = useParams()
  const navigate = useNavigate()
  const {
    cart,
    addToCart,
    cartError,
    clearCartError,
    tableSelection,
    setTableSelection,
    clearTableSelection,
  } = useCart()

  const [restaurant, setRestaurant] = useState(null)
  const [categories, setCategories] = useState([])
  const [items, setItems] = useState([])
  const [activeTable, setActiveTable] = useState(null)
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedItem, setSelectedItem] = useState(null)
  const [selectedQuantity, setSelectedQuantity] = useState(1)
  const [cartOpen, setCartOpen] = useState(false)

  useEffect(() => {
    if (!restaurantId) {
      return
    }

    if (!tableId) {
      if (tableSelection && Number(tableSelection.restaurantId) === Number(restaurantId)) {
        setActiveTable(tableSelection)
      } else {
        clearTableSelection()
        setActiveTable(null)
      }
      return
    }

    const selectedTableId = Number(tableId)
    if (!Number.isFinite(selectedTableId)) {
      setActiveTable(null)
      return
    }

    const fetchTableSelection = async () => {
      try {
        const response = await api.get('/restaurants/tables/')
        const tables = Array.isArray(response.data) ? response.data : []
        const matchedTable = tables.find(
          (table) => Number(table.id) === selectedTableId
            && Number(table.restaurant) === Number(restaurantId)
            && table.is_active !== false,
        )

        if (matchedTable) {
          setActiveTable(matchedTable)
          setTableSelection({
            id: matchedTable.id,
            restaurantId: Number(matchedTable.restaurant),
            tableNumber: matchedTable.table_number,
            restaurantName: restaurant?.name || null,
          })
          return
        }

        setActiveTable(null)
        clearTableSelection()
      } catch {
        setActiveTable(null)
        clearTableSelection()
      }
    }

    fetchTableSelection()
  }, [restaurantId, tableId, restaurant?.name, setTableSelection, clearTableSelection, tableSelection])

  useEffect(() => {
    const fetchRestaurantData = async () => {
      try {
        setLoading(true)
        setError('')

        const [restaurantResponse, categoriesResponse, itemsResponse] = await Promise.all([
          api.get('/restaurants/restaurants/'),
          api.get('/menu/categories/'),
          api.get('/menu/items/'),
        ])

        const restaurantList = Array.isArray(restaurantResponse.data) ? restaurantResponse.data : []
        const selectedRestaurant = restaurantList.find((entry) => Number(entry.id) === Number(restaurantId))

        if (!selectedRestaurant) {
          setError('This restaurant is not available.')
          setRestaurant(null)
          setCategories([])
          setItems([])
          return
        }

        const categoryList = Array.isArray(categoriesResponse.data) ? categoriesResponse.data : []
        const itemList = Array.isArray(itemsResponse.data) ? itemsResponse.data : []

        const filteredCategories = categoryList.filter(
          (category) => Number(category.restaurant) === Number(restaurantId) && category.is_active !== false,
        )
        const filteredItems = itemList.filter(
          (item) => Number(item.restaurant) === Number(restaurantId),
        )

        setRestaurant(selectedRestaurant)
        setCategories(filteredCategories)
        setItems(filteredItems)
      } catch (err) {
        const message = err.response?.status === 401
          ? 'Please log in again to continue.'
          : err.response?.status === 403
            ? 'You do not have access to this restaurant.'
            : 'Unable to load the menu right now.'
        setError(message)
      } finally {
        setLoading(false)
      }
    }

    fetchRestaurantData()
  }, [restaurantId])

  const visibleItems = useMemo(() => {
    if (selectedCategory === 'all') return items
    return items.filter((item) => Number(item.category) === Number(selectedCategory))
  }, [items, selectedCategory])

  const handleAddToCart = (item) => {
    if (!item?.is_available) {
      setSelectedItem(item)
      return
    }

    const result = addToCart(item, selectedQuantity)
    if (result.added) {
      setSelectedItem(null)
      setSelectedQuantity(1)
      setCartOpen(true)
      return
    }

    if (result.reason === 'restaurant_mismatch') {
      setSelectedItem(item)
    }
  }

  const confirmReplaceCart = () => {
    const activeItem = selectedItem
    if (!activeItem) return

    addToCart(activeItem, selectedQuantity, { replaceExisting: true })
    setSelectedItem(null)
    setSelectedQuantity(1)
    setCartOpen(true)
  }

  const closeModal = () => {
    setSelectedItem(null)
    setSelectedQuantity(1)
    clearCartError()
  }

  const restaurantName = restaurant?.name || 'Restaurant'

  const selectedTableLabel = activeTable ? `Table ${activeTable.table_number ?? activeTable.tableNumber ?? activeTable.id}` : 'No table selected'

  if (loading) {
    return (
      <div className="page-shell page-layout">
        <div className="panel loading-panel">Loading menu...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="page-shell page-layout">
        <div className="panel error-panel">
          <h1>{restaurantName}</h1>
          <p>{error}</p>
          <button type="button" className="primary-button" onClick={() => navigate('/restaurants')}>Back to restaurants</button>
        </div>
      </div>
    )
  }

  return (
    <div className="page-shell page-layout">
      <div className="panel wide-panel menu-panel">
        <div className="section-header restaurant-header">
          <div>
            <p className="eyebrow">Menu</p>
            <h1>{restaurantName}</h1>
            <p className="restaurant-description">{restaurant?.description || 'A welcoming place to enjoy your meal.'}</p>
            {activeTable ? (
              <p className="restaurant-table-badge">Dining at {selectedTableLabel}</p>
            ) : null}
          </div>

          <button type="button" className="primary-button" onClick={() => setCartOpen(true)}>
            Cart ({cart.length})
          </button>
        </div>

        <div className="category-tabs">
          <button
            type="button"
            className={selectedCategory === 'all' ? 'category-tab active' : 'category-tab'}
            onClick={() => setSelectedCategory('all')}
          >
            All
          </button>
          {categories.map((category) => (
            <button
              key={category.id}
              type="button"
              className={selectedCategory === String(category.id) ? 'category-tab active' : 'category-tab'}
              onClick={() => setSelectedCategory(String(category.id))}
            >
              {category.name}
            </button>
          ))}
        </div>

        {visibleItems.length === 0 ? (
          <div className="empty-state">
            <p>No items are available in this category yet.</p>
          </div>
        ) : (
          <div className="menu-grid">
            {visibleItems.map((item) => (
              <MenuItemCard
                key={item.id}
                item={item}
                onSelect={() => setSelectedItem(item)}
                canAdd={item.is_available}
              />
            ))}
          </div>
        )}
      </div>

      <CartDrawer open={cartOpen} onClose={() => setCartOpen(false)} />

      {selectedItem ? (
        <div className="modal-backdrop" onClick={closeModal}>
          <div className="modal-card" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h2>{selectedItem.name}</h2>
              <button type="button" className="ghost-button" onClick={closeModal}>Close</button>
            </div>

            <div className="modal-body">
              {selectedItem.image ? (
                <img src={selectedItem.image} alt={selectedItem.name} className="modal-image" onError={(event) => {
                  event.currentTarget.style.display = 'none'
                }} />
              ) : (
                <div className="modal-placeholder">No image</div>
              )}

              <p>{selectedItem.description || 'No description available.'}</p>
              <div className="detail-row">
                <strong>Price:</strong>
                <span>{new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Number(selectedItem.price) || 0)}</span>
              </div>
              <div className="detail-row">
                <strong>Status:</strong>
                <span className={selectedItem.is_available ? 'status-text available' : 'status-text unavailable'}>
                  {selectedItem.is_available ? 'Available' : 'Unavailable'}
                </span>
              </div>

              <div className="quantity-row">
                <label htmlFor="quantity">Quantity</label>
                <input
                  id="quantity"
                  type="number"
                  min="1"
                  max="99"
                  value={selectedQuantity}
                  onChange={(event) => setSelectedQuantity(Math.max(1, Number(event.target.value) || 1))}
                />
              </div>
            </div>

            {cartError ? (
              <div className="form-error cart-warning">{EMPTY_CART_MESSAGE}</div>
            ) : null}

            <div className="modal-actions">
              {cartError ? (
                <>
                  <button type="button" className="secondary-button" onClick={closeModal}>Cancel</button>
                  <button type="button" className="primary-button" onClick={confirmReplaceCart}>Clear cart and add</button>
                </>
              ) : (
                <button
                  type="button"
                  className="primary-button"
                  disabled={!selectedItem.is_available}
                  onClick={() => handleAddToCart(selectedItem)}
                >
                  Add to Cart
                </button>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
