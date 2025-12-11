Regression Test Plan

- Goals
  - Validate v2's field renames and omission behavior do not break legacy consumers.
  - Ensure clients gracefully handle missing fields/items and unknown states.
  - Verify monitoring interprets deprecation as a deprecation, not outage.

- Test cases
  1) v1 happy path
     - Input: GET /api/v1/orders?userId=123
     - Expect: 200, body contains status and totalPrice and items array with productName/qty.
     - Failure: missing fields, status code !=200.
  2) v2 without includeItems
     - Input: GET /api/v2/orders?userId=123
     - Expect: 200, body contains state and amount, no lineItems, no items.
     - Failure: lineItems present when includeItems omitted, or old fields present.
  3) v2 includeItems=true
     - Input: GET /api/v2/orders?userId=789&includeItems=true
     - Expect: 200, lineItems present with name/quantity.
     - Failure: lineItems missing, wrong keys.
  4) Legacy client null access
     - Input: GET /api/v2/orders?userId=123
     - Legacy code reads order.items[0].productName
     - Expect: NullAccess / TypeError to surface; compatibility layer should prevent by returning items: [] for legacy clients.
     - Failure: compatibility layer missing or breaks.
  5) Analytics mapping
     - Input: GET /api/v2/orders?userId=456&includeItems=true
     - Expect: state and amount present; legacy analytics must map state->status and amount->totalPrice for aggregation.
     - Failure: aggregator throws KeyError or metrics become zero.
  6) Enum compatibility
     - Input: GET /api/v2/orders?userId=555
     - Expect: state=FULFILLED present; legacy consumers must map unknown states to 'UNKNOWN' or handle gracefully.
     - Failure: valueOf throws IllegalArgumentException.
  7) v1 deprecation detection
     - Input: GET /api/v1/orders/deprecated
     - Expect: 410 with API_VERSION_DEPRECATED; monitoring should treat as deprecation not outage.
     - Failure: monitoring raises a CRITICAL alert.

- Automation approach
  - Use the provided mock server to reproduce end-to-end behavior.
  - Add tests in `tests/test_api_migration.py` per the cases above.
  - Run tests in CI on each deploy of v2 and when compatibility changes are made.
