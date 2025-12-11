API Call Evidence — realistic requests and responses

1) /api/v1/orders (legacy expectation)
Request:
GET /api/v1/orders?userId=123
Headers: X-Client: legacy-web, Accept: application/json
Response (200):
{
  "orderId": "ORD-123",
  "status": "PAID",
  "totalPrice": 199.99,
  "items": [
    { "productName": "Widget", "qty": 2 }
  ]
}

2) /api/v2/orders without includeItems (breaking change: items omitted, fields renamed)
Request:
GET /api/v2/orders?userId=123
Headers: X-Client: legacy-web, Accept: application/json
Response (200):
{
  "orderId": "ORD-123",
  "state": "PAID",
  "amount": 199.99
  // lineItems omitted because includeItems not provided
}

3) /api/v2/orders?includeItems=true (renamed fields and new lineItems shape)
Request:
GET /api/v2/orders?userId=789&includeItems=true
Headers: X-Client: legacy-web, Accept: application/json
Response (200):
{
  "orderId": "ORD-789",
  "state": "SHIPPED",
  "amount": 59.50,
  "lineItems": [
    { "name": "Pen", "quantity": 3 },
    { "name": "Notebook", "quantity": 2 }
  ]
}

4) /api/v1/orders when deprecated (monitoring misinterprets this as outage)
Request: GET /api/v1/orders?userId=999
Response (410):
Status: 410
Body:
{
  "error": "API_VERSION_DEPRECATED",
  "message": "Please migrate to /api/v2/orders"
}

5) v2 returns a new state value not present in legacy enums
GET /api/v2/orders?userId=555
Response body:
{
  "orderId": "ORD-555",
  "state": "FULFILLED",
  "amount": 120.0
}

Notes: Highlighted breaking changes
- Missing items vs present lineItems
- Renamed fields: status → state, totalPrice → amount
- New state values (FULFILLED) that legacy code cannot map into enums
- v1 deprecation (410) may be treated by monitoring as an outage