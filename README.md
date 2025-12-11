API Migration: /api/v1/orders → /api/v2/orders

Overview
- v2 introduces schema changes and behavioral changes that break legacy clients.
- This repo contains a mock API server and test harness to surface compatibility gaps.

Key changes
- Query parameter `includeItems` (default false) toggles whether item-level details are returned.
- Field renames: `status` -> `state`, `totalPrice` -> `amount`.
- Items renamed and reshaped: `items(productName, qty)` -> `lineItems(name, quantity)`.
- When includeItems is omitted or `false`, v2 omits `lineItems` entirely.
- v2 may introduce new `state` values such as `FULFILLED`.
- v1 endpoint is deprecated and returns `410` / `API_VERSION_DEPRECATED`.

Compatibility risks
- Legacy clients assume `items` always present and non-empty; code will crash when absent.
- Enum mapping from `state` to older `status` may fail with new values.
- Analytics and monitoring expect `status` and `totalPrice` fields.
- Monitoring that probes /api/v1/orders may interpret `410` as outage when it is deprecation.

Run the tests
- Uses Python 3 and Flask; tests run the mock server and then validate acceptance criteria.

Commands

Windows PowerShell (example):
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest -q
```

Interpretation
- Tests will provide PASS/FAIL per scenario.
- See `tests/test_api_migration.py` for exact checks and sample responses.

Contact
- For updates or migrations, update the compatibility wrapper to map v2 → v1 semantics or update clients.
