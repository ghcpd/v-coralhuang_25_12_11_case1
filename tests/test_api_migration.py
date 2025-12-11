import requests
import threading
import time
import subprocess
import sys

# We'll run the Flask server in a background process and then run tests against it

def start_server():
    # start server.py using same Python executable
    proc = subprocess.Popen([sys.executable, 'server.py'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc


def stop_server(proc):
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except Exception:
        proc.kill()


BASE = 'http://127.0.0.1:5005'


def assert_equal(a, b, message):
    if a != b:
        print(f"FAIL: {message} — expected {b!r}, got {a!r}")
        return False
    print(f"PASS: {message}")
    return True


def run_tests():
    results = []

    # 1) v1 orders happy path: ensure status, totalPrice, items exist
    r = requests.get(BASE + '/api/v1/orders', params={'userId': '123'})
    results.append(assert_equal(r.status_code, 200, 'v1 status code 200'))
    body = r.json()
    results.append(assert_equal('status' in body, True, 'v1 has status field'))
    results.append(assert_equal('totalPrice' in body, True, 'v1 has totalPrice field'))
    results.append(assert_equal('items' in body, True, 'v1 has items field'))

    # 2) v2 without includeItems: items/lineItems omitted, renamed fields present
    r = requests.get(BASE + '/api/v2/orders', params={'userId': '123'})
    results.append(assert_equal(r.status_code, 200, 'v2 without includeItems returns 200'))
    body = r.json()
    results.append(assert_equal('state' in body, True, 'v2 has state'))
    results.append(assert_equal('amount' in body, True, 'v2 has amount'))
    results.append(assert_equal('lineItems' in body, False, 'v2 omits lineItems when includeItems is not true'))
    results.append(assert_equal('items' in body, False, 'v2 does not expose old `items` field'))

    # 3) v2 includeItems=true: returns lineItems and shapeshifted item fields
    r = requests.get(BASE + '/api/v2/orders', params={'userId': '789', 'includeItems': 'true'})
    results.append(assert_equal(r.status_code, 200, 'v2 includeItems=true returns 200'))
    body = r.json()
    results.append(assert_equal('lineItems' in body, True, 'v2 returns lineItems when includeItems=true'))
    if 'lineItems' in body and isinstance(body['lineItems'], list) and len(body['lineItems']) > 0:
        li = body['lineItems'][0]
        results.append(assert_equal('name' in li, True, 'lineItem contains name'))
        results.append(assert_equal('quantity' in li, True, 'lineItem contains quantity'))

    # 4) Mapping failure: legacy clients expecting `status` and `totalPrice` would not find them
    r = requests.get(BASE + '/api/v2/orders', params={'userId': '456', 'includeItems': 'true'})
    body = r.json()
    results.append(assert_equal('status' in body, False, 'v2 does not have status field'))
    results.append(assert_equal('totalPrice' in body, False, 'v2 does not have totalPrice field'))

    # 5) New state value that breaks legacy enums
    r = requests.get(BASE + '/api/v2/orders', params={'userId': '555', 'includeItems': 'false'})
    body = r.json()
    results.append(assert_equal(body.get('state'), 'FULFILLED', 'v2 introduced FULFILLED state'))

    # 6) v1 deprecated path returns 410 and API_VERSION_DEPRECATED error
    r = requests.get(BASE + '/api/v1/orders/deprecated')
    results.append(assert_equal(r.status_code, 410, 'v1 deprecated path returns 410'))
    body = r.json()
    results.append(assert_equal(body.get('error'), 'API_VERSION_DEPRECATED', 'v1 deprecated returns API_VERSION_DEPRECATED'))

    # 7) Analytics counter case: v2 returns state and amount; aggregation relying on 'status' and 'totalPrice' would fail
    r = requests.get(BASE + '/api/v2/orders', params={'userId': '456', 'includeItems': 'true'})
    body = r.json()
    results.append(assert_equal('state' in body, True, 'analytics v2 still has state'))
    results.append(assert_equal('amount' in body, True, 'analytics v2 still has amount'))

    # 8) Safety: iterate items safely in legacy client style
    # Simulate legacy UI accessing items[0].productName when lineItems present instead
    r = requests.get(BASE + '/api/v2/orders', params={'userId': '789', 'includeItems': 'true'})
    body = r.json()
    try:
        _ = body['items'][0]['productName']
        results.append(False)
        print("FAIL: legacy UI naive items access did not throw (unexpected)")
    except Exception as e:
        results.append(True)
        print("PASS: legacy UI naive items access throws as expected — {}".format(type(e).__name__))

    # Summary
    passed = sum(1 for r in results if r)
    total = len(results)
    print("\nTest summary: {}/{} passed".format(passed, total))

if __name__ == '__main__':
    # Start server, run tests, then stop
    proc = start_server()
    print('Waiting for server to start...')
    time.sleep(1)
    try:
        run_tests()
    finally:
        stop_server(proc)
        print('Server stopped')
