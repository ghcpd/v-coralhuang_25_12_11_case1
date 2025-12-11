Client impact assessment

- Legacy UI (legacy-web):
  - Assumption: `items` always exists and contains at least one element.
  - Failure modes:
    - Null access: e.g., `order.items[0].productName` throws TypeError when `items` is undefined.
      - Root cause: v2 returns no `lineItems` if `includeItems` not given.
    - Mismatch in field names: `order.items[i].productName` -> `order.lineItems[i].name`.
  - Example failure log: "TypeError: Cannot read properties of undefined (reading '0') at renderOrderSummary; expected 'items[0].productName' but 'items' is undefined."

- Analytics job (analytics-batch):
  - Assumption: `status` and `totalPrice` present.
  - Failure modes:
    - KeyError or missing aggregation input when fields absent; metrics drop or aggregator fails.
    - Example: "KeyError: 'status' in aggregator.py:27 while reading order['status']; metrics 'orders_by_status' and 'revenue_total' drop to zero unexpectedly."

- Monitoring (infra-monitor):
  - Assumption: `/api/v1/orders` must return HTTP 200 to indicate system health.
  - Failure modes:
    - When v1 returns 410 for deprecation, monitoring raises false outage alerts.
    - Example: "CRITICAL: orders API down; expected HTTP 200 from /api/v1/orders, got 410 with error 'API_VERSION_DEPRECATED'."

- Batch importer (batch-importer):
  - Assumption: `state` maps to legacy `OrderStatus` enum via `valueOf(state)`.
  - Failure modes:
    - IllegalArgumentException or similar when encountering new state `FULFILLED`.
    - Example: "IllegalArgumentException: No enum constant OrderStatus.FULFILLED at OrderStatus.valueOf; record dropped and never imported into downstream system."

Mapping of failures to schema changes
- Missing `items` → omission of `lineItems` when includeItems not set.
- Renamed fields `status`/`totalPrice` → `state`/`amount` → missing keys in client code.
- Items reshaped → property name mismatches (`productName` vs `name`, `qty` vs `quantity`).
- New states → enum mapping failures.
- v1 deprecation → monitoring misinterprets deprecation as service outage.

Recommendations
- Roll out a compatibility layer (API gateway or middleware) that:
  - Maps `state` → `status` and `amount` → `totalPrice`.
  - Provides `items` always: if `lineItems` present map items accordingly; else return `items: []`.
  - Convert `lineItems` schema to match legacy expectation.
  - When v1 returns 410, adjust monitoring to flag deprecation instead of outage (or alter checks to call v2).
- Update important consumers (analytics, UI) as soon as possible; add runtime feature-flagged deployments to production.
- Add exhaustive regression tests (see regression_test_plan.md) and run them as part of CI and pre-deploy smoke tests.
