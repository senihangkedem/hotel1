# Restaurant SaaS Backend API Reference

This document summarizes the current backend API as implemented for local development.

## Authentication

### 1) Obtain JWT access token
- Method: POST
- Endpoint: /api/auth/token/
- Purpose: Authenticate a user and receive a JWT pair.
- Authentication required: No
- Example request body:
  ```json
  {
    "username": "owner1",
    "password": "your-password"
  }
  ```

### 2) Refresh access token
- Method: POST
- Endpoint: /api/auth/token/refresh/
- Purpose: Refresh an expired access token.
- Authentication required: No
- Example request body:
  ```json
  {
    "refresh": "your-refresh-token"
  }
  ```

### 3) Get current user
- Method: GET
- Endpoint: /api/auth/me/
- Purpose: Return the authenticated user summary.
- Authentication required: Yes
- Response includes non-sensitive profile data and the user's active restaurant memberships (restaurant id, name, and membership role).

## Restaurants

### Restaurant list and management
- Method: GET / POST
- Endpoint: /api/restaurants/restaurants/
- Access: owners manage their own restaurants; customers can read active restaurants; active restaurant staff can read only their assigned restaurants.
- Purpose: View/create restaurants owned by the authenticated user; staff membership never grants ownership.

### Restaurant detail
- Method: GET / PATCH / DELETE
- Endpoint: /api/restaurants/restaurants/<id>/
- Allowed roles: OWNER, SUPERUSER
- Purpose: Retrieve or manage a specific restaurant owned by the current user.

### Tables
- Method: GET / POST
- Endpoint: /api/restaurants/tables/
- Access: owners and managers manage tables; customers can read active tables for QR ordering; active staff can read tables only for assigned restaurants.
- Purpose: Operate tables within restaurant membership scope.

### Table detail
- Method: GET / PATCH / DELETE
- Endpoint: /api/restaurants/tables/<id>/
- Access: owners and managers can manage categories; customers can read active categories; active staff can read categories in assigned restaurants.
- Purpose: Manage a table tied to the current owner’s restaurant.

## Menu

### Categories
- Method: GET / POST
- Endpoint: /api/menu/categories/
- Access: owners and managers can manage menu items; customers can read available items; active staff can read menu items in assigned restaurants.
- Purpose: List and create categories for the current owner’s restaurant.

### Category detail
- Method: GET / PATCH / DELETE
- Endpoint: /api/menu/categories/<id>/
- Allowed roles: OWNER, SUPERUSER

### Menu items
- Method: GET / POST
- Endpoint: /api/menu/items/
- Allowed roles: OWNER, SUPERUSER
- Purpose: List and create menu items for the current owner’s restaurant.

### Menu item detail
- Method: GET / PATCH / DELETE
- Endpoint: /api/menu/items/<id>/
- Allowed roles: OWNER, SUPERUSER

## Restaurant staff

### Staff memberships
- Methods: GET / POST / PATCH / DELETE
- Endpoint: /api/restaurants/staff/ and /api/restaurants/staff/<id>/
- Access: restaurant owners (and superusers) only; every query is scoped to restaurants they own.
- POST creates a MANAGER, KITCHEN, or WAITER membership. Passwords are write-only and hashed by Django.
- PATCH may update phone, membership role, and active status. DELETE deactivates the membership; it does not delete user or order history.
- A staff user may have memberships at multiple restaurants. Membership role and active status are restaurant-specific.
- OWNER transfer is not supported; Restaurant.owner remains immutable through the API.

Important validation rules:
- Menu items must belong to the same restaurant as the selected category.
- Price must be non-negative.
- Item names cannot be blank.
- Unavailable items cannot be added to a new order.

### Recipes
- Endpoint: `/api/menu/recipes/`
- Methods: GET / POST / PATCH / DELETE
- Access: active restaurant staff can read recipes for their restaurant; owners and managers can manage them.
- Recipe menu item and inventory item must belong to the same restaurant. Quantities must be positive and use compatible units.

## Inventory

### Inventory items
- Endpoint: `/api/inventory/items/`
- Methods: GET / POST / PATCH / DELETE
- Access: restaurant owners and active managers, scoped to their restaurants.
- Units: `kg`, `g`, `litre`, `ml`, `piece`. Inventory units cannot be changed after a recipe or transaction references the item.

### Stock ledger
- Endpoint: `/api/inventory/transactions/`
- Methods: GET / POST (manual entries only)
- Manual types: `IN`, `OUT`, `ADJUSTMENT`; order source and reversal records are server-generated and append-only.
- The API rejects any operation that would make on-hand quantity negative.

## Billing and POS

