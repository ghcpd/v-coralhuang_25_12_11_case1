# Client Impact Assessment: Failure Scenarios

## Executive Summary

The migration from `/api/v1/orders` to `/api/v2/orders` introduces **5 critical failure modes** affecting legacy clients:

1. **Missing Field Errors**: Renamed/omitted fields cause null pointer and KeyError exceptions
2. **Enum Mapping Failures**: New `FULFILLED` state breaks legacy OrderStatus enum
3. **Analytics Data Corruption**: Metric aggregation fails due to renamed fields
4. **Monitoring False Alarms**: Deprecated v1 endpoint returns HTTP 410, triggering production alerts
5. **Item Processing Failures**: Conditional `lineItems` inclusion causes iteration errors

---

## Impact Analysis by Client Type

### 1. Legacy Web UI Client

**Affected Code Pattern:**
```javascript
// Legacy code - v1 style
function renderOrderDetails(response) {
  const orderId = response.orderId;
  const status = response.status;  // ← Will be undefined in v2
  const total = response.totalPrice;  // ← Will be undefined in v2
  
  const itemsHtml = response.items.map(item =>  // ← TypeError if items missing
    `<li>${item.productName}: ${item.qty}</li>`
  ).join('');
  
  return `<div>Order ${orderId} (${status}): $${total}\n${itemsHtml}</div>`;
}

// Called with v2 response (without includeItems)
const v2Response = {
  orderId: "ORD-123",
  state: "PAID",  // Not 'status'
  amount: 199.99  // Not 'totalPrice'
  // lineItems missing
};

renderOrderDetails(v2Response);
```

**Failure Output:**
```
TypeError: Cannot read properties of undefined (reading '0')
  at renderOrderDetails (app.js:3:15)
  at processOrders (app.js:10:20)
  
Cause: response.items is undefined
Expected: items[] array
Actual: lineItems property not present when includeItems not provided
```

**Concrete Example Error:**
```
TypeError: Cannot read properties of undefined (reading 'map')
Stack trace:
  at Object.<anonymous> (/app/ui/orders.js:42:15)
  at Module._load (internal/modules/commonjs)
  
Line 42: const itemsHtml = response.items.map(item => ...)
Field accessed: items
Response received: {orderId, state, amount}
Fix required: Check for items, use lineItems with field mapping
```

---

### 2. Analytics Batch Processing

**Affected Code Pattern:**
```python
# Legacy code - v1 style
def aggregate_order_metrics(orders_list):
  metrics = {
    'total_revenue': 0,
    'orders_by_status': {}
  }
  
  for order in orders_list:
    # These fields don't exist in v2
    status = order['status']  # KeyError in v2
    price = order['totalPrice']  # KeyError in v2
    
    metrics['total_revenue'] += price
    metrics['orders_by_status'][status] = metrics['orders_by_status'].get(status, 0) + 1
  
  return metrics

# Called with v2 response
v2_orders = [
  {'orderId': 'ORD-123', 'state': 'PAID', 'amount': 199.99},
  {'orderId': 'ORD-456', 'state': 'CANCELLED', 'amount': 0}
]

result = aggregate_order_metrics(v2_orders)
```

**Failure Output:**
```
KeyError: 'status'
  File "aggregator.py", line 27, in aggregate_order_metrics
    status = order['status']
  
Traceback:
  KeyError: 'status'
  metrics 'orders_by_status' remains {}
  metrics 'total_revenue' remains 0

Expected output: {total_revenue: 199.99, orders_by_status: {PAID: 1, CANCELLED: 1}}
Actual output: Job fails, metrics not updated, dashboard shows stale data
```

**Impact:**
- Revenue dashboards show zero revenue (incorrect)
- Order status distribution metrics become unavailable
- Downstream BI systems receive corrupted data
- Finance team cannot reconcile orders for that time period

---

### 3. Batch Import / ETL Pipeline

**Affected Code Pattern:**
```java
// Legacy code - v1 style
public class OrderImporter {
  public void importOrders(List<Map<String, Object>> orders) {
    for (Map<String, Object> order : orders) {
      String orderId = (String) order.get("orderId");
      
      // These fail in v2 with new state value
      String statusStr = (String) order.get("status");  // Null in v2
      OrderStatus status = OrderStatus.valueOf(statusStr);  // NPE or IAE
      
      double totalPrice = (double) order.get("totalPrice");  // ClassCastException
      
      List<Map> items = (List<Map>) order.get("items");  // Null in v2
      for (Map item : items) {
        String productName = (String) item.get("productName");  // NPE
        int qty = (int) item.get("qty");
        // Process item
      }
      
      saveToDatabase(orderId, status, totalPrice, items);
    }
  }
}

// Called with v2 response containing new FULFILLED state
List<Map<String, Object>> v2Orders = Arrays.asList(
  Map.of("orderId", "ORD-555", "state", "FULFILLED", "amount", 120.0)
);

importer.importOrders(v2Orders);
```

