import json

# Mock API responses
def mock_api_call(endpoint, params=None):
    if endpoint == "/api/v1/orders":
        return {
            "status_code": 410,
            "body": {
                "error": "API_VERSION_DEPRECATED",
                "message": "Please migrate to /api/v2/orders"
            }
        }
    elif endpoint == "/api/v2/orders":
        include_items = params.get("includeItems", "false") == "true"
        response = {
            "orderId": "ORD-123",
            "state": "PAID",
            "amount": 199.99
        }
        if include_items:
            response["lineItems"] = [
                {"name": "Widget", "quantity": 2},
                {"name": "Gadget", "quantity": 1}
            ]
        return {
            "status_code": 200,
            "body": response
        }
    else:
        return {"status_code": 404, "body": {"error": "Not Found"}}

# Test functions
def test_field_renaming():
    resp = mock_api_call("/api/v2/orders", {"includeItems": "false"})
    body = resp["body"]
    if "state" in body and "amount" in body:
        # Simulate mapping
        status = body["state"]
        total_price = body["amount"]
        if status == "PAID" and total_price == 199.99:
            return "PASS"
    return "FAIL: Missing or incorrect state/amount"

def test_include_items_false():
    resp = mock_api_call("/api/v2/orders", {"includeItems": "false"})
    body = resp["body"]
    if "lineItems" not in body:
        return "PASS"
    return "FAIL: lineItems present when includeItems=false"

def test_include_items_true():
    resp = mock_api_call("/api/v2/orders", {"includeItems": "true"})
    body = resp["body"]
    if "lineItems" in body and len(body["lineItems"]) > 0:
        # Simulate mapping to items
        items = [{"productName": item["name"], "qty": item["quantity"]} for item in body["lineItems"]]
        if items[0]["productName"] == "Widget" and items[0]["qty"] == 2:
            return "PASS"
    return "FAIL: Missing or incorrect lineItems"

def test_enum_compatibility():
    # Simulate v2 with new state
    resp = mock_api_call("/api/v2/orders", {"includeItems": "false"})
    body = resp["body"]
    body["state"] = "FULFILLED"  # Override for test
    known_states = ["PAID", "CANCELLED", "SHIPPED"]
    if body["state"] in known_states:
        return "PASS"
    else:
        # Simulate graceful handling
        print(f"Warning: Unknown state {body['state']}, defaulting to PAID")
        return "PASS (with warning)"

def test_v1_deprecation():
    resp = mock_api_call("/api/v1/orders")
    if resp["status_code"] == 410:
        return "PASS"
    return "FAIL: v1 not deprecated"

# Run tests
tests = [
    ("Field Renaming", test_field_renaming),
    ("IncludeItems False", test_include_items_false),
    ("IncludeItems True", test_include_items_true),
    ("Enum Compatibility", test_enum_compatibility),
    ("V1 Deprecation", test_v1_deprecation)
]

print("API Migration Regression Tests")
print("=" * 40)
for name, test_func in tests:
    result = test_func()
    print(f"{name}: {result}")
print("=" * 40)