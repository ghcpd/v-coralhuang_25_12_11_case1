# API Migration Analysis: /api/v1/orders to /api/v2/orders

## API Call Evidence

### /api/v1/orders (Deprecated)
**Request:**
```
GET /api/v1/orders?userId=123
Headers: X-Client: legacy-web, Accept: application/json
```

**Response:**
```json
{
  "statusCode": 410,
  "body": {
    "error": "API_VERSION_DEPRECATED",
    "message": "Please migrate to /api/v2/orders"
  }
}
```
**Breaking Change:** Returns 410 instead of 200, misinterpreted as outage.

### /api/v2/orders without includeItems
**Request:**
```
GET /api/v2/orders?userId=123
Headers: X-Client: legacy-web, Accept: application/json
```

**Response:**
```json
{
  "statusCode": 200,
  "body": {
    "orderId": "ORD-123",
    "state": "PAID",
    "amount": 199.99
  }
}
```
**Breaking Changes:** 
- `status` → `state`
- `totalPrice` → `amount`
- `items` absent (no `lineItems`)

### /api/v2/orders?includeItems=true
**Request:**
```
GET /api/v2/orders?userId=123&includeItems=true
Headers: X-Client: legacy-web, Accept: application/json
```

**Response:**
```json
{
  "statusCode": 200,
  "body": {
    "orderId": "ORD-123",
    "state": "PAID",
    "amount": 199.99,
    "lineItems": [
      {"name": "Widget", "quantity": 2},
      {"name": "Gadget", "quantity": 1}
    ]
  }
}
```
**Breaking Changes:** 
- `items` → `lineItems`
- `productName` → `name`
- `qty` → `quantity`

## Overview

This document analyzes the migration from `/api/v1/orders` to `/api/v2/orders`, which introduces breaking changes affecting legacy clients. The v2 API adds new behavior and schema modifications to improve efficiency and extensibility, but at the cost of backward compatibility.

### Motivation for v2
- **Performance**: Optional inclusion of item details via `includeItems` query parameter to reduce payload size for clients that don't need items.
- **Consistency**: Renamed fields for better alignment with internal models (`status` → `state`, `totalPrice` → `amount`).
- **Extensibility**: New `state` values (e.g., `FULFILLED`) to support additional order lifecycle stages.
- **Deprecation**: Explicit deprecation of v1 to encourage migration.

### Key Compatibility Risks
- Legacy clients assume `items` array always exists and is non-empty.
- Field renames (`status`/`totalPrice`) cause missing field errors.
- New `state` values break enum mappings in old clients.
- Deprecation of v1 is misinterpreted as outages by monitoring systems.
- Absence of `lineItems` when `includeItems` is false leads to null pointer exceptions.

## Schema Comparison

### v1 Schema
```json
{
  "orderId": "string",
  "status": "string", // Enum: PAID, CANCELLED, SHIPPED
  "totalPrice": "number",
  "items": [
    {
      "productName": "string",
      "qty": "integer"
    }
  ]
}
```

### v2 Schema
```json
{
  "orderId": "string",
  "state": "string", // Enum: PAID, CANCELLED, SHIPPED, FULFILLED, ...
  "amount": "number",
  "lineItems": [ // Optional, only present if includeItems=true
    {
      "name": "string",
      "quantity": "integer"
    }
  ]
}
```

### Differences
- **Renamed Fields**:
  - `status` → `state`
  - `totalPrice` → `amount`
  - `items` → `lineItems` (and optional)
- **Removed Fields**: None explicitly, but `lineItems` may be omitted.
- **Added Fields**: None, but `lineItems` structure changed.
- **Value Changes**: `state` enum extended with new values like `FULFILLED`.
- **Behavioral Changes**: `lineItems` only included if `includeItems=true`; otherwise, absent.

### Compatibility Issues and Mapping Rules
- **Field Renames**: Clients must map `state` to `status`, `amount` to `totalPrice`.
- **Optional Items**: Clients expecting `items` must check for `lineItems` and map `name` to `productName`, `quantity` to `qty`. If absent, treat as empty array.
- **New State Values**: Clients must handle unknown states gracefully (e.g., default to a safe value or log warnings).
- **Deprecation**: Clients should migrate to v2; monitoring should ignore 410 for v1.

## Client Impact Assessment

Legacy clients fail due to unmet assumptions:

1. **Missing Fields and Null Access**: Clients accessing `order.items[0].productName` fail with `TypeError` when `lineItems` is absent or renamed.
2. **Enum Mapping Failures**: New `state` like `FULFILLED` causes `IllegalArgumentException` in enum parsers.
3. **Incorrect Analytics**: Renamed fields (`status` → `state`, `totalPrice` → `amount`) lead to `KeyError` and zero metrics.
4. **Monitoring Outages**: v1 returning 410 is flagged as "API down" instead of deprecated.

Each failure ties to schema changes: renames break direct access, new values break enums, optional fields break assumptions.

## Regression Test Coverage

### Test Cases
1. **Field Renaming Validation**
   - Input: v2 response with `state` and `amount`
   - Expected: Map to `status` and `totalPrice`
   - Failure: Missing `status` or `totalPrice` in mapped output

2. **IncludeItems Behavior**
   - Input: v2 without `includeItems`
   - Expected: No `lineItems` field
   - Failure: Presence of `lineItems` or error on access

3. **Item List Safety**
   - Input: v2 with `includeItems=true`
   - Expected: `lineItems` present, map to `items`
   - Failure: Null access or mismatched structure

4. **Analytics Mapping**
   - Input: v2 response
   - Expected: Correct aggregation using `state` and `amount`
   - Failure: Incorrect counters or revenue

5. **Enum Compatibility**
   - Input: v2 with `state: "FULFILLED"`
   - Expected: Handle unknown state (e.g., skip or default)
   - Failure: Exception on unknown enum

6. **V1 Deprecation**
   - Input: v1 request
   - Expected: 410 response
   - Failure: 200 response or outage alert

## How to Run Automated Tests

1. Ensure Python 3.x and `requests` library installed.
2. Run `python test_api_migration.py` (assuming a mock server or simulated responses).
3. Review PASS/FAIL output for each test case.

### Outcomes Indicating Safe Migration
- All tests PASS: Migration is backward-compatible.
- FAIL on field renames: Implement client-side mapping.
- FAIL on items: Add conditional checks.
- FAIL on enums: Update enum definitions.
- FAIL on deprecation: Update monitoring logic.