**Failure Output:**
```
IllegalArgumentException: No enum constant OrderStatus.FULFILLED
  at java.lang.Enum.valueOf(Enum.java:238)
  at OrderImporter.importOrders(OrderImporter.java:42)
  at ETLPipeline.run(ETLPipeline.java:18)

Exception: Record ORD-555 with state FULFILLED cannot be imported
Action: Record skipped, never inserted into database
Impact: Order missing from data warehouse indefinitely
```

**Alternative Failure (Missing Field):**
```
NullPointerException: Cannot invoke method on null object
  at OrderImporter.importOrders(OrderImporter.java:44)

Cause: order.get("status") returns null (field doesn't exist in v2)
statusStr = null
OrderStatus.valueOf(null) → NPE
Action: Record ORD-556 fails import
Impact: Partial import, inconsistent data warehouse state
```

---

### 4. Monitoring & Alerting System

**Affected Code Pattern:**
```python
# Legacy code - v1 style
def monitor_orders_api():
  try:
    response = requests.get('https://api.example.com/api/v1/orders?userId=999')
    
    # Monitoring assumes HTTP 200 means healthy
    if response.status_code != 200:
      alert("CRITICAL: Orders API is down")
      trigger_pagerduty_incident()
      return False
    
    # If here, API is healthy
    log("Orders API check passed")
    return True
    
  except Exception as e:
    alert(f"ERROR: {e}")
    return False

# v1 endpoint returns 200 OK - check passes
# v2 deprecation: v1 endpoint returns 410 Gone
```

**Failure Output When v1 is Deprecated:**
```
CRITICAL ALERT: Orders API down
  Endpoint: /api/v1/orders
  Expected: HTTP 200
  Received: HTTP 410
  Response: {"error": "API_VERSION_DEPRECATED", "message": "Please migrate to /api/v2/orders"}

PagerDuty Incident: #P-2024-12-15-001 created
Severity: CRITICAL
Triggered: 2024-12-15T14:32:00Z

Impact:
  - On-call engineer paged
  - War room opened
  - Investigation begins for "API outage"
  - Developers spend 30min debugging healthy v2 endpoint
  - False alarm destroys alert credibility
```

**Multi-Endpoint Cascade:**
```
Timeline:
  14:30 - v1 deprecated, returns 410
  14:32 - Monitoring check fails
  14:33 - PagerDuty fires CRITICAL alert
  14:34 - On-call engineer woken up
  14:35 - Ops begins diagnostics
  14:45 - Someone checks v2 endpoint, finds it's healthy
  14:46 - Incident resolved as false alarm

Cost: 1 hour response time, 2+ engineer-hours, alert fatigue
```

---

### 5. Item Processing with Conditional Inclusion

**Affected Code Pattern:**
```python
# Legacy code - v1 style
def calculate_order_weight(order):
  """Calculate shipment weight from items"""
  total_weight = 0
  
  for item in order['items']:  # May be missing in v2
    product_id = item['productName']  # v2 uses 'name'
    quantity = item['qty']  # v2 uses 'quantity'
    
    # Lookup product weight
    weight = PRODUCT_DB[product_id]['weight_kg']
    total_weight += weight * quantity
  
  return total_weight

# Called with v2 response without includeItems
v2_response_no_items = {
  'orderId': 'ORD-789',
  'state': 'SHIPPED',
  'amount': 59.5
  # lineItems NOT included
}

weight = calculate_order_weight(v2_response_no_items)
```

**Failure Output:**
```
TypeError: 'NoneType' object is not iterable
  File "shipping.py", line 42, in calculate_order_weight
    for item in order['items']:
  
KeyError: 'items'
Value: None (key doesn't exist)
Expected: items array
Actual: lineItems present only when includeItems=true

Shipment never calculated, order stuck in processing
```

---

## Field Access Failure Matrix