### Bills
- Endpoint: `/api/billing/bills/`
- Methods: GET / POST / PATCH (unpaid discount changes only); detail GET; payment via `POST /api/billing/bills/<id>/pay/`.
- A unique one-to-one relation allows one bill per order. Bill lines snapshot the ordered item name, quantity, unit price, and subtotal.
- Owners/managers create bills, edit discounts while unpaid, and record payment. Managers and waiters can read bills for assigned restaurants. Customers can read only bills for their own orders. Kitchen staff cannot access bills.
- Payment methods are recording labels only (`CASH`, `CARD`, `BANK_TRANSFER`, `QR`, `OTHER`); no gateway processing is performed.
- Bill payment status is authoritative for billing. A successful payment atomically marks both the bill and `Order.payment_status` as `PAID`; duplicate payments return HTTP 409.
- Paid bills cannot be edited or deleted through the API/admin. Paid orders cannot be cancelled until a refund workflow exists.

### Restaurant billing settings
- Endpoint: `GET/PATCH /api/billing/settings/<restaurant_id>/`
- Owners/managers can configure `tax_rate` and `service_charge_rate` from 0% to 100%. Both default to 0%; rates are snapshotted on bill issuance.
- Bill formula: subtotal from the server-calculated order total, less discount, plus tax and service charge calculated on the discounted subtotal. Decimal arithmetic and cent rounding are used.
- Inventory is not changed by bill creation or payment. Stage 13 inventory deduction remains tied to the order's `CONFIRMED` -> `PREPARING` transition.

## Analytics

### Staff dashboard
- Endpoint: `GET /api/analytics/dashboard/`
- Access: owners, active restaurant managers, and superusers. Customers, waiters, and kitchen staff are denied.
- Query parameters: `restaurant=<id>` (optional when one available restaurant can be selected), `period=today|yesterday|7d|30d|custom`; custom ranges require ISO `start` and `end` dates.
- Revenue is collected bill `total_amount` grouped by `paid_at`; only PAID bills for non-cancelled orders are included.
- Unpaid amount is the sum of UNPAID bill totals for non-cancelled orders, grouped by bill issue time.
- Total/status/payment order counts use order creation time. Average paid bill value is collected revenue divided by included paid bill count, or zero when there are no paid bills.
- Popular-item quantity and item revenue aggregate OrderItem quantity/subtotal for non-cancelled orders created in the range. Item revenue is pre-discount menu subtotal, not collected revenue.
- Date boundaries use Django's configured timezone (`UTC` in this project). Currency output follows the existing `USD` frontend/billing convention; there is no currency conversion.
- Inventory reporting includes active item count and net order-ledger quantities (OUT minus REVERSAL) by item and unit. No low-stock threshold or inventory cost basis exists, so low-stock counts and valuation are intentionally omitted.

## Orders

### Orders
- Method: GET / POST
- Endpoint: /api/orders/orders/
- Access: customers create and view their own orders; owners and active staff view orders scoped to owned/assigned restaurants; superusers have administrative access.
- Purpose: Create orders and view only orders accessible to the authenticated user.

### Order detail
- Method: GET / PATCH / DELETE
- Endpoint: /api/orders/orders/<id>/
- Access: customer-owned orders or orders in an owned/assigned restaurant; cross-restaurant IDs are not accessible.
- Purpose: Access a specific order only when the user or their restaurant membership authorizes it.

### Order items
- Method: GET / POST
- Endpoint: /api/orders/items/
- Allowed roles: CUSTOMER, OWNER, SUPERUSER
- Purpose: List and manage order items available to the authenticated user.

### Order item detail
- Method: GET / PATCH / DELETE
- Endpoint: /api/orders/items/<id>/
- Allowed roles: CUSTOMER, OWNER, SUPERUSER

Important validation rules:
- Orders must contain at least one item.
- Quantity must be at least 1.
- Menu items must match the selected restaurant.
- Unavailable items are rejected.
- Order pricing is server-calculated and cannot be overwritten by client input.
- The order’s table must belong to the same restaurant as the order.
- Staff status transitions use `POST /api/orders/orders/<id>/transition/` with `{ "status": "..." }`.
- Inventory is deducted atomically at `CONFIRMED` -> `PREPARING`; repeating a status is idempotent.
- Cancelling after deduction creates a positive `REVERSAL` transaction; original order `OUT` transactions are preserved.

## Notes
- The project uses JWT authentication via DRF SimpleJWT.
- Local React development is expected to run on localhost:5173.
- Local media files are served from /media/ under the backend project.
- The known migration discrepancy in user_accounts remains and is intentionally not auto-created or applied during Stage 5.
