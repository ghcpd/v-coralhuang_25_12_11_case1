# README: API Migration Hardening Guide

## Overview

This package contains analysis, test coverage, and automated regression tests for the **Order API v1 → v2 migration** that has already caused failures in legacy clients.

### Critical Context

The migration from `/api/v1/orders` to `/api/v2/orders` introduces **5 breaking changes** that affect:
- Legacy web UI (NullPointerException on missing `items` field)
- Analytics pipelines (KeyError on renamed `status`/`totalPrice` fields)
- ETL/batch imports (IllegalArgumentException on new `FULFILLED` state value)
- Monitoring systems (false HTTP 410 outage alerts)
- Item processing workflows (conditional `lineItems` inclusion)

**Without remediation, legacy clients will fail within 30 minutes of deployment.**

---

## Repository Contents

| File | Purpose |
|------|---------|
| `01_API_EXAMPLES.md` | Concrete request/response examples for v1 vs v2 endpoints |
| `02_SCHEMA_COMPARISON.md` | Field mapping matrix, enum compatibility, migration risks |
| `03_IMPACT_ASSESSMENT.md` | Failure scenarios with stack traces and data loss analysis |
| `04_REGRESSION_TEST_PLAN.md` | 25-test coverage matrix with PASS/FAIL conditions |
| `regression_tests.py` | Automated test script (Python) - run before production deployment |
| `README.md` | This file |

---

## Quick Start

### 1. Review Breaking Changes

```
Status field:        status  →  state
Price field:         totalPrice  →  amount
Items container:     items  →  lineItems
Item name field:     productName  →  name
Item quantity field: qty  →  quantity
New state value:     (none)  →  FULFILLED (breaks legacy enum)
Item inclusion:      Always included  →  Conditional (requires includeItems parameter)
v1 deprecation:      HTTP 200  →  HTTP 410 Gone
```

### 2. Run Automated Tests

```bash
python regression_tests.py
```

**Expected output (PASS example):**
```
===== REGRESSION TEST SUITE =====
Running 25 test cases for API v1→v2 migration...

RT-001 [PASS] Field renaming: status → state
RT-002 [PASS] Field renaming: totalPrice → amount
RT-003 [PASS] Default includeItems=false omits lineItems
RT-004 [PASS] Explicit includeItems=false omits lineItems
RT-005 [PASS] includeItems=true includes lineItems array
...
RT-025 [PASS] Edge case: null field handling

===== SUMMARY =====
Total: 25 | PASS: 25 | FAIL: 0
Status: ✓ SAFE FOR PRODUCTION

Migration hardened. All legacy client patterns validated.
```

### 3. Deployment Checklist

- [ ] All 25 regression tests PASS
- [ ] Adapter layer deployed (provides v1-compatible response for legacy clients)
- [ ] Monitoring updated to check `/api/v2/orders` instead of v1
- [ ] Analytics job updated to use adapter or includes field mapping
- [ ] ETL import includes enum fallback for new `FULFILLED` state
- [ ] All 5 known error cases reproduced and verified as fixed
- [ ] Legacy client end-to-end tests executed

---

## Migration Risks & Remediation

### Risk 1: Missing `items` Field

**Symptom:** Legacy UI crashes with `TypeError: Cannot read properties of undefined`

**Root Cause:** v2 omits `lineItems` (and thus legacy `items`) when `includeItems` not provided

**Remediation:**
1. Deploy adapter layer that transforms v2 response to v1 schema
2. Adapter provides `items: []` when v2 omits lineItems
3. Update legacy client to pass `includeItems=true` for item details

**Verification:**
```bash
pytest regression_tests.py::test_RT_003  # includeItems default behavior
pytest regression_tests.py::test_RT_007  # Item fallback handling
```

---

### Risk 2: Field Renaming (status, totalPrice, productName, qty)

**Symptom:** KeyError on field access: `order['status']`, `order['totalPrice']`

