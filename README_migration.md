API migration: /api/v1/orders → /api/v2/orders
===============================================

This repository contains a minimal mock server and automated tests that demonstrate
breaking changes introduced when migrating /api/v1/orders to /api/v2/orders.
Use this to harden clients, validate compatibility layers, and to audit migration risk.

Contents
--------
- server_and_tests.py  : Self-contained mock server + test runner (Python 3 stdlib only)

Quick summary of the change
---------------------------
v2 changes:
- New (effectively required) query parameter: includeItems (default false).
  - When includeItems is not provided or false, v2 may omit item details entirely.
- Renamed response fields:
  - status -> state
  - totalPrice -> amount
  - items(productName, qty) -> lineItems(name, quantity)
- New enum values in `state` (e.g., FULFILLED) that do not exist in v1
- v1 endpoint is marked deprecated and returns explicit metadata (HTTP 410 / API_VERSION_DEPRECATED)

1) API call evidence (examples)
-------------------------------
Example: v1 (deprecated)
Request:
  GET /api/v1/orders
Response (HTTP 410):
{
  "error": "API_VERSION_DEPRECATED",
  "message": "API v1 is deprecated. Use /api/v2/orders",
  "deprecated": true,
  "recommended": "/api/v2/orders?includeItems=true"
}

Example: v2 without includeItems
Request:
  GET /api/v2/orders
Response (HTTP 200):
{
  "orders": [
    {
      "id": "order-123",
      "createdAt": "2025-12-11T10:00:00Z",
      "state": "FULFILLED",
      "amount": 199.99
      // lineItems omitted because includeItems not provided
    },
    {
      "id": "order-124",
      "createdAt": "2025-12-10T09:30:00Z",
      "state": "SHIPPED",
      "amount": 49.5
    }
  ]
}

Example: v2 with includeItems=true
Request:
  GET /api/v2/orders?includeItems=true
Response (HTTP 200):
{
  "orders": [
    {
      "id": "order-123",
      "createdAt": "2025-12-11T10:00:00Z",
      "state": "FULFILLED",
      "amount": 199.99,
      "lineItems": [
        {"name": "Widget A", "quantity": 2},
        {"name": "Widget B", "quantity": 1}
      ]
    },
    {
      "id": "order-124",
      "createdAt": "2025-12-10T09:30:00Z",
      "state": "SHIPPED",
      "amount": 49.5,
      "lineItems": [ {"name": "Gadget", "quantity": 3} ]
    }
  ]
}

Key breaking differences (highlight)
- Missing items vs present lineItems: legacy clients assume `items` is always present and non-empty.
- Renamed fields: `status` -> `state`, `totalPrice` -> `amount` (analytics and parsers may break).
- Renamed item subfields: items.productName -> lineItems.name, items.qty -> lineItems.quantity.
- New state values (e.g., "FULFILLED") that legacy enums don't recognize.
- v1 now returns HTTP 410 (API_VERSION_DEPRECATED), which monitoring systems may treat as an outage.

2) Schema diff (concise)
------------------------
OLD (/api/v1/orders)
- orders: [
    id: string
    createdAt: string (ISO 8601)
    status: enum {PENDING, PROCESSING, SHIPPED, CANCELLED, DELIVERED}
    totalPrice: number
    items: [ { productName: string, qty: int } ]  // always present and non-empty (legacy assumption)
  ]

NEW (/api/v2/orders)
- orders: [
    id: string
    createdAt: string (ISO 8601)
    state: enum {PENDING, PROCESSING, SHIPPED, CANCELLED, DELIVERED, FULFILLED, ...} // new values added
    amount: number
    lineItems?: [ { name: string, quantity: int } ] // optional; omitted if includeItems=false
  ]

Breaking changes summary
- Field renames: status -> state, totalPrice -> amount, items -> lineItems (and nested field renames).
  Impact: existing deserializers fail to find expected keys.
- Optional/omitted items: lineItems may be omitted entirely. Impact: code that assumes items array exists and contains elements will throw.
- Enum extension: new state values (FULFILLED) cause mapping or switch statements to fall into default/error branches.
- v1 HTTP 410: monitoring or healthchecks expecting 200 will fire incident alerts.

Compatibility/mapping rules (concrete)
- Field mapping (v2 -> v1):
  - state -> status via mapping table. Example mapping: FULFILLED -> DELIVERED (best-effort); unknown -> 'UNKNOWN' or map to a fallback allowed by client.
  - amount -> totalPrice
  - lineItems -> items: name -> productName, quantity -> qty
- Missing lineItems handling:
  - Safe: return items: [] (explicit empty list) and document that clients must handle empty lists.
  - Defensive (for legacy clients that assume non-empty): synthesize a single placeholder item: {productName: '<items omitted>', qty: 0} or configure compatibility layer to include item summaries.
- Enum fallback:
  - Map known new states to closest legacy state; otherwise return a stable fallback ('UNKNOWN' or 'PROCESSING') and document it.
