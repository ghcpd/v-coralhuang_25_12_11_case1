API migration: compatibility analysis and regression test plan

1) API call evidence (examples)

- /api/v1/orders (legacy)
Request:
GET /api/v1/orders?userId=123
Headers: X-Client: legacy-web, Accept: application/json

Response (200):
{
  "orderId": "ORD-123",
  "status": "PAID",
  "totalPrice": 199.99,
  "items": [
    { "productName": "Pen", "qty": 3 }
  ]
}

- /api/v2/orders (without includeItems)
Request:
GET /api/v2/orders?userId=123
Headers: X-Client: legacy-web, Accept: application/json

Response (200):
{
  "orderId": "ORD-123",
  "state": "PAID",
  "amount": 199.99
  // note: lineItems omitted because includeItems not provided
}

Breaking: "items" does not exist; legacy clients that access items[0] will get runtime errors.

- /api/v2/orders?includeItems=true
Request:
GET /api/v2/orders?userId=789&includeItems=true
Headers: X-Client: legacy-web, Accept: application/json

Response (200):
{
  "orderId": "ORD-789",
  "state": "SHIPPED",
  "amount": 59.5,
  "lineItems": [
    { "name": "Pen", "quantity": 3 },
    { "name": "Notebook", "quantity": 2 }
  ]
}

Breaking: fields are renamed (state/amount/lineItems) and inner item keys differ (name/quantity).

- /api/v1/orders when deprecated
Request:
GET /api/v1/orders?userId=999
Headers: X-Client: infra-monitor

Response (410):
{
  "error": "API_VERSION_DEPRECATED",
  "message": "Please migrate to /api/v2/orders"
}

Note: Monitoring that treats any non-200 as outage will alarm.

2) Schema comparison (v1 vs v2)

- v1 schema (representative):
  orderId: string (required)
  status: enum {PAID, CANCELLED, SHIPPED}
  totalPrice: number
  items: array of {
    productName: string
    qty: integer
  }

- v2 schema (representative):
  orderId: string (required)
  state: enum that includes old values + new values (e.g., FULFILLED)
  amount: number
  lineItems: array of {
    name: string
    quantity: integer
  }  // may be omitted when includeItems not requested

Compatibility-impacting diffs:
- Renames: status→state, totalPrice→amount, items→lineItems
- lineItems omitted when includeItems=false or absent → items missing
- New enum values (FULFILLED) may not map to legacy enums
- v1 deprecated and may return 410

Concrete mapping/fallback rules (compatibility layer recommendations):
- Always provide v1 shapes to legacy clients: map state->status, amount->totalPrice, and lineItems->items with name->productName and quantity->qty.
- If lineItems omitted, include items: [] (preferably include a header that items were omitted instead of returning 410/omitting key).
- Unknown state values: map to a safe fallback (e.g., UNKNOWN) and emit an X-Compatibility-Warning header with the original state.
- For /api/v1/orders keep returning HTTP 200 with a deprecation header during rollout; avoid returning 410 until consumers are migrated.

3) Client impact assessment (concise)

- Missing items → TypeError / NullPointer when client code does items[0] or items.forEach; root cause: lineItems omitted when includeItems not provided.
  Example failure: "TypeError: Cannot read properties of undefined (reading '0') at renderOrderSummary"

- Renamed fields → KeyError / missing metrics in analytics because code reads 'status' and 'totalPrice' that are absent.
  Example failure: "KeyError: 'status' in aggregator.py:27"

- New state values → enum mapping exceptions (Java: IllegalArgumentException: No enum constant OrderStatus.FULFILLED)

- Deprecated v1 endpoint returns 410 → monitoring marks an outage.
  Example log: "CRITICAL: orders API down; expected HTTP 200 from /api/v1/orders, got 410"

4) Regression test coverage (compact plan)

Each test case: input (endpoint+query+headers), expected output or compatibility mapping, failure conditions.

A. Field renames validation
- Input: v2 response with amount/state/lineItems
- Expected: compatibility layer exposes status=state, totalPrice=amount, items mapped
- Failure: missing mapped keys or incorrect mapping

B. includeItems behavior
- Input: v2 without includeItems
- Expected: compatibility layer ensures items key exists (array, possibly empty); detection flags missing items
- Failure: items key missing; legacy client indexing causes error

C. Item-list safety in legacy clients
- Input: v2 with no lineItems
- Expected: items: [] present; code avoids index access without checking length; detector warns about empty list semantics
- Failure: index errors in clients

D. Analytics mapping
- Input: v2 response only has amount/state
- Expected: aggregator sees status and totalPrice via mapping; totals computed correctly
- Failure: aggregator metrics drop or KeyError occurs

E. Enum compatibility
- Input: v2 response with state: FULFILLED
- Expected: compatibility layer maps unknown state to safe fallback and records the original value
- Failure: enum parsing exception and dropped rows

F. Deprecated v1 endpoint handling
- Input: /api/v1/orders returns 410 + API_VERSION_DEPRECATED body
- Expected: monitoring config treats 410 as deprecation; compatibility notice and no outage alarm
- Failure: monitoring generates outage alert

5) Automated tests provided
- run_tests.py: simple runner that loads error_case.json fixtures and executes checks implemented in tests/test_api_migration.py.
- Tests included exercise mapping, detection, and safety checks including the new state value FULFILLED.

6) What passing answers mean
- All tests PASS: basic compatibility rules (mapping keys, including items key, and deprecation detection) are satisfied by a compatibility layer or updated clients.
- Any FAIL indicates a concrete regression that will cause crashes, metric loss, or false monitoring alerts.

Notes:
- The included scripts are minimal and intentionally dependency-free so they are easily runnable in CI or locally.
- For production, extend tests to exercise headers, content negotiation, and end-to-end calls against staging API endpoints or a contract-test harness (Pact-like).