**Root Cause:** v2 renamed all order and item fields

**Remediation:**
1. Adapter layer provides v1 field names from v2 response
2. Map: state→status, amount→totalPrice, name→productName, quantity→qty
3. Transform lineItems array to items array with field mapping

**Verification:**
```bash
pytest regression_tests.py::test_RT_001  # status → state validation
pytest regression_tests.py::test_RT_002  # productName/qty → name/quantity validation
pytest regression_tests.py::test_RT_017  # Backward compatibility
```

---

### Risk 3: New State Value (FULFILLED)

**Symptom:** IllegalArgumentException: `No enum constant OrderStatus.FULFILLED`

**Root Cause:** v2 introduces `FULFILLED` state not in legacy OrderStatus enum

**Remediation:**
1. ETL import includes enum fallback mapping
2. Map FULFILLED → SHIPPED (or business-defined default)
3. Never allow record drop due to unknown enum value

**Verification:**
```bash
pytest regression_tests.py::test_RT_012  # New state enum mapping
pytest regression_tests.py::test_RT_021  # ETL import with mapped enum
```

---

### Risk 4: Monitoring False Alarms

**Symptom:** CRITICAL alert fires for v1 endpoint returning HTTP 410

**Root Cause:** Monitoring treats non-200 as outage; doesn't recognize deprecation signal

**Remediation:**
1. Update monitoring to check `/api/v2/orders` instead of v1
2. Accept HTTP 410 from v1 as expected deprecation (not failure)
3. Only alert on HTTP 5xx or timeouts from v2

**Verification:**
```bash
pytest regression_tests.py::test_RT_019  # v1 deprecation signal
pytest regression_tests.py::test_RT_020  # Monitoring alert handling
```

---

### Risk 5: Analytics Data Corruption

**Symptom:** Revenue metrics drop to zero; status distribution empty

**Root Cause:** Analytics code tries to read renamed fields (status, totalPrice)

**Remediation:**
1. Analytics job uses adapter layer (gets v1-compatible response)
2. Or: Analytics queries include explicit field mapping: state→status, amount→totalPrice
3. Test aggregation logic with both v1 and v2 responses

**Verification:**
```bash
pytest regression_tests.py::test_RT_014  # Analytics revenue calculation
pytest regression_tests.py::test_RT_015  # Analytics status aggregation
```

---

## Test Coverage Summary

| Test Category | Tests | Coverage |
|---|---|---|
| Field Renaming | RT-001, RT-002 | Top-level and nested field names validated |
| includeItems Behavior | RT-003, RT-004, RT-005, RT-006 | Default, explicit false, explicit true, empty items |
| Item Safety | RT-007, RT-008, RT-023 | Fallback handling, field transformation, multiple items |
| Enum Mapping | RT-009, RT-010, RT-011, RT-012, RT-013 | All status values, new FULFILLED, edge cases |
| Analytics Integration | RT-014, RT-015, RT-016 | Revenue calculation, status distribution, missing fields |
| Backward Compatibility | RT-017, RT-018 | Legacy code contracts, iteration patterns |
| Deprecation Signal | RT-019, RT-020 | Endpoint deprecation, monitoring alert handling |
| Data Integrity | RT-021, RT-022 | ETL import, missing fields |
| Edge Cases | RT-024, RT-025 | Zero amount, null values |

**Total Coverage:** 25 tests, all CRITICAL/HIGH severity scenarios included

---

## How to Interpret Test Results

### All Tests PASS ✓
```
Status: SAFE FOR PRODUCTION
All legacy client patterns validated.
Breaking changes properly handled by adapter layer.
Ready to deprecate v1 endpoint and complete v2 migration.
```

### Any CRITICAL Test FAILS ✗
```
Status: DO NOT DEPLOY
Example: RT-012 FAIL - New state value not mapped
Action: Review impact assessment (03_IMPACT_ASSESSMENT.md) for this failure
        Implement missing remediation before retesting
```

