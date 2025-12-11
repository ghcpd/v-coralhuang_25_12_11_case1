from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import json

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        data = json.dumps(obj).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        userId = qs.get('userId', ['000'])[0]
        includeItemsRaw = qs.get('includeItems', [None])[0]
        includeItems = False
        if includeItemsRaw and includeItemsRaw.lower() in ['true', '1', 'yes']:
            includeItems = True

        # v1 endpoint
        if path == '/api/v1/orders':
            resp = {
                "orderId": f"ORD-{userId}",
                "status": "PAID",
                "totalPrice": 199.99,
                "items": [
                    {"productName": "Pen", "qty": 3}
                ]
            }
            self._send(200, resp)
            return

        if path == '/api/v1/orders/deprecated':
            self._send(410, {"error": "API_VERSION_DEPRECATED", "message": "Please migrate to /api/v2/orders"})
            return

        # v2 endpoint
        if path == '/api/v2/orders':
            if userId == '123':
                resp = {"orderId": f"ORD-{userId}", "state": "PAID", "amount": 199.99}
                self._send(200, resp)
                return
            if userId == '456':
                resp = {"orderId": f"ORD-{userId}", "state": "CANCELLED", "amount": 0.0, "lineItems": []}
                self._send(200, resp)
                return
            if userId == '789':
                resp = {"orderId": f"ORD-{userId}", "state": "SHIPPED", "amount": 59.5, "lineItems": [{"name": "Pen", "quantity": 3}, {"name": "Notebook", "quantity": 2}]}
                self._send(200, resp)
                return
            if userId == '555':
                resp = {"orderId": f"ORD-{userId}", "state": "FULFILLED", "amount": 120.0}
                self._send(200, resp)
                return
            resp = {"orderId": f"ORD-{userId}", "state": "PAID", "amount": 100.0}
            if includeItems:
                resp["lineItems"] = [{"name": "Generic", "quantity": 1}]
            self._send(200, resp)
            return

        # default 404
        self._send(404, {"error": "NOT_FOUND"})

def run(server_class=HTTPServer, handler_class=Handler, port=5005):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Starting mock API server on port {port}')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()

if __name__ == '__main__':
    run()
from flask import Flask, request, jsonify
app = Flask(__name__)

# v1 returns older schema - always returns items and uses status/totalPrice
@app.route('/api/v1/orders')
def v1_orders():
    userId = request.args.get('userId', '000')
    # Demo: v1 returns a single order with items and old fields
    resp = {
        "orderId": f"ORD-{userId}",
        "status": "PAID",
        "totalPrice": 199.99,
        "items": [
            {"productName": "Pen", "qty": 3}
        ]
    }
    return jsonify(resp), 200

# v2 returns new schema. includeItems controls lineItems presence. v2 also includes a new state FULFILLED for one testcase
@app.route('/api/v2/orders')
def v2_orders():
    userId = request.args.get('userId', '000')
    includeItemsRaw = request.args.get('includeItems')
    includeItems = False
    if includeItemsRaw and includeItemsRaw.lower() in ['true','1','yes']:
        includeItems = True

    # Example responses depending on userId to differentiate cases
    if userId == '123':
        # Missing includeItems -> lineItems omitted
        resp = {
            "orderId": f"ORD-{userId}",
            "state": "PAID",
            "amount": 199.99
        }
        return jsonify(resp), 200

    if userId == '456':
        # Analytics case: include items, state CANCELLED
        resp = {
            "orderId": f"ORD-{userId}",
            "state": "CANCELLED",
            "amount": 0.0,
            "lineItems": []
        }
        return jsonify(resp), 200

    if userId == '789':
        # Items present when includeItems true, with renamed fields
        resp = {
            "orderId": f"ORD-{userId}",
            "state": "SHIPPED",
            "amount": 59.5,
            "lineItems": [
                {"name": "Pen", "quantity": 3},
                {"name": "Notebook", "quantity": 2}
            ]
        }
        return jsonify(resp), 200

    if userId == '555':
        # New state value introduced
        resp = {
            "orderId": f"ORD-{userId}",
            "state": "FULFILLED",
            "amount": 120.0
        }
        return jsonify(resp), 200

    # Generic response honoring includeItems
    resp = {
        "orderId": f"ORD-{userId}",
        "state": "PAID",
        "amount": 100.0,
    }
    if includeItems:
        resp["lineItems"] = [
            {"name": "Generic", "quantity": 1}
        ]
    return jsonify(resp), 200

# Deprecated v1 path returns 410
@app.route('/api/v1/orders/deprecated')
def v1_deprecated():
    return jsonify({"error": "API_VERSION_DEPRECATED", "message": "Please migrate to /api/v2/orders"}), 410

if __name__ == '__main__':
    app.run(port=5005)