- Deprecation for v1:
  - Do not use 410 for rolling upgrades if many clients rely on 200; instead return 200 with a deprecation header or payload and a long deprecation window.

3) Client impact assessment (concise, mapped to changes)
--------------------------------------------------------
- Missing items / renamed items -> runtime crash
  Example: legacy client code: product = response['orders'][0]['items'][0]['productName']
  Failure: KeyError/IndexError because 'items' missing -> null-pointer or index crash.
  Root cause: v2 omits lineItems when includeItems is false and renamed field keys.

- Renamed numeric field -> analytics misattribution
  Example: analytics job reads totalPrice; v2 writes amount.
  Failure: missing revenue, zeros, or wrong aggregated metrics.
  Root cause: totalPrice was renamed to amount.

- Enum mapping failure -> incorrect business logic
  Example: switch(status) has no branch for 'FULFILLED' -> falls to default -> triggers compensation, alerts, or incorrect flow.
  Root cause: v2 adds state values not present in v1.

- Monitoring false outages -> Pager/On-call noise
  Example: healthcheck GET /api/v1/orders receives 410 -> monitoring treats as failure
  Failure: PagerDuty alerts, escalations, assumed production outage.
  Root cause: v1 returns HTTP 410 / API_VERSION_DEPRECATED.

4) Regression test coverage (compact, actionable)
-------------------------------------------------
Each test below includes: input (request), expected output, and failure condition.

T1 - v1 endpoint deprecation behavior
- Input: GET /api/v1/orders
- Expected: HTTP 410, body contains {error: 'API_VERSION_DEPRECATED'} OR (if staged) HTTP 200 + deprecation header
- Failure: Any HTTP 200 without deprecation metadata (if deprecation intended) OR 410 when clients must stay healthy without incidents

T2 - v2 field renames verification
- Input: GET /api/v2/orders
- Expected: HTTP 200; orders[].state exists; orders[].amount exists; orders[].lineItems absent when includeItems not provided
- Failure: Old fields still present (status/totalPrice/items) OR new fields missing

T3 - includeItems behavior
- Input A: GET /api/v2/orders (no includeItems)
  - Expected: lineItems omitted
  - Failure: lineItems present unexpectedly OR items still exist under old name
- Input B: GET /api/v2/orders?includeItems=true
  - Expected: lineItems present and non-empty; nested fields name and quantity
  - Failure: lineItems missing or fields mismatched

T4 - item-list safety for legacy clients
- Input: GET /api/v2/orders (no includeItems)
- Expected: Compatibility layer either provides items:[] or synthesizes a safe placeholder to avoid index errors
- Failure: legacy client that does items[0] crashes -> detect by simulating access

T5 - analytics mapping
- Input: GET /api/v2/orders
- Expected: amount present; compatibility tests map amount->totalPrice and validate aggregated totals
- Failure: analytics pipeline observes missing totalPrice or zeros

T6 - enum compatibility
- Input: GET /api/v2/orders?includeItems=true (ensures states are visible)
- Expected: All observed state values map to known legacy states via mapping table or explicit fallback
- Failure: Unknown state -> mapping error or exception in switch statements

T7 - monitoring impact
- Input: GET /api/v1/orders
- Expected: If v1 intentionally deprecated, update monitoring to treat 410 as acceptable or change healthcheck endpoint
- Failure: monitoring fires on 410

5) Automated tests (what's included)
------------------------------------
The provided server_and_tests.py performs the following automated checks (and prints a clear PASS/FAIL transcript):
- Verifies v1 returns deprecation metadata (HTTP 410 + API_VERSION_DEPRECATED)
- Validates v2 without includeItems has renamed fields and omits lineItems; simulates legacy client crash
- Validates v2 with includeItems=true exposes lineItems and demonstrates a new state value (FULFILLED) that legacy enums don't accept
- Exercises compatibility-layer mapping v2->v1, both with and without synthesizing placeholder items, and shows which prevents legacy crashes
- Checks analytics field presence and mapping feasibility
- Demonstrates monitoring false-outage when v1 returns 410

How to run the tests
--------------------
Requirements: Python 3.7+ (no external packages required)

From this repository root:
  python server_and_tests.py

Exit codes:
- 0: all tests passed
- 2: one or more tests failed (this is expected while migration issues exist)

6) What 'safe for legacy consumers' looks like
---------------------------------------------
A migration is safe when either:
- Backwards-compatibility is preserved (v1 continues to serve a stable, documented schema and 200 OK) OR
- A compatibility layer/proxy performs the precise mappings and fallbacks below:
  - state -> status mapping table covering all new state values
  - amount -> totalPrice
  - lineItems -> items mapping
  - If lineItems omitted: provide items:[] and ideally also synthesize safe placeholder items where legacy code expects non-empty arrays (or better, fix clients)
  - Avoid returning HTTP 410 for v1 while active clients still depend on it; use 200 + deprecation header for a long window

License & notes
----------------
This repository contains a minimal reproduction and test harness for engineering teams to audit migration risk.
