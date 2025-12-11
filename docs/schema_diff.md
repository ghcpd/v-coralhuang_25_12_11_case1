Schema diff: v1 → v2

- Top-level renames and type changes:
  - `status` (string) → renamed to `state` (string). v2 may introduce new values (e.g., `FULFILLED`).
  - `totalPrice` (number) → renamed to `amount` (number).
  - `items` (array of { productName, qty }) → renamed and reshaped to `lineItems` (array of { name, quantity }).

- Behavioral changes:
  - v2 adds query parameter `includeItems` to control whether item-level details are returned; default or omitted -> no `lineItems` returned.
  - v1 endpoint `/api/v1/orders` is deprecated: may return HTTP 410 and `API_VERSION_DEPRECATED` error.

- Breaking vs non-breaking changes:
  - Breaking:
    - Field renames (`status` -> `state`, `totalPrice` -> `amount`) are breaking because name-based access will fail.
    - Item name/shape change: `items` -> `lineItems` with different nested property names is breaking for code that accesses `items[0].productName`.
    - Omission of `lineItems` by default is breaking for code that assumes `items` always exists (null-pointer).
    - New `state` values (e.g., `FULFILLED`) break strict enum mapping (e.g., `OrderStatus.valueOf(state)`).
    - `/api/v1/orders` returning 410 may be misinterpreted as an outage.
  - Non-breaking:
    - `orderId` remains same; these changes are additive or renames.

- Suggested compatibility/mapping rules:
  - If `state` present but `status` not, map `state` -> `status` using a mapping table: {PAID -> PAID, CANCELLED -> CANCELLED, SHIPPED -> SHIPPED}. Unknown `state` values should map to a safe fallback (e.g., `UNKNOWN`), and be logged.
  - If `amount` present but `totalPrice` not, copy `amount` -> `totalPrice`.
  - If `lineItems` present, adapt to `items` by mapping each {name, quantity} -> {productName: name, qty: quantity}; if `lineItems` omitted, ensure older clients receive empty `items` array to avoid null access.
  - If `/api/v1/orders` returns 410, treat as deprecation — do not trigger an outage alert.
  - For enum changes, ensure the mapping layer handles unknown states gracefully: log and map to `UNKNOWN` or `PAID/CANCELLED/SHIPPED` where feasible.
