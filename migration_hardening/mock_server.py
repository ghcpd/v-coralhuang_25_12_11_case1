#!/usr/bin/env python3
"""Simple Flask mock server for Orders API v1/v2 for local testing.

Endpoints:
- GET /api/v1/orders?userId=...
- GET /api/v2/orders?userId=...&includeItems=(true|false)

Behavior reflects the breaking changes described in the migration doc.
"""
from flask import Flask, request, jsonify, make_response

app = Flask(__name__)

# sample fixture data (from error_case.json)
ORDERS = {
    "123": {
        "orderId": "ORD-123",
        # v2 representation
        "state": "PAID",
        "amount": 199.99,
        "lineItems": [
            {"name": "Widget", "quantity": 2}
        ]
    },
    "456": {
        "orderId": "ORD-456",
        "state": "CANCELLED",
        "amount": 0.0,
        "lineItems": []
    },
    "789": {
        "orderId": "ORD-789",
        "state": "SHIPPED",
        "amount": 59.5,
        "lineItems": [
            {"name": "Pen", "quantity": 3},
            {"name": "Notebook", "quantity": 2}
        ]
    },
    "555": {
        "orderId": "ORD-555",
        "state": "FULFILLED",
        "amount": 120.0
    },
}


@app.route('/api/v1/orders')
def api_v1_orders():
    userId = request.args.get('userId')
    # Simulate deprecation path for userId 999
    if userId == '999':
        return make_response(jsonify({
            "error": "API_VERSION_DEPRECATED",
            "message": "Please migrate to /api/v2/orders"
        }), 410)

    # v1 returns the old schema; for simplicity, construct it from v2 fixture
    order = ORDERS.get(userId, None)
    if not order:
        return jsonify({}), 200

    # Map v2 -> v1
    items = []
    if 'lineItems' in order and order['lineItems']:
        items = [{"productName": li['name'], "qty": li['quantity']} for li in order['lineItems']]

    v1 = {
        "orderId": order['orderId'],
        "status": order['state'],
        "totalPrice": order['amount'],
        "items": items
    }
    return jsonify(v1)


@app.route('/api/v2/orders')
def api_v2_orders():
    userId = request.args.get('userId')
    includeItems = request.args.get('includeItems', 'false').lower() == 'true'
    order = ORDERS.get(userId, None)
    if not order:
        return jsonify({}), 200

    # Base v2 response
    body = {
        "orderId": order['orderId'],
        "state": order['state'],
        "amount": order['amount']
    }

    # Include lineItems only when explicitly requested
    if includeItems and 'lineItems' in order:
        body['lineItems'] = order['lineItems']

    # --- Compatibility layer additions (short-lived)
    # Provide legacy aliases so older clients keep working
    # Map state -> status and amount -> totalPrice
    legacy_states = {"PAID", "CANCELLED", "SHIPPED"}
    if order.get('state') in legacy_states:
        body['status'] = order['state']
        body['statusNormalized'] = order['state']
    else:
        # Unknown/new state (e.g., FULFILLED) — provide safe fallback and surface original
        body['status'] = "UNKNOWN"
        body['statusNormalized'] = "UNKNOWN"
        body['stateLegacy'] = order['state']

    body['totalPrice'] = order['amount']

    # Ensure 'items' array always exists for legacy clients
    if 'lineItems' in order and includeItems and order['lineItems']:
        body['items'] = [{"productName": li['name'], "qty": li['quantity']} for li in order['lineItems']]
    else:
        # If not requested or no line items, present an empty array (never null/undefined)
        body['items'] = []

    return jsonify(body)


if __name__ == '__main__':
    print('Starting mock Orders API on http://127.0.0.1:8080')
    app.run(host='127.0.0.1', port=8080, debug=False)