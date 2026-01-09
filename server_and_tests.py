"""
Self-contained mock API server + automated tests for the v1->v2 orders migration.
Runs a local HTTP server on 127.0.0.1:8000 and executes a suite of tests that
exercise breaking changes and compatibility mappings described in the report.

No external dependencies required (uses Python 3 stdlib only).

Run: python server_and_tests.py
"""

import json
import threading
import time
import urllib.parse
import http.server
import socketserver
import urllib.request
import urllib.error
import sys

HOST = '127.0.0.1'
PORT = 8000

# --- Mock API server ---
class OrdersHandler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, status, obj):
        body = json.dumps(obj).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # reduce noise
        return

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == '/api/v1/orders':
            # New deployment marks v1 as deprecated and returns explicit metadata (HTTP 410)
            payload = {
                'error': 'API_VERSION_DEPRECATED',
                'message': 'API v1 is deprecated. Use /api/v2/orders',
                'deprecated': True,
                'recommended': '/api/v2/orders?includeItems=true'
            }
            self._send_json(410, payload)
            return

        if path == '/api/v2/orders':
            includeItems_raw = qs.get('includeItems', [None])[0]
            includeItems = False
            if includeItems_raw is not None:
                v = str(includeItems_raw).lower()
                includeItems = v in ('1', 'true', 'yes')
            # Example dataset: two orders. One uses a new 'state' value not present in v1 enums.
            orders = [
                {
                    'id': 'order-123',
                    'createdAt': '2025-12-11T10:00:00Z',
                    'state': 'FULFILLED',            # NEW state value (would break legacy enums)
                    'amount': 199.99,               # renamed from totalPrice
                },
                {
                    'id': 'order-124',
                    'createdAt': '2025-12-10T09:30:00Z',
                    'state': 'SHIPPED',
                    'amount': 49.5,
                }
            ]

            if includeItems:
                # attach lineItems (renamed structure)
                orders[0]['lineItems'] = [
                    {'name': 'Widget A', 'quantity': 2},
                    {'name': 'Widget B', 'quantity': 1}
                ]
                orders[1]['lineItems'] = [
                    {'name': 'Gadget', 'quantity': 3}
                ]
            # When includeItems is not provided or false, lineItems may be omitted entirely.
            self._send_json(200, {'orders': orders})
            return

        # unknown
        self.send_response(404)
        self.end_headers()


