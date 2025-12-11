Client Impact Assessment — failures, example logs, and mitigations

1) Missing items causes UI crash
- Symptom: TypeError: Cannot read properties of undefined (reading '0') at renderOrderSummary
- Cause: v2 omits lineItems when includeItems not present; legacy UI assumes order.items exists and indexes into items[0]
- Mitigation: compatibility layer always includes items: [] when lineItems absent; client fixes: null-check and check length before indexing

2) Renamed fields break analytics and batch jobs
- Symptom: KeyError: 'status' in aggregator.py:27 while reading order['status']
- Cause: analytics code reads status and totalPrice; v2 uses state and amount
- Mitigation: compatibility aliasing (status ← state; totalPrice ← amount) or update aggregator to read new fields

3) New state enums break enum parsing
- Symptom: IllegalArgumentException: No enum constant OrderStatus.FULFILLED at OrderStatus.valueOf
- Cause: v2 adds 'FULFILLED' not in legacy enum; OrderStatus.valueOf throws
- Mitigation: map new states to legacy-safe values or provide statusNormalized/stateLegacy fields; fix parsing to allow unknown values

4) /api/v1 deprecation triggers false outages
- Symptom: CRITICAL: orders API down; expected HTTP 200 from /api/v1/orders, got 410
- Cause: infrastructure monitoring treats any non-200 as outage; v1 intentionally returns 410 when deprecated
- Mitigation: run compatibility proxy for /api/v1 during deprecation window, or update monitors to expect 410 and treat as deprecation (non-outage)

Severity matrix (quick)
- Crash: High (UI NPEs)
- Data correctness (analytics): High
- Monitoring false-alarms: Medium
- Enum mapping: High (can drop records)

Telemetry recommendations
- Count responses where compatibility aliasing was used (e.g., status created from state)
- Track occurrences of unknown state values
- Monitor frequency of v1 calls and return code trends to schedule deprecation