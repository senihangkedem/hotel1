/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

const CART_STORAGE_KEY = 'restaurant_cart'
const TABLE_STORAGE_KEY = 'restaurant_table_selection'
const CartContext = createContext(null)

function readStoredCart() {
  try {
    const raw = localStorage.getItem(CART_STORAGE_KEY)
    if (!raw) return []

    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function readStoredTableSelection() {
  try {
    const raw = localStorage.getItem(TABLE_STORAGE_KEY)
    if (!raw) return null

    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' ? parsed : null
  } catch {
    return null
  }
}

export function CartProvider({ children }) {
  const [cart, setCart] = useState(readStoredCart)
  const [cartError, setCartError] = useState('')
  const [tableSelection, setTableSelectionState] = useState(readStoredTableSelection)

  useEffect(() => {
    localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(cart))
  }, [cart])

  useEffect(() => {
    localStorage.setItem(TABLE_STORAGE_KEY, JSON.stringify(tableSelection))
  }, [tableSelection])

  const clearCartError = useCallback(() => setCartError(''), [])

  const setTableSelection = useCallback((selection) => {
    if (!selection || !selection.id) {
      setTableSelectionState(null)
      return
    }

    setTableSelectionState({
      id: Number(selection.id),
      restaurantId: Number(selection.restaurantId ?? selection.restaurant ?? selection.restaurant_id),
      tableNumber: selection.tableNumber ?? selection.table_number ?? null,
      restaurantName: selection.restaurantName ?? selection.restaurant_name ?? null,
    })
  }, [])

  const clearTableSelection = useCallback(() => setTableSelectionState(null), [])

  const getItemRestaurantId = useCallback((menuItem) => Number(menuItem.restaurant ?? menuItem.restaurantId), [])

  const addToCart = useCallback((menuItem, quantity = 1, options = {}) => {
    const requestedQuantity = Number(quantity)
    if (!menuItem || !menuItem.id || !menuItem.name || !menuItem.is_available) {
      setCartError('This item is unavailable right now.')
      return { added: false, reason: 'unavailable' }
    }

    const safeQuantity = Number.isFinite(requestedQuantity) && requestedQuantity > 0 ? Math.floor(requestedQuantity) : 1
    const newItem = {
      id: menuItem.id,
      restaurantId: getItemRestaurantId(menuItem),
      restaurantName: menuItem.restaurant_name || menuItem.restaurantName || null,
      name: menuItem.name,
      price: Number(menuItem.price) || 0,
      image: menuItem.image || null,
      quantity: safeQuantity,
    }

    if (cart.length > 0 && cart[0].restaurantId !== newItem.restaurantId) {
      if (options.replaceExisting) {
        setCart([newItem])
        setCartError('')
        return { added: true, replaced: true }
      }

      setCartError('Your cart contains items from another restaurant.')
      return { added: false, reason: 'restaurant_mismatch' }
    }

    setCartError('')
    setCart((previous) => {
      const existing = previous.find((item) => item.id === newItem.id)

      if (existing) {
        return previous.map((item) =>
          item.id === newItem.id
            ? { ...item, quantity: item.quantity + newItem.quantity }
            : item,
        )
      }

      return [...previous, newItem]
    })

    return { added: true }
  }, [cart, getItemRestaurantId])

  const updateQuantity = useCallback((itemId, nextQuantity) => {
    const safeQty = Number(nextQuantity)
    if (!Number.isFinite(safeQty) || safeQty <= 0) {
      setCart((previous) => previous.filter((item) => item.id !== itemId))
      return
    }

    setCart((previous) =>
      previous.map((item) =>
        item.id === itemId ? { ...item, quantity: safeQty } : item,
      ),
    )
  }, [])

  const increaseQuantity = useCallback((itemId) => {
    setCart((previous) =>
      previous.map((item) =>
        item.id === itemId ? { ...item, quantity: item.quantity + 1 } : item,
      ),
    )
  }, [])

  const decreaseQuantity = useCallback((itemId) => {
    setCart((previous) =>
      previous.flatMap((item) => {
        if (item.id !== itemId) return [item]
        if (item.quantity <= 1) return []
        return [{ ...item, quantity: item.quantity - 1 }]
      }),
    )
  }, [])

  const removeFromCart = useCallback((itemId) => {
    setCart((previous) => previous.filter((item) => item.id !== itemId))
  }, [])

  const clearCart = useCallback(() => {
    setCart([])
    setCartError('')
  }, [])

  const cartTotal = useMemo(
    () => cart.reduce((sum, item) => sum + Number(item.price) * Number(item.quantity), 0),
    [cart],
  )

  const cartItemCount = useMemo(
    () => cart.reduce((sum, item) => sum + Number(item.quantity), 0),
    [cart],
  )

  const value = useMemo(
    () => ({
      cart,
      cartError,
      cartTotal,
      cartItemCount,
      tableSelection,
      addToCart,
      updateQuantity,
      increaseQuantity,
      decreaseQuantity,
      removeFromCart,
      clearCart,
      clearCartError,
      setTableSelection,
      clearTableSelection,
    }),
    [addToCart, cart, cartError, cartItemCount, cartTotal, clearCart, clearCartError, clearTableSelection, decreaseQuantity, increaseQuantity, removeFromCart, setTableSelection, tableSelection, updateQuantity],
  )

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>
}

export function useCart() {
  const context = useContext(CartContext)

  if (!context) {
    throw new Error('useCart must be used within a CartProvider')
  }

  return context
}
