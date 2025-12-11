"""Tests for API migration compatibility between /api/v1/orders and /api/v2/orders.
These are executable as a simple script via run_tests.py for environments without pytest.
"""
import json
from pathlib import Path
from migration_utils import (map_v2_to_legacy, detect_deprecation,
                             find_compatibility_issues)

ROOT = Path(__file__).resolve().parents[1]
ERROR_CASES_PATH = ROOT / "error_case.json"


def load_error_cases():
    with ERROR_CASES_PATH.open() as f:
        j = json.load(f)
    return {c["id"]: c for c in j["error_cases"]}


def test_missing_includeItems_v2(case):
    resp = case["response"]
    issues = find_compatibility_issues(resp)
    mapped = map_v2_to_legacy(resp, include_items_requested=False)

    checks = []
    # Expect items to be absent in v2 body and compatibility issue flagged
    checks.append(("missing_items_flagged", "missing_items_when_no_includeItems" in issues))
    # Legacy mapping should provide an items key (empty list) to avoid undefined access
    checks.append(("legacy_items_provided", isinstance(mapped.get("items"), list)))
    # But empty list still causes index-based access to fail in legacy clients
    checks.append(("items_not_nonempty", len(mapped.get("items")) == 0))
    return checks


def test_analytics_uses_status_totalPrice(case):
    resp = case["response"]
    mapped = map_v2_to_legacy(resp, include_items_requested=True)
    checks = []
    # Analytics expects 'status' and 'totalPrice'
    checks.append(("status_present", "status" in mapped and mapped["status"] is not None))
    checks.append(("totalPrice_present", "totalPrice" in mapped and mapped["totalPrice"] is not None))
    return checks


def test_items_vs_lineItems_mismatch(case):
    resp = case["response"]
    mapped = map_v2_to_legacy(resp, include_items_requested=True)
    checks = []
    # Ensure items are mapped from lineItems
    if "lineItems" in resp.get("body", {}):
        checks.append(("items_mapped_len", len(mapped.get("items", [])) == len(resp["body"]["lineItems"])))
    # Validate fields in mapped items
    it = mapped.get("items", [])
    for idx, item in enumerate(it):
        checks.append((f"item_{idx}_has_productName", "productName" in item))
        checks.append((f"item_{idx}_has_qty", "qty" in item))
    return checks


def test_deprecated_v1_monitored_as_outage(case):
    resp = case["response"]
    is_deprec, reason = detect_deprecation(resp)
    checks = []
    checks.append(("detected_deprecation", is_deprec))
    checks.append(("reason_present", bool(reason)))
    return checks


def test_new_state_enum_breaks_legacy_enum(case):
    resp = case["response"]
    issues = find_compatibility_issues(resp)
    checks = []
    checks.append(("unknown_state_flagged", any(i.startswith("unknown_state_value") for i in issues)))
    mapped = map_v2_to_legacy(resp)
    checks.append(("mapped_state_fallback", mapped.get("status") == "UNKNOWN"))
    return checks
