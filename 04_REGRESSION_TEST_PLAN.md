# Regression Test Plan & Coverage Matrix

## Test Execution Model

| Test ID | Test Category | Scenario | Input | Expected Output | Failure Condition | Severity |
|---------|---|----------|-------|-----------------|------------------|----------|
| **RT-001** | Field Renaming | v2 response field name validation | GET /api/v2/orders?userId=123&includeItems=true | Response has `state` (not `status`), `amount` (not `totalPrice`) | Response contains old field names `status` or `totalPrice` | CRITICAL |
| **RT-002** | Field Renaming | Nested item field name validation | GET /api/v2/orders?userId=123&includeItems=true | Response lineItems[0] has `name` and `quantity` | Response contains old field names `productName` or `qty` in items | CRITICAL |
| **RT-003** | includeItems Behavior | Default behavior (includeItems not provided) | GET /api/v2/orders?userId=123 (no includeItems param) | Response omits `lineItems` key entirely | Response includes `lineItems` or `items` key | CRITICAL |
| **RT-004** | includeItems Behavior | Explicit includeItems=false | GET /api/v2/orders?userId=123&includeItems=false | Response omits `lineItems` key | Response includes lineItems | CRITICAL |
| **RT-005** | includeItems Behavior | includeItems=true included | GET /api/v2/orders?userId=123&includeItems=true | Response includes `lineItems` array with items | Response omits lineItems or lineItems is empty when items exist | CRITICAL |
| **RT-006** | Item Safety | Empty items with includeItems=true | GET /api/v2/orders?userId=empty&includeItems=true | Response has `lineItems: []` | Response missing lineItems key or null value | HIGH |
| **RT-007** | Item Safety | Fallback handling in legacy adapter | Adapter receives v2 response without lineItems | Adapter returns mapped response with `items: []` | Adapter throws error or returns undefined items | HIGH |
| **RT-008** | Item Safety | Field mapping during adapter transformation | Adapter receives v2 lineItems=[{name, quantity}] | Adapter returns items=[{productName, qty}] with values correctly mapped | Mapped items have missing fields or incorrect names | HIGH |
| **RT-009** | Enum Mapping | v1 status value mapping | State value `PAID` in v2 response | Adapter maps to OrderStatus.PAID | Mapping returns wrong status or throws error | CRITICAL |
| **RT-010** | Enum Mapping | v1 status value mapping | State value `CANCELLED` in v2 response | Adapter maps to OrderStatus.CANCELLED | Mapping returns wrong status or throws error | CRITICAL |
| **RT-011** | Enum Mapping | v1 status value mapping | State value `SHIPPED` in v2 response | Adapter maps to OrderStatus.SHIPPED | Mapping returns wrong status or throws error | CRITICAL |
| **RT-012** | Enum Mapping | New state value (FULFILLED) | State value `FULFILLED` in v2 response | Adapter maps to defined fallback (e.g., SHIPPED) without throwing exception | Adapter throws IllegalArgumentException or skips record | CRITICAL |
| **RT-013** | Enum Mapping | Unknown state value | State value `UNKNOWN_STATE` in v2 response (edge case) | Adapter either maps to default or throws descriptive error | Adapter throws unhelpful exception or crashes silently | HIGH |
| **RT-014** | Analytics Integration | Revenue calculation with field mapping | v2 response with `amount: 199.99` | Adapter maps to `totalPrice: 199.99`; revenue sum correct | Revenue metric is zero or incorrect due to missing field | CRITICAL |
| **RT-015** | Analytics Integration | Status distribution with field mapping | v2 response array with mixed states (PAID, CANCELLED) | Adapter maps to legacy statuses; aggregation counts correct | Status buckets are empty or show wrong distribution | CRITICAL |
| **RT-016** | Analytics Integration | Missing lineItems fallback | v2 response without lineItems | Adapter provides empty items array, no analytics failure | Analytics code crashes on null/undefined items | CRITICAL |
| **RT-017** | Backward Compatibility | Legacy code calling adapter | Legacy code expects: order['status'], order['totalPrice'], order['items'] | Adapter response has all three fields with correct values | Adapter response missing any field or has wrong field name | CRITICAL |
| **RT-018** | Backward Compatibility | v1 pagination with v2 adapter | Legacy code loops: for item in order['items'] | Loop executes without error; correct number of items processed | Loop throws TypeError or processes wrong number of items | CRITICAL |
| **RT-019** | Deprecation Signal | v1 endpoint deprecation status | GET /api/v1/orders | Returns HTTP 410 with error='API_VERSION_DEPRECATED' | Returns HTTP 200 (endpoint not deprecated) | HIGH |
| **RT-020** | Deprecation Signal | Monitoring alert handling | Monitoring system receives HTTP 410 from v1 | Monitoring system recognizes as deprecation (not outage) | Monitoring fires CRITICAL alert for false outage | CRITICAL |
| **RT-021** | Data Integrity | ETL import with enum mapping | ETL pipeline receives v2 response with state=FULFILLED | ETL either successfully imports with mapped status or skips with logged reason | ETL silently drops record without logging | CRITICAL |
| **RT-022** | Data Integrity | ETL import with missing fields | ETL pipeline receives v2 response | ETL uses adapter, all required fields present | ETL throws NullPointerException or KeyError | CRITICAL |
| **RT-023** | Edge Case | Multiple lineItems processing | GET /api/v2/orders?includeItems=true with 10 items | All 10 items correctly mapped with field transformation | Any item dropped or field missing in mapping | HIGH |
| **RT-024** | Edge Case | Order with zero amount | GET /api/v2/orders?includeItems=true&orderId=CANCELLED_ORDER | Response has `amount: 0` correctly mapped to `totalPrice: 0` | Amount/totalPrice missing or incorrect | MEDIUM |
| **RT-025** | Edge Case | Null/undefined field values | Response with optional fields missing | Adapter handles gracefully, provides sensible defaults | Adapter crashes on undefined field access | HIGH |