def run_server_in_thread():
    class ThreadedTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    httpd = ThreadedTCPServer((HOST, PORT), OrdersHandler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, t

# --- Simple HTTP helpers ---

def http_get(path, timeout=5):
    url = f'http://{HOST}:{PORT}' + path
    req = urllib.request.Request(url, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            body = resp.read().decode('utf-8')
            return status, body
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode('utf-8')
        except Exception:
            body = ''
        return e.code, body
    except Exception as ex:
        return None, str(ex)

# --- Compatibility helpers (mapping v2 -> v1) ---

LEGACY_STATES = {'PENDING', 'PROCESSING', 'SHIPPED', 'CANCELLED', 'DELIVERED'}
# Suggested mapping rules: map known states; unknown states -> FALLBACK ("UNKNOWN") or best-effort mapping
STATE_MAPPING = {
    'FULFILLED': 'DELIVERED',  # best-effort mapping for new state
    'SHIPPED': 'SHIPPED'
}


def map_v2_to_v1(order_v2, synthesize_item_placeholder=False):
    """Return a v1-like dict from a v2 order object.
    - state -> status (mapped via STATE_MAPPING; fallback to 'UNKNOWN')
    - amount -> totalPrice
    - lineItems -> items with name->productName, quantity->qty
    - if lineItems missing: items -> [] unless synthesize_item_placeholder True,
      in which case a single placeholder item is added to avoid client crashes that assume non-empty arrays.
    """
    mapped = {}
    mapped['id'] = order_v2.get('id')
    mapped['createdAt'] = order_v2.get('createdAt')
    state = order_v2.get('state')
    if state in STATE_MAPPING:
        mapped['status'] = STATE_MAPPING[state]
    else:
        mapped['status'] = 'UNKNOWN'  # explicit fallback

    mapped['totalPrice'] = order_v2.get('amount')

    lineItems = order_v2.get('lineItems')
    if lineItems is None:
        if synthesize_item_placeholder:
            mapped['items'] = [{'productName': '<items omitted>', 'qty': 0}]
        else:
            mapped['items'] = []
    else:
        mapped['items'] = [{'productName': li.get('name'), 'qty': li.get('quantity')} for li in lineItems]

    return mapped

# --- Test definitions ---

class TestResult:
    def __init__(self, name):
        self.name = name
        self.passed = False
        self.message = ''

    def set_pass(self, message=''):
        self.passed = True
        self.message = message

    def set_fail(self, message=''):
        self.passed = False
        self.message = message

    def summary(self):
        status = 'PASS' if self.passed else 'FAIL'
        return f'{status}: {self.name} - {self.message}'


def run_tests():
    results = []

    # Test 1: /api/v1/orders deprecation behavior
    t1 = TestResult('v1_deprecation_returns_410_and_deprecation_metadata')
    status, body = http_get('/api/v1/orders')
    try:
        parsed = json.loads(body)
    except Exception:
        parsed = None
    if status == 410 and parsed and parsed.get('error') == 'API_VERSION_DEPRECATED':
        t1.set_pass('v1 returns 410 with API_VERSION_DEPRECATED')
    else:
        t1.set_fail(f'Expected 410 + API_VERSION_DEPRECATED, got status={status}, body={body}')
    results.append(t1)

    # Test 2: v2 without includeItems -> renamed fields present, lineItems omitted
    t2 = TestResult('v2_without_includeItems_field_rename_and_lineItems_absent')
    status, body = http_get('/api/v2/orders')
    if status != 200:
        t2.set_fail(f'Expected 200 from v2 without includeItems, got {status}')
    else:
        parsed = json.loads(body)
        orders = parsed.get('orders', [])
        if not orders:
            t2.set_fail('v2 returned empty orders array')
        else:
            o = orders[0]
            # Check renamed fields
            if 'state' in o and 'amount' in o and 'lineItems' not in o:
                # Simulate legacy client access that expects items to exist and be non-empty
                legacy_crash = False
                try:
                    # legacy client: items always exists and non-empty
                    _ = o['items'][0]['productName']
                except Exception as ex:
                    legacy_crash = True
                if legacy_crash:
                    t2.set_pass('v2 omits lineItems; renamed fields present; legacy client would crash on missing items')
                else:
                    t2.set_fail('Unexpected: legacy-style access did not crash')
            else:
                t2.set_fail('Field rename or lineItems omission not present as expected')
    results.append(t2)

    # Test 3: v2 with includeItems=true -> has lineItems; exercise new state value vs legacy enum
    t3 = TestResult('v2_with_includeItems_new_state_enum_compatibility')
    status, body = http_get('/api/v2/orders?includeItems=true')
    if status != 200:
        t3.set_fail(f'Expected 200, got {status}')
    else:
        parsed = json.loads(body)
        orders = parsed.get('orders', [])
        unknown_states = []
        missing_lineitems = False
        for o in orders:
            if 'lineItems' not in o:
                missing_lineitems = True
            # simulate legacy enum check
            if o.get('state') not in LEGACY_STATES:
                unknown_states.append(o.get('state'))
        if missing_lineitems:
            t3.set_fail('Expected lineItems to be present when includeItems=true')
        elif unknown_states:
            t3.set_pass(f'lineItems present; but found new/unknown state values: {unknown_states} (legacy enums would fail)')
        else:
            t3.set_pass('lineItems present and all states compatible with legacy enums')
    results.append(t3)

    # Test 4: Compatibility mapping: map v2 -> v1 and check legacy-client safety
    t4 = TestResult('compatibility_layer_mapping_v2_to_v1_and_safety')
    status, body = http_get('/api/v2/orders')
    if status != 200:
        t4.set_fail(f'v2 returned {status}'); results.append(t4)
    else:
        parsed = json.loads(body)
        orders = parsed.get('orders', [])
        # mapping without synthesizing placeholder
        mapped_simple = [map_v2_to_v1(o, synthesize_item_placeholder=False) for o in orders]
        # mapping with placeholder synthesize
        mapped_safe = [map_v2_to_v1(o, synthesize_item_placeholder=True) for o in orders]

        # Simulate a legacy client that blindly reads items[0]['productName'] and expects status in known set
        def legacy_client_behavior(mapped_orders):
            try:
                first_item_name = mapped_orders[0]['items'][0]['productName']
            except Exception as ex:
                return False, f'crash_on_items_access: {ex}'
            status_ok = mapped_orders[0]['status'] in LEGACY_STATES
            if not status_ok:
                return False, f'unknown_status: {mapped_orders[0]["status"]}'
            return True, 'ok'

        ok_simple, msg_simple = legacy_client_behavior(mapped_simple)
        ok_safe, msg_safe = legacy_client_behavior(mapped_safe)

        detail = f'simple_map_ok={ok_simple} ({msg_simple}); safe_map_ok={ok_safe} ({msg_safe})'
        if not ok_simple and ok_safe:
            t4.set_pass('Mapping with synthesized placeholder prevents item-access crashes; state may still be mapped to UNKNOWN unless mapping provided. ' + detail)
        elif ok_simple and ok_safe:
            t4.set_pass('Both mappings safe (unexpected); detail: ' + detail)
        else:
            t4.set_fail('Compatibility mapping insufficient: ' + detail)
    results.append(t4)

    # Test 5: Analytics integrity: analytics expects totalPrice and status; verify mapping or detection
    t5 = TestResult('analytics_field_presence_and_mapping')
    # call v2 directly and check fields analytics expects
    status, body = http_get('/api/v2/orders')
    if status != 200:
        t5.set_fail(f'v2 returned {status}')
    else:
        parsed = json.loads(body)
        orders = parsed.get('orders', [])
        issues = []
        for o in orders:
            if 'amount' not in o:
                issues.append('missing_amount')
            if 'state' not in o:
                issues.append('missing_state')
        if issues:
            t5.set_fail('Analytics fields missing in v2: ' + ','.join(issues))
        else:
            # check mapping to analytics' expected names
            mapped = [map_v2_to_v1(o, synthesize_item_placeholder=False) for o in orders]
            analytics_ok = all(('totalPrice' in m and 'status' in m) for m in mapped)
            if analytics_ok:
                t5.set_pass('v2 contains amount/state; mapping to totalPrice/status possible')
            else:
                t5.set_fail('Mapping to analytics expected fields failed')
    results.append(t5)

    # Test 6: Monitoring false-outage: legacy monitoring expects /api/v1/orders to be 200
    t6 = TestResult('monitoring_deems_v1_deprecated_as_outage')
    status, body = http_get('/api/v1/orders')
    if status == 200:
        t6.set_fail('v1 returned 200 (no deprecation) - test expects deprecation behavior to demonstrate monitoring impact')
    else:
        # Simulate monitoring rule: consider anything !=200 an outage
        monitoring_considers_outage = (status != 200)
        if monitoring_considers_outage:
            t6.set_pass(f'Monitoring would treat v1 as outage: status={status}')
        else:
            t6.set_fail(f'Unexpected monitoring judgement for status={status}')
    results.append(t6)

    # Print human-readable transcript
    print('\n=== Automated test results ===\n')
    passed = 0
    for r in results:
        prefix = 'PASS' if r.passed else 'FAIL'
        print(f'{prefix}: {r.name}')
        if r.message:
            print(f'  -> {r.message}')
        if r.passed:
            passed += 1
    total = len(results)
    print(f"\nSummary: {passed}/{total} tests passed")

    # Exit code non-zero if any failed
    if passed != total:
        print('\nOne or more tests failed (expected: migration incompatibilities).')
        sys.exit(2)
    else:
        print('\nAll tests passed.')
        sys.exit(0)


if __name__ == '__main__':
    print('Starting mock API server on http://%s:%d' % (HOST, PORT))
    httpd, thread = run_server_in_thread()
    # give server a moment
    time.sleep(0.15)
    try:
        run_tests()
    finally:
        print('\nShutting down server...')
        httpd.shutdown()
        httpd.server_close()
        time.sleep(0.05)
