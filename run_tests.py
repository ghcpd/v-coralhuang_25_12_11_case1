"""Simple test runner for API migration compatibility checks.
Executes tests defined in tests/test_api_migration.py and prints a readable report.
"""
import json
from pathlib import Path
from tests.test_api_migration import (
    load_error_cases,
    test_missing_includeItems_v2,
    test_analytics_uses_status_totalPrice,
    test_items_vs_lineItems_mismatch,
    test_deprecated_v1_monitored_as_outage,
    test_new_state_enum_breaks_legacy_enum,
)

ROOT = Path(__file__).resolve().parent


def run_all():
    cases = load_error_cases()
    total = 0
    passed = 0
    results = []

    # map case ids to tests
    mapping = {
        "missing_includeItems_v2": test_missing_includeItems_v2,
        "analytics_uses_status_totalPrice": test_analytics_uses_status_totalPrice,
        "items_vs_lineItems_mismatch": test_items_vs_lineItems_mismatch,
        "deprecated_v1_monitored_as_outage": test_deprecated_v1_monitored_as_outage,
        "new_state_enum_breaks_legacy_enum": test_new_state_enum_breaks_legacy_enum,
    }

    print("Running API migration compatibility tests:\n")

    for cid, test_fn in mapping.items():
        case = cases.get(cid)
        if case is None:
            print(f"SKIP: {cid} -- case missing in fixtures")
            continue
        checks = test_fn(case)
        for name, ok in checks:
            total += 1
            status = "PASS" if ok else "FAIL"
            if ok:
                passed += 1
            print(f"{cid}: {name}: {status}")
    print("\nSummary:")
    print(f"{passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    import sys
    rc = run_all()
    sys.exit(rc)