---

## Test Case Details

### Test RT-001: Field Renaming Validation (status → state)

**Input:**
```http
GET /api/v2/orders?userId=123&includeItems=true
```

**Expected Response:**
```json
{
  "orderId": "ORD-123",
  "state": "PAID",
  "amount": 199.99,
  "lineItems": [...]
}
```

**PASS Condition:**
- Response contains key `state` with value in [PAID, CANCELLED, SHIPPED, FULFILLED]
- Response does NOT contain key `status`

**FAIL Condition:**
- Response missing `state` key
- Response contains `status` key instead of `state`
- `state` value is null or empty string

**Failure Example:**
```json
{
  "orderId": "ORD-123",
  "status": "PAID",  // ← FAIL: wrong field name
  "totalPrice": 199.99,
  "items": [...]
}
```

---

### Test RT-003 & RT-004: includeItems Default & Explicit false

**Input 1 (Default):**
```http
GET /api/v2/orders?userId=123
```

**Input 2 (Explicit false):**
```http
GET /api/v2/orders?userId=123&includeItems=false
```

**Expected Response (Both):**
```json
{
  "orderId": "ORD-123",
  "state": "PAID",
  "amount": 199.99
}
```

**PASS Condition:**
- Response does NOT contain `lineItems` key
- Response does NOT contain `items` key
- Response body has exactly 3 keys: orderId, state, amount

**FAIL Condition:**
- Response includes `lineItems` key (should be omitted)
- Response includes `items` key
- lineItems has empty value `null` instead of being absent

**Test RT-005: includeItems=true**

**Input:**
```http
GET /api/v2/orders?userId=123&includeItems=true
```

**Expected Response:**
```json
{
  "orderId": "ORD-123",
  "state": "PAID",
  "amount": 199.99,
  "lineItems": [
    { "name": "Pen", "quantity": 3 },
    { "name": "Notebook", "quantity": 2 }
  ]
}
```

**PASS Condition:**
- Response contains `lineItems` key
- lineItems is array (not null, not object)
- lineItems has correct number of items (>0 for this test case)
- Each item has `name` and `quantity` fields

**FAIL Condition:**
- lineItems missing entirely
- lineItems is null or empty array (when items should exist)
- lineItems[0] missing `name` or `quantity` fields

---

### Test RT-012: New State Value (FULFILLED) Compatibility

**Input:**
```http
GET /api/v2/orders?userId=555&includeItems=false
```

**Response (Contains New State):**
```json
{
  "orderId": "ORD-555",
  "state": "FULFILLED",
  "amount": 120.0
}
```

**Legacy Client Adapter Behavior:**

**PASS Condition (via adapter):**
```java
// Adapter must handle new state
OrderState v2State = OrderState.valueOf("FULFILLED");  // OK
OrderStatus legacyStatus = adapter.mapState(v2State);  // Maps to fallback (e.g., SHIPPED)
assert legacyStatus != null;
assert legacyStatus in [PAID, CANCELLED, SHIPPED];  // Mapped to valid legacy value
```

**FAIL Condition:**
```java
// Without adapter or with poor mapping
OrderStatus.valueOf("FULFILLED");  // IllegalArgumentException ← FAIL
// Record skipped, data lost
```

**Concrete Failure Log:**
```
IllegalArgumentException: No enum constant OrderStatus.FULFILLED
  at java.lang.Enum.valueOf(Enum.java:238)
  at OrderImporter.importOrders(OrderImporter.java:42)
  
Record ORD-555 dropped from import. Never saved to database.
```

