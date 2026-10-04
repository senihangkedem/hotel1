function formatPrice(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return 'N/A'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(numeric)
}

export default function MenuItemCard({ item, onSelect, isSelected = false, canAdd = true }) {
  const imageUrl = item?.image
  const hasImage = Boolean(imageUrl)

  return (
    <button
      type="button"
      className={`menu-item-card ${isSelected ? 'selected' : ''} ${!canAdd ? 'unavailable' : ''}`}
      onClick={() => onSelect(item)}
      disabled={!canAdd && !isSelected}
      aria-label={item?.name ? `View ${item.name}` : 'Menu item'}
    >
      <div className="menu-item-image-wrap">
        {hasImage ? (
          <img
            src={imageUrl}
            alt={item?.name || 'Menu item'}
            className="menu-item-image"
            onError={(event) => {
              event.currentTarget.style.display = 'none'
              event.currentTarget.parentElement?.classList.add('placeholder-visible')
            }}
          />
        ) : null}
        {!hasImage ? <div className="menu-item-placeholder">No image</div> : null}
        {!item?.is_available ? <span className="availability-pill unavailable">Unavailable</span> : null}
      </div>

      <div className="menu-item-body">
        <div className="menu-item-header">
          <h3>{item?.name || 'Unnamed item'}</h3>
          <span>{formatPrice(item?.price)}</span>
        </div>

        <p>{item?.description || 'No description available.'}</p>

        <div className="menu-item-footer">
          <span className={`status-text ${item?.is_available ? 'available' : 'unavailable'}`}>
            {item?.is_available ? 'Available' : 'Currently unavailable'}
          </span>
          <span className="card-action">View details</span>
        </div>
      </div>
    </button>
  )
}
