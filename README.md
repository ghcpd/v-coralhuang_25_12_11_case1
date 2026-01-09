API migration: /api/v1/orders → /api/v2/orders

Summary
-------
This repo contains an analysis and test harness to validate compatibility issues introduced by migrating /api/v1/orders to /api/v2/orders.

Key changes in v2
- New required query parameter includeItems (default false) controls whether items are returned.
- Field renames: status -> state; totalPrice -> amount; items(productName, qty) -> lineItems(name, quantity).
- lineItems may be omitted when includeItems is absent or false.
- New state values (e.g., FULFILLED) may be present and not in legacy enums.
- /api/v1/orders returns explicit deprecation (HTTP 410, API_VERSION_DEPRECATED) rather than 200.

Compatibility Risks
- Legacy clients assume items[] always exists and non-empty; absence or empty arrays cause indexing errors.
- Analytics that read status and totalPrice will miss fields (renames) unless mapped.
- Enum parsing (e.g., OrderStatus.valueOf(state)) will throw on unknown values.
- Monitoring that treats non-200 as outage will be triggered by deprecation responses.

Files
- migration_utils.py: mapping/detection helpers and safe fallback rules.
- error_case.json: concrete request/response test fixtures (realistic examples).
- tests/test_api_migration.py: test logic using fixtures.
- run_tests.py: simple runner printing PASS/FAIL and returning nonzero exit on failures.

How to run
- Python 3.x (no external deps required):
    python run_tests.py

Interpreting results
- All PASS: migration is compatible with legacy consumers according to our rules (including safe fallbacks implemented by a compatibility layer).
- Any FAIL: indicates a scenario where legacy clients may crash or produce incorrect metrics; fix by adding server-side compatibility layer or updating clients and re-running tests.

Recommended mitigations
- Server-side compatibility middleware that returns v1-shaped payloads when X-Client or an Accept header indicates a legacy consumer, OR a v1 passthrough that maps fields as below:
    - state -> status (if unknown, map to 'UNKNOWN' or a safe fallback and add a header indicating mapping)
    - amount -> totalPrice
    - lineItems -> items (map name->productName, quantity->qty). If includeItems is false, return items: [] (and consider including a header to indicate items omitted)
    - /api/v1/orders: keep returning HTTP 200 for a transition period and add deprecation header; avoid returning 410 until consumers are migrated

Contact
- For engineering handoff: include this README plus the automated test evidence (run_tests.py output) when discussing migration rollout plans.
