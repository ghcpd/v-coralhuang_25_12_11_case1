Schema Comparison — v1 vs v2

Old schema (v1)
- orderId: string
- status: enum {PAID, CANCELLED, SHIPPED}
- totalPrice: number
- items: [ { productName: string, qty: integer } ]  // assumed present and non-empty by clients

New schema (v2)
- orderId: string
- state: enum {PAID, CANCELLED, SHIPPED, FULFILLED, ...}
- amount: number
- lineItems: [ { name: string, quantity: integer } ]  // optional; present only when includeItems=true
- Query: includeItems (default false) controls whether lineItems are returned
- /api/v1: may return 410 with API_VERSION_DEPRECATED (deprecation metadata)

Breaking differences
- Renames: status → state; totalPrice → amount
- Structural rename + optionality: items(...) → lineItems(...); lineItems optional and omitted when includeItems not provided
- Added enum values (e.g., FULFILLED)
- v1 deprecation behavior (non-200 response)

Compatibility mapping rules (concrete)
1) Field aliases
- status = response.get("status") or response.get("state")
- totalPrice = response.get("totalPrice") or response.get("amount")

2) Items mapping
- If lineItems present: items = lineItems.map(li => ({ productName: li.name, qty: li.quantity }))
- Else: items = []  // MUST be present (not undefined/null) for legacy clients

3) Enum mapping
- Map known new states to legacy equivalents when semantics allow (e.g., FULFILLED → SHIPPED if shipping semantics match). If mapping isn't possible, set status="UNKNOWN" or include a stateLegacy/stateNormalized field and log for migration telemetry.

4) Deprecation handling
- For the transition period, keep /api/v1 responding 200 with an X-API-Deprecated: true header or a deprecation object in the body. If returning 410, communicate with monitoring to treat it as planned deprecation.

Notes: These rules are intended for a short-term compatibility layer. Encourage consumer updates to v2 semantics as a medium-term goal.