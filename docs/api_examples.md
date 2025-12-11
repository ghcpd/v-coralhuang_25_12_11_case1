API examples (requests and responses)

1) /api/v1/orders
Request
GET /api/v1/orders?userId=123
Headers: X-Client: legacy-web, Accept: application/json

Response (200)
{
  "orderId": "ORD-123",
  "status": "PAID",
  "totalPrice": 199.99,
  "items": [
    {"productName": "Pen", "qty": 3}
  ]
}

Notes: legacy response format. `items` always present in v1.

2) /api/v2/orders without includeItems
Request
GET /api/v2/orders?userId=123
Headers: X-Client: legacy-web, Accept: application/json

Response (200)
{
  "orderId": "ORD-123",
  "state": "PAID",
  "amount": 199.99
  // lineItems omitted because includeItems was not requested
}

Notes: Items omitted by default; callers expecting `items` will fail.

3) /api/v2/orders?includeItems=true
Request
GET /api/v2/orders?userId=789&includeItems=true
Headers: X-Client: legacy-web, Accept: application/json

Response (200)
{
  "orderId": "ORD-789",
  "state": "SHIPPED",
  "amount": 59.5,
  "lineItems": [
    { "name": "Pen", "quantity": 3 },
    { "name": "Notebook", "quantity": 2 }
  ]
}

Notes: `lineItems` present only when includeItems=true. Field names mismatched from legacy `items` shape.

4) /api/v1/orders/deprecated (monitoring)
Request
GET /api/v1/orders/deprecated
Headers: X-Client: infra-monitor, Accept: application/json

Response (410)
{
  "error": "API_VERSION_DEPRECATED",
  "message": "Please migrate to /api/v2/orders"
}

Notes: Monitoring that asserts status 200 may raise false outage alerts. Update monitoring logic or move probes to v2.