| Client Type | Field Accessed | v1 Result | v2 Result (no includeItems) | v2 Result (with includeItems) | Failure Type |
|-------------|---|-----------|---------------------------|------------------------------|------------|
| Web UI | `response['status']` | "PAID" | undefined | undefined | TypeError |
| Web UI | `response['items'][0]` | {productName, qty} | TypeError | TypeError |
| Analytics | `order['totalPrice']` | 199.99 | KeyError | KeyError | KeyError |
| Analytics | `order['status']` | "PAID" | KeyError | KeyError | KeyError |
| ETL | `OrderStatus.valueOf(order['status'])` | OK | NullPointerException | NullPointerException | NPE |
| ETL | New state value in enum | N/A | N/A | IllegalArgumentException | IAE |
| Monitoring | GET /api/v1/orders | HTTP 200 | HTTP 410 | N/A | Alert Storm |
| Shipping | `order['items']` loop | OK | KeyError | OK | KeyError |
| Shipping | `item['productName']` | "Laptop" | N/A | KeyError | KeyError |

---

## Data Integrity Failures

### Scenario A: Revenue Metric Corruption
```
Event: v2 deployed without adapter layer
T+0h: API switch to v2
T+1h: Analytics batch runs, tries to read 'totalPrice'
T+1h+5m: KeyError on all orders, metrics job fails silently
T+6h: Finance team notices revenue dashboard is missing 5+ hours of data
T+24h: Manual reconciliation required to recover lost metrics
Impact: $500K+ in unreconciled transactions
```

### Scenario B: Duplicate Record Import
```
Event: ETL pipeline fails with enum exception
T+0h: New order arrives with state=FULFILLED
T+2h: ETL tries to import, fails on enum validation
T+2h+30m: Manual retry by ops team
T+3h+30m: Retry succeeds but original job already started - DUPLICATE
T+4h: Data warehouse has duplicate order record
T+24h: Reports show 2x order volume for that period
Impact: Audit findings, manual record deletion, process rework
```

### Scenario C: Item Processing Blocked
```
Event: Fulfillment system cannot calculate weight
T+0h: Order placed, calls fulfillment API
T+15m: Fulfillment calls v2 without includeItems to get weight
T+15m+30s: Code crashes trying to iterate missing 'items'
T+30m: Order stuck in "pending" state
T+2h: Order timeout, customer contact initiated
T+3h: Issue escalated to engineering
Impact: Order fulfillment SLA miss, customer complaint
```

---

## Enum Compatibility Failure Detailed Example

### Legacy System State
```java
// Original v1 enum (3 values)
public enum OrderStatus {
  PAID,      // Order paid
  CANCELLED, // Order cancelled
  SHIPPED    // Order shipped
}

// Legacy database constraint
CREATE TABLE orders (
  status VARCHAR(20) CHECK (status IN ('PAID', 'CANCELLED', 'SHIPPED'))
);
```

### New v2 Response Introduces FULFILLED
```json
{
  "orderId": "ORD-555",
  "state": "FULFILLED",  // ← NEW value not in legacy enum
  "amount": 120.0
}
```

### Legacy Code Fails
```java
String stateFromV2 = "FULFILLED";

// Legacy code: direct enum parsing
try {
  OrderStatus status = OrderStatus.valueOf(stateFromV2);
  saveToDatabase(status);
} catch (IllegalArgumentException e) {
  // This happens!
  System.err.println("No enum constant OrderStatus.FULFILLED");
  skipRecord();  // Record lost forever
}
```

### Proper Fix (Not Deployed)
```java
// Mapping layer with fallback
String stateFromV2 = "FULFILLED";
OrderState newState = OrderState.valueOf(stateFromV2);
OrderStatus legacyStatus = mapNewStateToLegacy(newState);  // Fallback logic

private OrderStatus mapNewStateToLegacy(OrderState state) {
  return switch(state) {
    case PAID -> OrderStatus.PAID;
    case CANCELLED -> OrderStatus.CANCELLED;
    case SHIPPED -> OrderStatus.SHIPPED;
    case FULFILLED -> OrderStatus.SHIPPED;  // Business decision: treat FULFILLED as SHIPPED
  };
}
```

---

## Summary: Failure Impact Timeline

| Time | Client | Issue | Data Loss | Visibility |
|------|--------|-------|-----------|-----------|
| T+0min | All | Schema mismatch begins | None | Low |
| T+5min | Web UI | NullPointerException in rendering | None | High (user sees blank) |
| T+30min | Monitoring | 410 response triggers alert | None | Very High (PagerDuty fires) |
| T+1h | Analytics | KeyError on field access | HIGH (missed metrics) | Low (silent job failure) |
| T+2h | ETL/Batch | Enum exception, record skipped | HIGH (missing records) | Low (batch log only) |
| T+6h | Finance | Revenue metrics missing | HIGH (audit trail corrupted) | CRITICAL (CFO escalation) |

**Mitigation Window:** First 30 minutes before cascading failures become visible to business stakeholders.
