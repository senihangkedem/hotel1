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

export default function CartPage() {
  const { cart, cartTotal, cartItemCount, increaseQuantity, decreaseQuantity, removeFromCart, clearCart } = useCart()

  return (
    <div className="page-shell page-layout">
      <div className="panel wide-panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Review</p>
            <h1>Cart</h1>
          </div>
          {cart.length > 0 ? (
            <button type="button" className="secondary-button" onClick={clearCart}>Clear cart</button>
          ) : null}
        </div>

        {cart.length === 0 ? (
          <div className="empty-state">
            <p>Your cart is empty.</p>
          </div>
        ) : (
          <>
            <div className="cart-page-list">
              {cart.map((item) => (
                <div key={item.id} className="cart-page-item">
                  <div>
                    <h3>{item.name}</h3>
                    <p>{formatPrice(item.price)} each</p>
                  </div>

                  <div className="cart-page-controls">
                    <button type="button" onClick={() => decreaseQuantity(item.id)}>-</button>
                    <span>{item.quantity}</span>
                    <button type="button" onClick={() => increaseQuantity(item.id)}>+</button>
                  </div>

                  <div className="cart-page-total">{formatPrice(Number(item.price) * Number(item.quantity))}</div>

                  <button type="button" className="text-button" onClick={() => removeFromCart(item.id)}>
                    Remove
                  </button>
                </div>
              ))}
            </div>

            <div className="cart-summary box-summary">
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
              <Link to="/checkout" className="primary-button button-link">Proceed to checkout</Link>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
