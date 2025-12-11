#!/usr/bin/env python3
"""
Compatibility test runner for Orders API (v1/v2 migration)
Usage: python test_api_compat.py --base-url http://localhost:8080
Exits 0 if all tests pass; exits 1 otherwise.
"""

import requests
import sys
import argparse
import json

parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default="http://localhost:8080", help="API base URL")
args = parser.parse_args()
B = args.base_url.rstrip("/")

failures = 0
warnings = 0


def log_ok(msg):
    print("PASS: " + msg)


def log_fail(msg):
    global failures
    failures += 1
    print("FAIL: " + msg)


def log_warn(msg):
    global warnings
    warnings += 1
    print("WARN: " + msg)


def check_v1_basic(userId="123"):
    r = requests.get(f"{B}/api/v1/orders", params={"userId": userId}, headers={"Accept":"application/json"})
    if r.status_code == 200:
        try:
            j = r.json()
        except Exception as e:
            log_fail(f"/api/v1 returned 200 but body not JSON: {e}")
            return
        if all(k in j for k in ("status", "totalPrice", "items")):
            log_ok("/api/v1 returns status, totalPrice and items")
        else:
            log_fail("/api/v1 missing expected fields: %s" % json.dumps(j))
    elif r.status_code == 410:
        log_warn("/api/v1 returned 410 (deprecation) - ensure monitoring & compatibility proxy")
    else:
        log_fail(f"/api/v1 returned unexpected status {r.status_code}")


def check_v2_no_items(userId="123"):
    r = requests.get(f"{B}/api/v2/orders", params={"userId": userId}, headers={"Accept":"application/json"})
    if r.status_code != 200:
        log_fail("/api/v2 no-items returned non-200: %s" % r.status_code)
        return
    try:
        j = r.json()
    except Exception as e:
        log_fail(f"/api/v2 returned non-json body: {e}")
        return
    if "state" not in j or "amount" not in j:
        log_fail("/api/v2 missing state/amount: %s" % json.dumps(j))
    else:
        log_ok("/api/v2 returned state and amount")
    # compatibility requirement: items should exist
    if "items" in j:
        if isinstance(j["items"], list):
            log_ok("Compatibility: 'items' present and array when includeItems absent")
        else:
            log_fail("'items' present but not an array")
    else:
        log_fail("Compatibility: 'items' missing when includeItems absent")


def check_v2_with_items(userId="789"):
    r = requests.get(f"{B}/api/v2/orders", params={"userId": userId, "includeItems": "true"}, headers={"Accept":"application/json"})
    if r.status_code != 200:
        log_fail("/api/v2?includeItems returned non-200: %s" % r.status_code)
        return
    try:
        j = r.json()
    except Exception as e:
        log_fail(f"/api/v2?includeItems returned non-json body: {e}")
        return
    if "lineItems" not in j:
        log_fail("/api/v2?includeItems: missing lineItems: %s" % json.dumps(j))
    else:
        log_ok("/api/v2?includeItems returned lineItems")
    # compatibility: items mapping
    if "items" in j and isinstance(j["items"], list):
        if all((isinstance(it.get("productName"), str) and isinstance(it.get("qty"), (int, float))) for it in j["items"]):
            log_ok("Compatibility: items mapping present with productName/qty")
        else:
            log_fail("Compatibility: items mapping shape incorrect: %s" % json.dumps(j.get("items")))
    else:
        log_fail("Compatibility: 'items' missing even though lineItems present")


def check_enum_handling(userId="555"):
    r = requests.get(f"{B}/api/v2/orders", params={"userId": userId}, headers={"Accept":"application/json"})
    if r.status_code != 200:
        log_fail("enum check: bad status %s" % r.status_code)
        return
    try:
        j = r.json()
    except Exception as e:
        log_fail(f"enum check: non-json body: {e}")
        return
    state = j.get("state")
    if state is None:
        log_fail("enum check: 'state' missing")
        return
    if "status" in j:
        log_ok("enum compatibility: 'status' provided")
    elif "stateLegacy" in j or "statusNormalized" in j:
        log_ok("enum compatibility via stateLegacy/statusNormalized")
    else:
        log_fail("enum compatibility missing: no status/stateLegacy; state=%s" % state)


def summary_and_exit():
    print("\nSummary: %d failure(s), %d warning(s)" % (failures, warnings))
    if failures > 0:
        print("Some compatibility checks failed. Fix them before migrating clients.")
        sys.exit(1)
    if warnings > 0:
        print("Warnings exist. Verify monitoring and consider temporary compatibility proxy.")
    print("All checks passed.")
    sys.exit(0)


if __name__ == '__main__':
    print("Running Orders API compatibility tests against", B)
    check_v1_basic()
    check_v2_no_items()
    check_v2_with_items()
    check_enum_handling()
    summary_and_exit()