---

### Test RT-017: Backward Compatibility - Legacy Code Contract

**Legacy Client Code:**
```javascript
function processLegacy(response) {
  const status = response.status;
  const price = response.totalPrice;
  const items = response.items || [];
  return {
    status: status,
    price: price,
    itemCount: items.length
  };
}
```

**Adapter Output (v2 → v1):**
```json
{
  "orderId": "ORD-123",
  "status": "PAID",
  "totalPrice": 199.99,
  "items": [
    { "productName": "Pen", "qty": 3 }
  ]
}
```

**PASS Condition:**
- `response.status` returns "PAID" (not undefined)
- `response.totalPrice` returns 199.99 (not undefined)
- `response.items` returns array (not undefined)
- `items[0].productName` returns "Pen" (not undefined)
- `items[0].qty` returns 3 (not undefined)

**FAIL Condition:**
- Any of above fields returns undefined or null
- Adapter throws error instead of providing mapped response
- Items have wrong property names or values

**Failure Example:**
```javascript
const status = response.status;  // undefined ← FAIL
const price = response.totalPrice;  // undefined ← FAIL
const items = response.items;  // undefined ← FAIL
itemsHtml = items.map(...);  // TypeError: Cannot read property 'map' of undefined
```

---

### Test RT-019 & RT-020: Deprecation Signal Handling

**Input:**
```http
GET /api/v1/orders?userId=999
```

**Expected Response:**
```
HTTP/1.1 410 Gone

{
  "error": "API_VERSION_DEPRECATED",
  "message": "Please migrate to /api/v2/orders"
}
```

**PASS Condition (for RT-019):**
- HTTP status code is 410 (Gone)
- Response body contains `error: "API_VERSION_DEPRECATED"`
- Response body contains migration guidance

**FAIL Condition:**
- HTTP status is 200 (endpoint not marked deprecated)
- HTTP status is 500 (internal error instead of deprecation signal)
- Response lacks deprecation metadata

**PASS Condition (for RT-020 - Monitoring):**
```python
# Monitoring system must recognize 410 as deprecation, not outage
if response.status == 410 and 'DEPRECATED' in response.error:
  log("Endpoint deprecated, but API healthy via v2")
  # Don't trigger alert
else if response.status != 200:
  alert("API unreachable")  # Only for truly problematic codes
```

**FAIL Condition:**
```python
# Monitoring treats 410 as outage
if response.status != 200:
  alert("CRITICAL: API DOWN")  # ← False positive, monitoring fails
```

---

### Test RT-021: ETL Import with Enum Mapping

**Input (ETL receives v2 response):**
```json
{
  "orderId": "ORD-555",
  "state": "FULFILLED",
  "amount": 120.0,
  "lineItems": [{"name": "Book", "quantity": 1}]
}
```

**PASS Condition:**
- ETL successfully imports record
- Record saved to warehouse with mapped status (e.g., SHIPPED)
- lineItems correctly transformed to items with field mapping
- Query: `SELECT COUNT(*) FROM orders WHERE orderId='ORD-555'` returns 1

**FAIL Condition:**
- ETL job crashes on enum exception
- Record silently dropped (no log, no database entry)
- Query: `SELECT COUNT(*) FROM orders WHERE orderId='ORD-555'` returns 0
- ETL log shows: `IllegalArgumentException: No enum constant OrderStatus.FULFILLED`

**Failure Scenario (Real Production):**
```
ETL Import Report:
  Records processed: 100
  Records imported: 99
  Records failed: 1
  Failed record: ORD-555 (new state FULFILLED)
  
Data warehouse after import:
  SELECT COUNT(*) FROM orders WHERE state='FULFILLED': 0  ← Lost record
  SELECT COUNT(*) FROM orders WHERE orderId='ORD-555': 0  ← Lost forever
```

---

## Summary: Test Execution Checklist

- [ ] All RT-001 through RT-003: Field presence and naming validated
- [ ] RT-005, RT-006, RT-007: Item inclusion behavior correct with adapter
- [ ] RT-009 through RT-012: Enum mapping handles all state values
- [ ] RT-014, RT-015, RT-016: Analytics integration with adapter works
- [ ] RT-017, RT-018: Legacy client code compatibility verified
- [ ] RT-019, RT-020: Deprecation signal recognized, monitoring not triggered
- [ ] RT-021, RT-022: ETL import succeeds with mapped fields
- [ ] RT-023 through RT-025: Edge cases handled gracefully

**Success Criteria:** All tests PASS. Any CRITICAL or HIGH severity FAIL blocks migration.