### Any HIGH Test FAILS ⚠
```
Status: CONDITIONAL - Assess business impact
Example: RT-020 FAIL - Monitoring triggers false alert
Action: Update monitoring configuration to recognize deprecation signal
        Re-run test to verify, or accept known limitation with business risk acceptance
```

---

## Regression Test Scripts

### Pseudo-Code: What Each Test Does

```python
# Test RT-001: Field renaming validation
response = GET /api/v2/orders?includeItems=true
assert "state" in response  # New name
assert "status" not in response  # Old name not present
PASS

# Test RT-003: Default includeItems behavior
response = GET /api/v2/orders  # No includeItems parameter
assert "lineItems" not in response  # Must be omitted
assert "items" not in response  # Must not fallback
PASS

# Test RT-012: New enum value handling
response = GET /api/v2/orders with state="FULFILLED"
adapter_output = adapter.transform(response)
assert adapter_output.status in [PAID, CANCELLED, SHIPPED]  # Mapped to valid legacy value
PASS

# Test RT-021: ETL import with enum mapping
response_with_fulfilled = {..., "state": "FULFILLED"}
etl.import(response_with_fulfilled)
assert database.count(orderId="ORD-555") == 1  # Record saved
PASS
```

---

## Known Affected Clients

| Client | Failure Mode | Status | Remediation |
|--------|---|---|---|
| Legacy Web UI | Missing items field → TypeError | CRITICAL | Deploy adapter layer |
| Analytics Batch | KeyError on status/totalPrice | CRITICAL | Use adapter or update field mapping |
| ETL Pipeline | IllegalArgumentException on FULFILLED | CRITICAL | Add enum fallback, update mapping |
| Monitoring System | HTTP 410 triggers false alarm | HIGH | Update to check v2 endpoint |
| Fulfillment Service | Missing lineItems for weight calc | HIGH | Pass includeItems=true or use adapter |

---

## Migration Timeline

### Phase 1: Pre-Deployment (This Week)
- Review all documentation in this package
- Run automated regression tests
- Verify all tests PASS
- Confirm adapter layer ready for deployment

### Phase 2: Canary Deployment (Day 1)
- Deploy v2 API with adapter layer
- Monitor canary traffic (10% of requests)
- Verify zero failures in test metrics
- Check analytics and monitoring for anomalies

### Phase 3: Full Rollout (Day 2)
- Gradual ramp-up to 100% traffic
- Monitor error rates and performance
- Confirm all legacy clients functioning
- Review impact assessment for any unplanned failures

### Phase 4: v1 Deprecation (Week 2)
- Confirm v2 adoption complete
- Begin returning HTTP 410 from v1 endpoint
- Notify remaining v1 users of migration deadline
- Monitor and resolve any late-migration issues

### Phase 5: v1 Decommission (Week 4)
- Remove v1 endpoint entirely
- Archive migration documentation
- Close any residual support tickets

---

## Support & Escalation

**Test Failure?** Check `/03_IMPACT_ASSESSMENT.md` for your specific error scenario.

**Client Integration Issue?** Review `/02_SCHEMA_COMPARISON.md` for field mapping rules.

**Deployment Question?** Verify `/04_REGRESSION_TEST_PLAN.md` for required test coverage.

**Production Incident?** Compare actual error to examples in `/03_IMPACT_ASSESSMENT.md` and apply corresponding fix from `/02_SCHEMA_COMPARISON.md`.

---

## Success Criteria

✓ Migration is safe for legacy consumers when:
1. All 25 regression tests PASS
2. Adapter layer deployed and functioning
3. Zero alerts from monitoring system
4. Analytics metrics continuous (no zero-value gaps)
5. ETL import successful with proper enum mapping
6. Legacy web UI rendering orders without errors
7. Fulfillment service calculating weights correctly

**Estimated deployment impact:** 30 minutes of preparation, 2 hours for canary, 4 hours for full rollout, 0 production incidents.
