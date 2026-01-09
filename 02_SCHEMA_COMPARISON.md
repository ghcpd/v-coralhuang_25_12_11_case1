# Schema Comparison & Backward Compatibility Analysis

## v1 Order Schema (Legacy)

```json
{
  "orderId": "string",
  "status": "enum (PAID | CANCELLED | SHIPPED)",
  "totalPrice": "number",
  "items": "array of Item",
  "createdAt": "ISO8601 timestamp"
}

Item {
  "productName": "string",
  "qty": "integer (>= 0)"
}
```

### v1 Schema Constraints
- `items` is **always present** (may be empty array `[]`)
- `status` must be one of: `PAID`, `CANCELLED`, `SHIPPED`
- `totalPrice` is always a non-negative number
- All fields are required in the response

---

## v2 Order Schema (New)

```json
{
  "orderId": "string",
  "state": "enum (PAID | CANCELLED | SHIPPED | FULFILLED)",
  "amount": "number",
  "lineItems": "array of LineItem (OPTIONAL, only if includeItems=true)",
  "createdAt": "ISO8601 timestamp"
}

LineItem {
  "name": "string",
  "quantity": "integer (>= 0)"
}
```

### v2 Schema Constraints
- `lineItems` is **conditionally present** (omitted if `includeItems` is absent or `false`)
- `state` can be: `PAID`, `CANCELLED`, `SHIPPED`, or **`FULFILLED`** (new)
- `amount` is always a non-negative number
- Query parameter `includeItems` controls response structure

---

## Field Mapping Matrix

| v1 Field | v2 Field | Change Type | Impact | Fallback Strategy |
|----------|----------|-------------|--------|-------------------|
| `status` | `state` | **Renamed** | Direct property access fails | Map state → status in adapter layer |
| `totalPrice` | `amount` | **Renamed** | Direct property access fails | Map amount → totalPrice in adapter layer |
| `items` | `lineItems` | **Renamed + Conditional** | Array iteration fails; may be undefined | Check for lineItems existence; fallback to empty array |
| `items[].productName` | `lineItems[].name` | **Renamed** | Property access fails in loops | Transform lineItems array during mapping |
| `items[].qty` | `lineItems[].quantity` | **Renamed** | Property access fails in loops | Transform lineItems array during mapping |

---

## Enum Compatibility Issues

### Status/State Values

**v1 OrderStatus Enum:**
```java
public enum OrderStatus {
  PAID,
  CANCELLED,
  SHIPPED
}
```

**v2 State Enum:**
```java
public enum OrderState {
  PAID,
  CANCELLED,
  SHIPPED,
  FULFILLED  // ← NEW, breaks v1 enum
}
```

### Legacy Client Behavior When Encountering v2 Response
```
Receive: state = "FULFILLED"
Action: OrderStatus.valueOf("FULFILLED")
Result: IllegalArgumentException: No enum constant OrderStatus.FULFILLED
Impact: Record dropped, never imported to downstream system
```

### Proper Fallback
```java
// Safe mapping with fallback
OrderState stateFromV2 = OrderState.valueOf(response.state);
OrderStatus legacyStatus = switch(stateFromV2) {
  case PAID -> OrderStatus.PAID;
  case CANCELLED -> OrderStatus.CANCELLED;
  case SHIPPED -> OrderStatus.SHIPPED;
  case FULFILLED -> OrderStatus.SHIPPED; // or PAID, business decision
};
```

---

## Response Structure Differences

### Scenario 1: v2 Without includeItems (Default)

**v1 Equivalent:**
```json
{
  "orderId": "ORD-123",
  "status": "PAID",
  "totalPrice": 199.99,
  "items": []  // Always present, may be empty
}
```

**v2 Actual Response:**
```json
{
  "orderId": "ORD-123",
  "state": "PAID",
  "amount": 199.99
  // lineItems key is absent entirely
}
```

**Client Code Failure:**
```python
# v1-style code (legacy)
for item in response['items']:  # KeyError if items missing
  process(item['productName'], item['qty'])

# v2 without includeItems fails:
# KeyError: 'items' - the key doesn't exist
```

### Scenario 2: v2 With includeItems=true

**v1 Equivalent:**
```json
{
  "orderId": "ORD-123",
  "status": "PAID",
  "totalPrice": 199.99,
  "items": [
    { "productName": "Pen", "qty": 3 },
    { "productName": "Notebook", "qty": 2 }
  ]
}
```

**v2 Actual Response:**
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

**Client Code Failure:**
```python
# v1-style code (legacy)
for item in response['items']:  # KeyError: items
  process(item['productName'], item['qty'])

# v2 has 'lineItems' not 'items'
# KeyError: 'items' - wrong key name
# Even if key existed, KeyError: 'productName' - wrong field name
```

---

## Backward Compatibility Assessment

| Change | Severity | Mitigation | Cost |
|--------|----------|-----------|------|
| Field renames (status/totalPrice) | **CRITICAL** | Adapter layer with field mapping | Low (simple transformation) |
| Nested field renames (productName/qty) | **CRITICAL** | Array transformation in adapter | Low (simple transformation) |
| Conditional lineItems | **CRITICAL** | Default to empty array when missing | Low (fallback logic) |
| New state value (FULFILLED) | **HIGH** | Enum fallback mapping | Medium (enum definition update) |
| v1 deprecation (HTTP 410) | **HIGH** | Update monitoring to check v2 endpoint | Medium (infrastructure change) |
| Query parameter requirement | **MEDIUM** | Document mandatory `includeItems` parameter | Low (documentation) |

---

## Compatibility Layer Mapping Rules

### Rule 1: Field Name Mapping
```
v2.state → v1.status
v2.amount → v1.totalPrice
v2.lineItems → v1.items
```

### Rule 2: Conditional Item Inclusion
```
If includeItems not provided or false:
  v1.items = []  (empty array)
  
Else if includeItems = true:
  v1.items = [transform(li) for li in v2.lineItems]
  where transform(li) = {productName: li.name, qty: li.quantity}
```

### Rule 3: State/Status Mapping
```
v2.state → v1.status:
  PAID → PAID
  CANCELLED → CANCELLED
  SHIPPED → SHIPPED
  FULFILLED → SHIPPED (or business-defined default)
```

### Rule 4: Safe Navigation
```
Legacy code must:
  1. Check for key existence before access: if 'items' in response
  2. Use .get() with defaults: response.get('items', [])
  3. Type-check enums: use try-except for OrderStatus.valueOf()
```

---

## Migration Timeline Risks

| Phase | Risk | Symptom | Timeline |
|-------|------|---------|----------|
| **Week 1** | Legacy clients call v2 without adaptation | Null pointer errors, KeyError, lost data | Immediate |
| **Week 2** | Analytics still read renamed fields | Revenue metrics drop to zero, false alarms | 1-2 days post-deploy |
| **Week 3** | Monitoring treats v1 deprecation as outage | PagerDuty fire, emergency escalations | 4-6 hours post-deploy |
| **Week 4** | New state value encountered in production | Record loss in downstream systems | Random, unpredictable |

---

## Summary: What Breaks Without Adapter Layer

1. **Direct field access**: `response['status']` → KeyError
2. **Nested field access**: `response['items'][0]['productName']` → TypeError/KeyError
3. **Enum parsing**: `OrderStatus.valueOf("FULFILLED")` → IllegalArgumentException
4. **Monitoring alerts**: HTTP 410 from v1 → false positive outage alarm
5. **Analytics aggregation**: Missing renamed fields → corrupted metrics
6. **Item iteration**: `for item in response['items']` → TypeError when lineItems omitted
