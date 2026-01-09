# API Call Examples: v1 vs v2 Migration

## 1. GET /api/v1/orders (Legacy - Stable)

### Request
```http
GET /api/v1/orders?userId=123 HTTP/1.1
Host: api.example.com
X-Client: legacy-web
Accept: application/json
```

### Response
```json
{
  "orderId": "ORD-123",
  "status": "PAID",
  "totalPrice": 199.99,
  "items": [
    {
      "productName": "Laptop",
      "qty": 1
    },
    {
      "productName": "Mouse",
      "qty": 2
    }
  ],
  "createdAt": "2024-01-15T10:30:00Z"
}
```

**Characteristics:**
- `status` field (not `state`)
- `totalPrice` field (not `amount`)
- `items` array always present (even if empty)
- Item properties: `productName`, `qty`
- Status values: `PAID`, `CANCELLED`, `SHIPPED`
- Always returns HTTP 200

---

## 2. GET /api/v2/orders (Without includeItems)

### Request
```http
GET /api/v2/orders?userId=123 HTTP/1.1
Host: api.example.com
X-Client: legacy-web
Accept: application/json
```

### Response
```json
{
  "orderId": "ORD-123",
  "state": "PAID",
  "amount": 199.99,
  "createdAt": "2024-01-15T10:30:00Z"
}
```

**Characteristics:**
- `state` field (renamed from `status`)
- `amount` field (renamed from `totalPrice`)
- **`lineItems` is completely omitted** (not included in response)
- Default `includeItems=false` suppresses item details
- **BREAKING CHANGE**: Legacy code expecting `items[]` will get `undefined`

---

## 3. GET /api/v2/orders (With includeItems=true)

### Request
```http
GET /api/v2/orders?userId=123&includeItems=true HTTP/1.1
Host: api.example.com
X-Client: legacy-web
Accept: application/json
```

### Response
```json
{
  "orderId": "ORD-123",
  "state": "PAID",
  "amount": 199.99,
  "lineItems": [
    {
      "name": "Laptop",
      "quantity": 1
    },
    {
      "name": "Mouse",
      "quantity": 2
    }
  ],
  "createdAt": "2024-01-15T10:30:00Z"
}
```

**Characteristics:**
- `state` field (renamed from `status`)
- `amount` field (renamed from `totalPrice`)
- `lineItems` array present (when `includeItems=true`)
- Item properties: `name`, `quantity` (renamed from `productName`, `qty`)
- **BREAKING CHANGE**: Field renaming breaks direct property access
- **BREAKING CHANGE**: `lineItems` key name differs from `items`

---

## 4. New State Value Example (FULFILLED)

### Request
```http
GET /api/v2/orders?userId=555&includeItems=true HTTP/1.1
Host: api.example.com
Accept: application/json
```

### Response (New State Value)
```json
{
  "orderId": "ORD-555",
  "state": "FULFILLED",
  "amount": 120.0,
  "lineItems": [
    {
      "name": "Book",
      "quantity": 1
    }
  ],
  "createdAt": "2024-01-10T14:20:00Z"
}
```

**Characteristics:**
- **NEW**: `FULFILLED` state value did not exist in v1
- v1 only supported: `PAID`, `CANCELLED`, `SHIPPED`
- Legacy OrderStatus enum will throw `IllegalArgumentException` when encountering `FULFILLED`

---

## 5. Deprecated v1 Endpoint Behavior

### Request (Deprecated Endpoint)
```http
GET /api/v1/orders?userId=999 HTTP/1.1
Host: api.example.com
Accept: application/json
```

### Response (Deprecation Notice)
```json
HTTP/1.1 410 Gone

{
  "error": "API_VERSION_DEPRECATED",
  "message": "Please migrate to /api/v2/orders",
  "supportedVersion": "v2",
  "migrationGuide": "https://docs.example.com/api/v2-migration"
}
```

**Characteristics:**
- Returns HTTP 410 (Gone) instead of 200
- Legacy monitoring expects HTTP 200 and treats 410 as outage
- **BREAKING CHANGE**: Monitoring will fire false alarms

---

## 6. Schema Comparison Table

| Aspect | v1 (/api/v1/orders) | v2 (/api/v2/orders) | Breaking? |
|--------|-------------------|-------------------|-----------|
| Status Field | `status` | `state` | ✓ YES - Field renamed |
| Price Field | `totalPrice` | `amount` | ✓ YES - Field renamed |
| Items Container | `items` | `lineItems` | ✓ YES - Field renamed |
| Item Name | `productName` | `name` | ✓ YES - Field renamed |
| Item Quantity | `qty` | `quantity` | ✓ YES - Field renamed |
| Items Default | Always present | **Omitted by default** | ✓ YES - Conditional inclusion |
| Control Parameter | N/A | `includeItems` query param | ✓ NEW - Clients must adapt |
| Status Values | PAID, CANCELLED, SHIPPED | PAID, CANCELLED, SHIPPED, **FULFILLED** | ✓ YES - New enum value |
| HTTP on Deprecation | 200 OK | 410 Gone | ✓ YES - Status code change |

---

## Summary of Breaking Changes

1. **Field Renames**: `status`→`state`, `totalPrice`→`amount`, `items`→`lineItems`
2. **Nested Field Renames**: `productName`→`name`, `qty`→`quantity`
3. **Conditional Item Inclusion**: `lineItems` omitted unless `includeItems=true`
4. **New Enum Value**: `FULFILLED` state not in v1 OrderStatus enum
5. **Deprecation Signal**: v1 endpoint returns HTTP 410 instead of 200
6. **Query Parameter Requirement**: v2 requires understanding of `includeItems` behavior
