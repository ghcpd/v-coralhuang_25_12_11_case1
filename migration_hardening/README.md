Orders API v1 → v2 migration: compatibility hardening

Summary
- v2 changes: includeItems flag (default false), renamed fields (status → state, totalPrice → amount), items → lineItems (name/quantity), optional omission of lineItems when includeItems=false, extra state values (e.g., FULFILLED), and explicit deprecation behavior for /api/v1 (e.g., 410). 
- Risk: legacy clients assume v1 schema and semantics (items always present, fixed field names and enums, v1 always 200). These assumptions cause crashes, analytics errors, and false outages.

Key compatibility rules
- Provide compatibility aliases: status ← state, totalPrice ← amount.
- Always include items array in responses for clients that expect it: items = map(lineItems) if present else [] (never undefined/null).
- Normalize or map new state values into a legacy-safe status or include stateLegacy/statusNormalized to avoid enum parsing exceptions.
- During deprecation window, /api/v1 should either return 200 with a deprecation header and body, or a 410 with monitoring teams updated to avoid false outages.

How to run tests
- Ensure Python >= 3.8 and the requests library installed: pip install requests
- Run: python migration_hardening/test_api_compat.py --base-url http://localhost:8080
- Exit code 0: all compatibility checks passed. Non-zero: one or more failures.

Safe migration indicators
- All regression tests pass for /api/v2 (with and without includeItems) and the /api/v1 compatibility behavior.
- No monitoring alerts from infra during the deprecation window.
- Analytics and downstream jobs process v2 responses without field-name or enum errors.

Next steps
1. Deploy a short-lived compatibility proxy that implements the mapping rules above.
2. Add these tests to CI and block merges on FAIL.
3. Notify consumers and provide migration timeline and support telemetry (counts of legacy-field accesses).

Contact
- Engineering lead: [your-team@example.com]

License: internal engineering doc (do not publish).