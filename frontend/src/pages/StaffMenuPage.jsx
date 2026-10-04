import { useEffect, useMemo, useState } from 'react'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

function getErrorMessage(error) {
  const data = error.response?.data
  if (typeof data === 'string') return data
  if (data && typeof data === 'object') return Object.values(data).flat().join(' ')
  return 'Unable to complete the recipe request.'
}

export default function StaffMenuPage() {
  const { user } = useAuth()
  const [restaurants, setRestaurants] = useState([])
  const [restaurantId, setRestaurantId] = useState('')
  const [menuItems, setMenuItems] = useState([])
  const [inventoryItems, setInventoryItems] = useState([])
  const [recipes, setRecipes] = useState([])
  const [drafts, setDrafts] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [savingId, setSavingId] = useState(null)

  const canManage = user?.is_superuser
    || user?.role === 'OWNER'
    || user?.staff_memberships?.some((membership) => membership.role === 'MANAGER')

  useEffect(() => {
    if (!canManage) return undefined
    let active = true

    Promise.all([
      api.get('/restaurants/restaurants/'),
      api.get('/menu/items/'),
      api.get('/inventory/items/'),
      api.get('/menu/recipes/'),
    ])
      .then(([restaurantResponse, menuResponse, inventoryResponse, recipeResponse]) => {
        if (!active) return
        const restaurantList = Array.isArray(restaurantResponse.data) ? restaurantResponse.data : []
        const recipeList = Array.isArray(recipeResponse.data) ? recipeResponse.data : []
        setRestaurants(restaurantList)
        setRestaurantId((current) => current || String(restaurantList[0]?.id || ''))
        setMenuItems(Array.isArray(menuResponse.data) ? menuResponse.data : [])
        setInventoryItems(Array.isArray(inventoryResponse.data) ? inventoryResponse.data : [])
        setRecipes(recipeList)
        setDrafts(Object.fromEntries(recipeList.map((recipe) => [recipe.id, {
          quantity_required: recipe.quantity_required,
        }])))
      })
      .catch((loadError) => {
        if (active) setError(getErrorMessage(loadError))
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => { active = false }
  }, [canManage])

  const visibleMenuItems = useMemo(
    () => menuItems.filter((item) => Number(item.restaurant) === Number(restaurantId)),
    [menuItems, restaurantId],
  )
  const visibleInventoryItems = useMemo(
    () => inventoryItems.filter(
      (item) => Number(item.restaurant) === Number(restaurantId) && item.is_active,
    ),
    [inventoryItems, restaurantId],
  )
  const recipesByMenuItem = useMemo(() => recipes.reduce((grouped, recipe) => {
    const key = String(recipe.menu_item)
    grouped[key] = [...(grouped[key] || []), recipe]
    return grouped
  }, {}), [recipes])

  const reloadRecipes = async () => {
    const response = await api.get('/menu/recipes/')
    const recipeList = Array.isArray(response.data) ? response.data : []
    setRecipes(recipeList)
    setDrafts(Object.fromEntries(recipeList.map((recipe) => [recipe.id, {
      quantity_required: recipe.quantity_required,
    }])))
  }

  const addIngredient = async (event, menuItem) => {
    event.preventDefault()
    const draft = drafts[`new-${menuItem.id}`] || {}
    const selectedInventoryItem = visibleInventoryItems.find(
      (item) => String(item.id) === String(draft.inventory_item),
    )
    if (!selectedInventoryItem) {
      setError('Choose an inventory item from this restaurant.')
      return
    }

    setSavingId(`new-${menuItem.id}`)
    setError('')
    setSuccess('')
    try {
      await api.post('/menu/recipes/', {
        menu_item: menuItem.id,
        inventory_item: selectedInventoryItem.id,
        quantity_required: draft.quantity_required,
        unit: selectedInventoryItem.unit,
      })
      await reloadRecipes()
      setSuccess(`Recipe updated for ${menuItem.name}.`)
    } catch (saveError) {
      setError(getErrorMessage(saveError))
    } finally {
      setSavingId(null)
    }
  }

  const saveRecipe = async (recipe) => {
    setSavingId(recipe.id)
    setError('')
    setSuccess('')
    try {
      await api.patch(`/menu/recipes/${recipe.id}/`, drafts[recipe.id])
      setSuccess(`Updated ${recipe.inventory_item_name}.`)
      await reloadRecipes()
    } catch (saveError) {
      setError(getErrorMessage(saveError))
    } finally {
      setSavingId(null)
    }
  }

  const removeRecipe = async (recipe) => {
    setError('')
    setSuccess('')
    try {
      await api.delete(`/menu/recipes/${recipe.id}/`)
      setRecipes((current) => current.filter((entry) => entry.id !== recipe.id))
      setSuccess(`Removed ${recipe.inventory_item_name}.`)
    } catch (removeError) {
      setError(getErrorMessage(removeError))
    }
  }

  const setDraftValue = (key, field, value) => {
    setDrafts((current) => ({
      ...current,
      [key]: { ...current[key], [field]: value },
    }))
  }

  if (!canManage) {
    return (
      <div className="page-shell page-layout">
        <div className="panel error-panel">
          <h1>Menu recipes</h1>
          <p>Recipe editing is limited to restaurant owners and managers.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="page-shell page-layout">
      <div className="panel wide-panel staff-workspace-panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Kitchen setup</p>
            <h1>Menu recipes</h1>
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

        {loading ? (
          <div className="loading-panel">Loading menu and inventory...</div>
        ) : visibleMenuItems.length === 0 ? (
          <div className="empty-state"><p>No menu items are available for this restaurant.</p></div>
        ) : (
          <div className="recipe-menu-list">
            {visibleMenuItems.map((menuItem) => {
              const itemRecipes = recipesByMenuItem[String(menuItem.id)] || []
              const newDraft = drafts[`new-${menuItem.id}`] || {}

              return (
                <section className="recipe-menu-section" key={menuItem.id}>
                  <div className="recipe-menu-heading">
                    <div>
                      <p className="eyebrow">Menu item</p>
                      <h2>{menuItem.name}</h2>
                    </div>
                    <span>{menuItem.is_available ? 'Available' : 'Unavailable'}</span>
                  </div>

                  {itemRecipes.length > 0 ? (
                    <div className="recipe-lines">
                      {itemRecipes.map((recipe) => (
                        <div className="recipe-line" key={recipe.id}>
                          <strong>{recipe.inventory_item_name}</strong>
                          <span className="recipe-unit-label">{recipe.unit}</span>
                          <input
                            aria-label={`Quantity of ${recipe.inventory_item_name} per ${menuItem.name}`}
                            type="number"
                            min="0.000001"
                            step="0.000001"
                            value={drafts[recipe.id]?.quantity_required ?? recipe.quantity_required}
                            onChange={(event) => setDraftValue(recipe.id, 'quantity_required', event.target.value)}
                          />
                          <button type="button" className="secondary-button small-button" disabled={savingId === recipe.id} onClick={() => saveRecipe(recipe)}>
                            Save
                          </button>
                          <button type="button" className="text-button" onClick={() => removeRecipe(recipe)}>
                            Remove
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="muted-text">No ingredients are linked to this menu item.</p>
                  )}

                  {visibleInventoryItems.length > 0 ? (
                    <form className="recipe-add-row" onSubmit={(event) => addIngredient(event, menuItem)}>
                      <label>
                        Ingredient
                        <select
                          value={newDraft.inventory_item || ''}
                          onChange={(event) => setDraftValue(`new-${menuItem.id}`, 'inventory_item', event.target.value)}
                          required
                        >
                          <option value="" disabled>Select stock item</option>
                          {visibleInventoryItems.map((item) => (
                            <option key={item.id} value={item.id}>{item.name} ({item.unit})</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Quantity per item
                        <input
                          type="number"
                          min="0.000001"
                          step="0.000001"
                          value={newDraft.quantity_required || ''}
                          onChange={(event) => setDraftValue(`new-${menuItem.id}`, 'quantity_required', event.target.value)}
                          required
                        />
                      </label>
                      <button type="submit" className="primary-button small-button" disabled={savingId === `new-${menuItem.id}`}>
                        Add ingredient
                      </button>
                    </form>
                  ) : (
                    <p className="muted-text">Add inventory items before building this recipe.</p>
                  )}
                </section>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}