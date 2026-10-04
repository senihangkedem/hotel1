import { Link } from 'react-router-dom'
import { useCart } from '../context/CartContext'

function formatPrice(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '$0.00'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(numeric)
}

export default function CartDrawer({ open, onClose }) {
  const { cart, cartTotal, cartItemCount, increaseQuantity, decreaseQuantity, removeFromCart, clearCart } = useCart()

  if (!open) return null

  return (
    <div className="cart-overlay" onClick={onClose}>
      <aside className="cart-panel" onClick={(event) => event.stopPropagation()}>
        <div className="cart-header">
          <h2>Cart</h2>
          <button type="button" className="ghost-button" onClick={onClose}>Close</button>
        </div>

        {cart.length === 0 ? (
          <div className="empty-state compact">
            <p>Your cart is empty.</p>
          </div>
        ) : (
          <>
            <div className="cart-items">
              {cart.map((item) => (
                <div key={item.id} className="cart-item-row">
                  <div className="cart-item-info">
                    <strong>{item.name}</strong>
                    <span>{formatPrice(item.price)} each</span>
                  </div>

                  <div className="cart-controls">
                    <button type="button" onClick={() => decreaseQuantity(item.id)}>-</button>
                    <span>{item.quantity}</span>
                    <button type="button" onClick={() => increaseQuantity(item.id)}>+</button>
                  </div>

                  <button type="button" className="text-button" onClick={() => removeFromCart(item.id)}>
                    Remove
                  </button>
                </div>
              ))}
            </div>

            <div className="cart-summary">
              <div>
                <span>Items</span>
                <strong>{cartItemCount}</strong>
              </div>
              <div>
                <span>Subtotal</span>
                <strong>{formatPrice(cartTotal)}</strong>
              </div>
            </div>

            <div className="cart-actions">
              <button type="button" className="secondary-button" onClick={clearCart}>Clear cart</button>
              <Link to="/checkout" className="primary-button button-link">Checkout</Link>
            </div>
          </>
        )}
      </aside>
    </div>
  )
}
