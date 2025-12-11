Regression Test Plan — compact test cases

Test-1: Field renames and aliases
- Input: GET /api/v2/orders?userId=any&includeItems=true
- Expected: response contains both 'state' and alias 'status'; 'amount' and alias 'totalPrice' exist
- Failure: alias fields missing

Test-2: includeItems absent (items presence contract)
- Input: GET /api/v2/orders?userId=any (no includeItems)
- Expected: response contains items: [] (array) to satisfy legacy client assumptions
- Failure: items undefined or null

Test-3: includeItems=true mapping shape
- Input: GET /api/v2/orders?userId=any&includeItems=true where lineItems present
- Expected: response includes lineItems and items mapped with {productName, qty}
- Failure: mapping incorrect or items missing

Test-4: Empty lineItems
- Input: GET /api/v2/orders?includeItems=true with lineItems: []
- Expected: items: [] present
- Failure: items missing or null

Test-5: Enum compatibility and unknown state handling
- Input: GET /api/v2/orders?userId=555 where state='FULFILLED'
- Expected: response provides a legacy-safe 'status' or 'stateLegacy' and client does not throw when parsing
- Failure: enum parse error or record dropped

Test-6: Analytics correctness
- Input: GET /api/v2/orders?includeItems=true where amount=0.0 and state='CANCELLED'
- Expected: analytics reads amount via alias totalPrice and aggregates revenue correctly
- Failure: revenue misaggregation due to missing totalPrice

Test-7: /api/v1 deprecation behavior
- Input: GET /api/v1/orders
- Expectation: during transition, return 200 with X-API-Deprecated: true OR if 410 returned, monitors configured to treat it as planned deprecation
- Failure: monitoring emits outage alerts

Test Implementation notes
- Each test includes an explicit expected output and exact failure condition.
- Tests should run in CI and block merges if any compatibility test fails.
- Add additional tests for consumer-specific edge cases (bulk imports, streaming, enum parsing in typed languages).