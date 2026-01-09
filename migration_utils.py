"""
migration_utils.py

Small utility functions to detect and mitigate breaking API changes between
/api/v1/orders and /api/v2/orders for testing and compatibility checks.
"""
from typing import Dict, Any, List, Tuple

LEGACY_STATE_ENUM = {"PAID", "CANCELLED", "SHIPPED"}


def map_lineitems_to_items(line_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Map v2 lineItems -> v1 items (productName, qty).
    If line_items is None or not a list, returns an empty list.
    """
    if not line_items:
        return []
    mapped = []
    for li in line_items:
        mapped.append({
            "productName": li.get("name"),
            "qty": li.get("quantity")
        })
    return mapped


def map_v2_to_legacy(v2_response: Dict[str, Any], include_items_requested: bool = False,
                      fallback_state: str = "UNKNOWN") -> Dict[str, Any]:
    """Return a v1-shaped dict from a v2 response.

    Rules applied:
    - state -> status (if unknown state not in legacy enum, set to fallback_state)
    - amount -> totalPrice
    - lineItems -> items mapped by name->productName, quantity->qty
      If include_items_requested is False and lineItems is omitted, items is set to []
    - orderId preserved
    """
    res = {}
    body = v2_response.get("body", {}) if isinstance(v2_response, dict) else {}

    res["orderId"] = body.get("orderId")

    # map state -> status with enum safeguard
    state = body.get("state")
    if state is None:
        res["status"] = None
    else:
        if state in LEGACY_STATE_ENUM:
            res["status"] = state
        else:
            # unknown new enum value
            res["status"] = fallback_state

    # amount -> totalPrice
    if "amount" in body:
        res["totalPrice"] = body.get("amount")
    else:
        res["totalPrice"] = None

    # items
    line_items = body.get("lineItems")  # may be absent when includeItems not requested
    if line_items is None:
        # ensure legacy clients get an items key to avoid undefined access
        # empty list may still break clients that assume non-empty; that must be noted in compatibility report
        res["items"] = []
    else:
        res["items"] = map_lineitems_to_items(line_items)

    return res


def detect_deprecation(response: Dict[str, Any]) -> Tuple[bool, str]:
    """Detect if response indicates v1 deprecation (e.g., 410 or API_VERSION_DEPRECATED)."""
    status_code = response.get("statusCode") if isinstance(response, dict) else None
    body = response.get("body", {}) if isinstance(response, dict) else {}
    if status_code == 410:
        return True, "HTTP 410 deprecation"
    if isinstance(body, dict) and body.get("error") == "API_VERSION_DEPRECATED":
        return True, "body indicates API_VERSION_DEPRECATED"
    return False, ""


def find_compatibility_issues(v2_response: Dict[str, Any]) -> List[str]:
    """Return a list of compatibility issues found for legacy consumers."""
    issues = []
    body = v2_response.get("body", {}) if isinstance(v2_response, dict) else {}

    # renamed fields
    if "state" in body and "status" not in body:
        issues.append("renamed_field: status -> state")
    if "amount" in body and "totalPrice" not in body:
        issues.append("renamed_field: totalPrice -> amount")

    # lineItems vs items
    if "lineItems" in body and "items" not in body:
        issues.append("renamed_field: items -> lineItems")

    # missing items when includeItems not set
    if "lineItems" not in body:
        issues.append("missing_items_when_no_includeItems")

    # new enum values
    state = body.get("state")
    if state and state not in LEGACY_STATE_ENUM:
        issues.append(f"unknown_state_value: {state}")

    return issues
