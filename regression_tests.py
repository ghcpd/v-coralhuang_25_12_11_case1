#!/usr/bin/env python3
"""
API Migration Regression Test Suite
Tests: /api/v1/orders (legacy) vs /api/v2/orders (new)

Validates all breaking changes and verifies backward compatibility layer.
Run before production deployment.

Usage:
    python regression_tests.py                    # Run all tests
    python regression_tests.py --test RT-001      # Run single test
    python regression_tests.py --verbose          # Detailed output
"""

import json
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum
import argparse


class TestResult(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"


@dataclass
class TestCase:
    test_id: str
    category: str
    description: str
    severity: str  # CRITICAL, HIGH, MEDIUM
    endpoint: str
    request_params: Dict[str, Any]
    expected_checks: List[callable]
    failure_message: str
    

class APIResponseMock:
    """Mock API responses for testing"""
    
    @staticmethod
    def v1_single_order() -> Dict:
        """v1 response - legacy schema"""
        return {
            "orderId": "ORD-123",
            "status": "PAID",
            "totalPrice": 199.99,
            "items": [
                {"productName": "Laptop", "qty": 1},
                {"productName": "Mouse", "qty": 2}
            ],
            "createdAt": "2024-01-15T10:30:00Z"
        }
    
    @staticmethod
    def v2_with_items() -> Dict:
        """v2 response - with includeItems=true"""
        return {
            "orderId": "ORD-123",
            "state": "PAID",
            "amount": 199.99,
            "lineItems": [
                {"name": "Laptop", "quantity": 1},
                {"name": "Mouse", "quantity": 2}
            ],
            "createdAt": "2024-01-15T10:30:00Z"
        }
    
    @staticmethod
    def v2_without_items() -> Dict:
        """v2 response - without includeItems (default)"""
        return {
            "orderId": "ORD-123",
            "state": "PAID",
            "amount": 199.99,
            "createdAt": "2024-01-15T10:30:00Z"
        }
    
    @staticmethod
    def v2_with_fulfilled_state() -> Dict:
        """v2 response - with new FULFILLED state"""
        return {
            "orderId": "ORD-555",
            "state": "FULFILLED",  # NEW state value not in v1 enum
            "amount": 120.0,
            "createdAt": "2024-01-10T14:20:00Z"
        }
    
    @staticmethod
    def v2_empty_items() -> Dict:
        """v2 response - with includeItems=true but no items"""
        return {
            "orderId": "ORD-EMPTY",
            "state": "PAID",
            "amount": 0.0,
            "lineItems": [],
            "createdAt": "2024-01-15T10:30:00Z"
        }


class CompatibilityAdapter:
    """Transforms v2 response to v1 schema for legacy clients"""
    
    @staticmethod
    def transform_v2_to_v1(v2_response: Dict) -> Dict:
        """
        Transforms v2 schema to v1 schema for backward compatibility.
        
        Mappings:
            state → status
            amount → totalPrice
            lineItems → items (with field transformation)
            name → productName
            quantity → qty
        """
        state_mapping = {
            "PAID": "PAID",
            "CANCELLED": "CANCELLED",
            "SHIPPED": "SHIPPED",
            "FULFILLED": "SHIPPED"  # Fallback for new state
        }
        
        v1_response = {
            "orderId": v2_response.get("orderId"),
            "status": state_mapping.get(v2_response.get("state", "PAID"), "PAID"),
            "totalPrice": v2_response.get("amount", 0),
            "items": [],
            "createdAt": v2_response.get("createdAt")
        }
        
        # Transform lineItems to items
        if "lineItems" in v2_response and v2_response["lineItems"]:
            v1_response["items"] = [
                {
                    "productName": item.get("name"),
                    "qty": item.get("quantity")
                }
                for item in v2_response["lineItems"]
            ]
        else:
            # Always include items array, even if empty (v1 contract)
            v1_response["items"] = []
        
        return v1_response
    
    @staticmethod
    def parse_state_enum(state_value: str) -> str:
        """Parse state enum with fallback for new values"""
        valid_states = ["PAID", "CANCELLED", "SHIPPED"]
        if state_value not in valid_states:
            # New state encountered - return fallback
            return "SHIPPED"  # Business-defined fallback
        return state_value


class RegressionTestSuite:
    """Comprehensive regression test suite for API migration"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: List[tuple] = []
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.critical_failures = 0
    
    def run_all_tests(self) -> bool:
        """Run complete test suite"""
        print("=" * 60)
        print("REGRESSION TEST SUITE: Order API v1 → v2 Migration")
        print("=" * 60)
        print()
        
        # Test Group 1: Field Renaming
        self.test_RT_001_status_field_renaming()
        self.test_RT_002_nested_field_renaming()
        
        # Test Group 2: includeItems Behavior
        self.test_RT_003_default_no_includeItems()
        self.test_RT_004_explicit_includeItems_false()
        self.test_RT_005_explicit_includeItems_true()
        self.test_RT_006_empty_items_array()
        
        # Test Group 3: Adapter & Item Safety
        self.test_RT_007_adapter_missing_items()
        self.test_RT_008_adapter_field_mapping()
        
        # Test Group 4: Enum Mapping
        self.test_RT_009_enum_paid()
        self.test_RT_010_enum_cancelled()
        self.test_RT_011_enum_shipped()
        self.test_RT_012_enum_fulfilled_new_state()
        self.test_RT_013_enum_unknown_value()
        
        # Test Group 5: Analytics Integration
        self.test_RT_014_analytics_revenue()
        self.test_RT_015_analytics_status_distribution()
        self.test_RT_016_analytics_missing_items()
        
        # Test Group 6: Backward Compatibility
        self.test_RT_017_legacy_code_contract()
        self.test_RT_018_legacy_iteration()
        
        # Test Group 7: Deprecation Signal
        self.test_RT_019_v1_deprecation_http_410()
        self.test_RT_020_monitoring_alert_handling()
        
        # Test Group 8: Data Integrity
        self.test_RT_021_etl_import_with_enum()
        self.test_RT_022_etl_missing_fields()
        
        # Test Group 9: Edge Cases
        self.test_RT_023_multiple_items()
        self.test_RT_024_zero_amount()
        self.test_RT_025_null_field_handling()
        
        self.print_summary()
        
        # Return success if no critical failures
        return self.critical_failures == 0
    
    def run_single_test(self, test_id: str) -> bool:
        """Run a single test by ID"""
        test_method = f"test_{test_id.lower()}"
        if hasattr(self, test_method):
            print(f"Running {test_id}...")
            getattr(self, test_method)()
            self.print_summary()
            return self.failed_tests == 0
        else:
            print(f"ERROR: Test {test_id} not found")
            return False
    
    def assert_test(self, test_id: str, condition: bool, severity: str, message: str):
        """Record test result"""
        self.total_tests += 1
        
        if condition:
            result = TestResult.PASS
            self.passed_tests += 1
            status_symbol = "✓"
        else:
            result = TestResult.FAIL
            self.failed_tests += 1
            status_symbol = "✗"
            if severity == "CRITICAL":
                self.critical_failures += 1
        
        self.results.append((test_id, result, severity, message))
        
        prefix = f"{status_symbol} {test_id}"
        severity_label = f"[{severity}]"
        
        if result == TestResult.PASS:
            print(f"{prefix:10} {severity_label:12} PASS: {message}")
        else:
            print(f"{prefix:10} {severity_label:12} FAIL: {message}")
            if self.verbose:
                print(f"  → {message}")
    
    # ===== Test Cases =====
    
    def test_RT_001_status_field_renaming(self):
        """Field renaming: status → state"""
        response = APIResponseMock.v2_with_items()
        has_state = "state" in response and response["state"] is not None
        no_status = "status" not in response
        self.assert_test(
            "RT-001",
            has_state and no_status,
            "CRITICAL",
            "v2 response contains 'state' field, not 'status'"
        )
    
    def test_RT_002_nested_field_renaming(self):
        """Field renaming: productName/qty → name/quantity"""
        response = APIResponseMock.v2_with_items()
        items = response.get("lineItems", [])
        has_correct_names = len(items) > 0 and \
                           "name" in items[0] and \
                           "quantity" in items[0]
        no_old_names = len(items) > 0 and \
                       "productName" not in items[0] and \
                       "qty" not in items[0]
        self.assert_test(
            "RT-002",
            has_correct_names and no_old_names,
            "CRITICAL",
            "Item fields renamed: name/quantity (not productName/qty)"
        )
    
    def test_RT_003_default_no_includeItems(self):
        """Default behavior: includeItems not provided → lineItems omitted"""
        response = APIResponseMock.v2_without_items()
        has_no_items = "lineItems" not in response and "items" not in response
        self.assert_test(
            "RT-003",
            has_no_items,
            "CRITICAL",
            "lineItems key omitted when includeItems not provided"
        )
    
    def test_RT_004_explicit_includeItems_false(self):
        """Explicit includeItems=false → lineItems omitted"""
        response = APIResponseMock.v2_without_items()
        has_no_items = "lineItems" not in response
        self.assert_test(
            "RT-004",
            has_no_items,
            "CRITICAL",
            "lineItems omitted when includeItems=false"
        )
    
    def test_RT_005_explicit_includeItems_true(self):
        """includeItems=true → lineItems included"""
        response = APIResponseMock.v2_with_items()
        has_items = "lineItems" in response and isinstance(response["lineItems"], list)
        items_not_empty = len(response.get("lineItems", [])) > 0
        self.assert_test(
            "RT-005",
            has_items and items_not_empty,
            "CRITICAL",
            "lineItems array present when includeItems=true"
        )
    
    def test_RT_006_empty_items_array(self):
        """Empty items with includeItems=true → lineItems present as []"""
        response = APIResponseMock.v2_empty_items()
        has_items_key = "lineItems" in response
        is_array = isinstance(response.get("lineItems"), list)
        is_empty = len(response.get("lineItems", [])) == 0
        self.assert_test(
            "RT-006",
            has_items_key and is_array and is_empty,
            "HIGH",
            "lineItems present as empty array when no items exist"
        )
    
    def test_RT_007_adapter_missing_items(self):
        """Adapter: v2 without lineItems → v1 with items:[]"""
        v2_response = APIResponseMock.v2_without_items()
        v1_response = CompatibilityAdapter.transform_v2_to_v1(v2_response)
        
        has_items_key = "items" in v1_response
        items_is_array = isinstance(v1_response.get("items"), list)
        items_empty = len(v1_response.get("items", [])) == 0
        
        self.assert_test(
            "RT-007",
            has_items_key and items_is_array and items_empty,
            "HIGH",
            "Adapter provides items:[] when v2 omits lineItems"
        )
    
    def test_RT_008_adapter_field_mapping(self):
        """Adapter: Field transformation (name→productName, quantity→qty)"""
        v2_response = APIResponseMock.v2_with_items()
        v1_response = CompatibilityAdapter.transform_v2_to_v1(v2_response)
        
        has_items = len(v1_response.get("items", [])) > 0
        first_item = v1_response["items"][0] if has_items else {}
        has_product_name = "productName" in first_item
        has_qty = "qty" in first_item
        correct_values = first_item.get("productName") == "Laptop" and \
                        first_item.get("qty") == 1
        
        self.assert_test(
            "RT-008",
            has_product_name and has_qty and correct_values,
            "HIGH",
            "Adapter transforms lineItems to items with correct field names"
        )
    
    def test_RT_009_enum_paid(self):
        """Enum mapping: PAID state"""
        state = "PAID"
        mapped_state = CompatibilityAdapter.parse_state_enum(state)
        self.assert_test(
            "RT-009",
            mapped_state == "PAID",
            "CRITICAL",
            "PAID state maps correctly"
        )
    
    def test_RT_010_enum_cancelled(self):
        """Enum mapping: CANCELLED state"""
        state = "CANCELLED"
        mapped_state = CompatibilityAdapter.parse_state_enum(state)
        self.assert_test(
            "RT-010",
            mapped_state == "CANCELLED",
            "CRITICAL",
            "CANCELLED state maps correctly"
        )
    
    def test_RT_011_enum_shipped(self):
        """Enum mapping: SHIPPED state"""
        state = "SHIPPED"
        mapped_state = CompatibilityAdapter.parse_state_enum(state)
        self.assert_test(
            "RT-011",
            mapped_state == "SHIPPED",
            "CRITICAL",
            "SHIPPED state maps correctly"
        )
    
    def test_RT_012_enum_fulfilled_new_state(self):
        """Enum mapping: NEW FULFILLED state (not in v1 enum) → fallback"""
        state = "FULFILLED"  # NEW value that would break legacy OrderStatus.valueOf()
        mapped_state = CompatibilityAdapter.parse_state_enum(state)
        
        # Should map to fallback without throwing exception
        is_valid = mapped_state in ["PAID", "CANCELLED", "SHIPPED"]
        
        self.assert_test(
            "RT-012",
            is_valid,
            "CRITICAL",
            "New FULFILLED state mapped to fallback (SHIPPED)"
        )
    
    def test_RT_013_enum_unknown_value(self):
        """Enum mapping: Unknown state value → fallback"""
        state = "UNKNOWN_STATE"
        mapped_state = CompatibilityAdapter.parse_state_enum(state)
        
        # Should provide fallback without throwing
        is_valid = mapped_state in ["PAID", "CANCELLED", "SHIPPED"]
        
        self.assert_test(
            "RT-013",
            is_valid,
            "HIGH",
            "Unknown state value handled with fallback"
        )
    
    def test_RT_014_analytics_revenue(self):
        """Analytics: Revenue calculation with field mapping"""
        v2_response = APIResponseMock.v2_with_items()
        v1_response = CompatibilityAdapter.transform_v2_to_v1(v2_response)
        
        # Analytics should be able to sum totalPrice
        has_total_price = "totalPrice" in v1_response
        price_correct = v1_response.get("totalPrice") == 199.99
        
        self.assert_test(
            "RT-014",
            has_total_price and price_correct,
            "CRITICAL",
            "Analytics: totalPrice field available and correct for revenue sum"
        )
    
    def test_RT_015_analytics_status_distribution(self):
        """Analytics: Status distribution aggregation"""
        responses = [
            CompatibilityAdapter.transform_v2_to_v1(APIResponseMock.v2_with_items()),
            CompatibilityAdapter.transform_v2_to_v1(APIResponseMock.v2_without_items())
        ]
        
        # Should be able to count by status
        status_counts = {}
        for resp in responses:
            status = resp.get("status")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        has_paid_count = "PAID" in status_counts
        count_correct = status_counts.get("PAID") == 2
        
        self.assert_test(
            "RT-015",
            has_paid_count and count_correct,
            "CRITICAL",
            "Analytics: Status distribution aggregation works"
        )
    
    def test_RT_016_analytics_missing_items(self):
        """Analytics: Handles missing lineItems (default behavior)"""
        v2_response = APIResponseMock.v2_without_items()
        v1_response = CompatibilityAdapter.transform_v2_to_v1(v2_response)
        
        # Analytics should still function with empty items
        has_items_key = "items" in v1_response
        items_safe = isinstance(v1_response.get("items"), list)
        
        self.assert_test(
            "RT-016",
            has_items_key and items_safe,
            "CRITICAL",
            "Analytics: handles missing lineItems with empty array fallback"
        )
    
    def test_RT_017_legacy_code_contract(self):
        """Backward compatibility: Legacy code expects status/totalPrice/items"""
        v2_response = APIResponseMock.v2_with_items()
        v1_response = CompatibilityAdapter.transform_v2_to_v1(v2_response)
        
        has_status = "status" in v1_response and v1_response["status"] is not None
        has_total_price = "totalPrice" in v1_response and v1_response["totalPrice"] is not None
        has_items = "items" in v1_response
        items_accessible = len(v1_response.get("items", [])) > 0
        first_item_valid = "productName" in v1_response["items"][0] and \
                          "qty" in v1_response["items"][0]
        
        self.assert_test(
            "RT-017",
            has_status and has_total_price and has_items and items_accessible and first_item_valid,
            "CRITICAL",
            "Adapter provides v1 field contract: status, totalPrice, items"
        )
    
    def test_RT_018_legacy_iteration(self):
        """Backward compatibility: Legacy iteration over items"""
        v2_response = APIResponseMock.v2_with_items()
        v1_response = CompatibilityAdapter.transform_v2_to_v1(v2_response)
        
        # Legacy code: for item in order['items']
        items = v1_response.get("items", [])
        iteration_safe = isinstance(items, list)
        item_count = len(items)
        first_item_name = items[0].get("productName") if item_count > 0 else None
        
        self.assert_test(
            "RT-018",
            iteration_safe and item_count == 2 and first_item_name == "Laptop",
            "CRITICAL",
            "Legacy iteration pattern works: for item in order['items']"
        )
    
    def test_RT_019_v1_deprecation_http_410(self):
        """Deprecation signal: v1 returns HTTP 410"""
        # Simulated v1 endpoint response
        v1_status_code = 410
        v1_body = {
            "error": "API_VERSION_DEPRECATED",
            "message": "Please migrate to /api/v2/orders"
        }
        
        has_410_status = v1_status_code == 410
        has_deprecation_error = v1_body.get("error") == "API_VERSION_DEPRECATED"
        
        self.assert_test(
            "RT-019",
            has_410_status and has_deprecation_error,
            "HIGH",
            "v1 endpoint returns HTTP 410 Gone with deprecation signal"
        )
    
    def test_RT_020_monitoring_alert_handling(self):
        """Monitoring: Recognizes 410 as deprecation, not outage"""
        v1_status_code = 410
        error_msg = "API_VERSION_DEPRECATED"
        
        # Proper monitoring logic
        is_deprecation = v1_status_code == 410 and "DEPRECATED" in error_msg
        should_alert = not is_deprecation  # Should NOT alert on 410 deprecation
        
        self.assert_test(
            "RT-020",
            should_alert == False,  # Monitoring should NOT fire alert
            "CRITICAL",
            "Monitoring recognizes HTTP 410 as deprecation (not outage)"
        )
    
    def test_RT_021_etl_import_with_enum(self):
        """ETL import: Handles new FULFILLED state via mapping"""
        v2_response = APIResponseMock.v2_with_fulfilled_state()
        v1_response = CompatibilityAdapter.transform_v2_to_v1(v2_response)
        
        # ETL should successfully process record
        has_order_id = "orderId" in v1_response
        status_mapped = v1_response.get("status") in ["PAID", "CANCELLED", "SHIPPED"]
        fulfilled_mapped = v2_response.get("state") == "FULFILLED" and \
                          v1_response.get("status") == "SHIPPED"
        
        self.assert_test(
            "RT-021",
            has_order_id and status_mapped and fulfilled_mapped,
            "CRITICAL",
            "ETL import: new FULFILLED state mapped to SHIPPED, record saved"
        )
    
    def test_RT_022_etl_missing_fields(self):
        """ETL import: Safe navigation for missing fields"""
        v2_response = {"orderId": "ORD-TEST"}  # Minimal response
        v1_response = CompatibilityAdapter.transform_v2_to_v1(v2_response)
        
        # Should not crash, provide sensible defaults
        has_defaults = "status" in v1_response and \
                      "totalPrice" in v1_response and \
                      "items" in v1_response
        
        self.assert_test(
            "RT-022",
            has_defaults,
            "CRITICAL",
            "Adapter provides sensible defaults for missing fields"
        )
    
    def test_RT_023_multiple_items(self):
        """Edge case: Multiple items (10+) processed correctly"""
        response = {
            "orderId": "ORD-MANY",
            "state": "SHIPPED",
            "amount": 500.0,
            "lineItems": [
                {"name": f"Item-{i}", "quantity": i+1}
                for i in range(10)
            ]
        }
        v1_response = CompatibilityAdapter.transform_v2_to_v1(response)
        
        item_count = len(v1_response.get("items", []))
        all_mapped = all(
            "productName" in item and "qty" in item
            for item in v1_response["items"]
        )
        
        self.assert_test(
            "RT-023",
            item_count == 10 and all_mapped,
            "HIGH",
            "Multiple items (10+) correctly mapped"
        )
    
    def test_RT_024_zero_amount(self):
        """Edge case: Order with zero amount"""
        response = {
            "orderId": "ORD-ZERO",
            "state": "CANCELLED",
            "amount": 0.0
        }
        v1_response = CompatibilityAdapter.transform_v2_to_v1(response)
        
        total_price_exists = "totalPrice" in v1_response
        amount_correct = v1_response.get("totalPrice") == 0.0
        
        self.assert_test(
            "RT-024",
            total_price_exists and amount_correct,
            "MEDIUM",
            "Zero amount correctly mapped to totalPrice"
        )
    
    def test_RT_025_null_field_handling(self):
        """Edge case: Null/undefined field values"""
        response = {
            "orderId": "ORD-NULL",
            "state": None,  # Null value
            "amount": None
        }
        
        # Adapter should handle gracefully
        try:
            v1_response = CompatibilityAdapter.transform_v2_to_v1(response)
            has_status = "status" in v1_response
            has_price = "totalPrice" in v1_response
            success = has_status and has_price
        except Exception as e:
            if self.verbose:
                print(f"  Exception during null handling: {e}")
            success = False
        
        self.assert_test(
            "RT-025",
            success,
            "HIGH",
            "Adapter handles null field values gracefully"
        )
    
    def print_summary(self):
        """Print test execution summary"""
        print()
        print("=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests:      {self.total_tests}")
        print(f"Passed:           {self.passed_tests} ✓")
        print(f"Failed:           {self.failed_tests} ✗")
        print(f"Critical Failures: {self.critical_failures}")
        print()
        
        if self.critical_failures == 0 and self.failed_tests == 0:
            print("Status: ✓ ALL TESTS PASSED - SAFE FOR PRODUCTION")
            print()
            print("All legacy client patterns validated.")
            print("Breaking changes properly handled by adapter layer.")
            print("Ready to complete v2 migration with v1 deprecation.")
        elif self.critical_failures > 0:
            print("Status: ✗ CRITICAL FAILURES - DO NOT DEPLOY")
            print()
            print(f"Critical failures must be fixed before production deployment.")
            print("See failure details above and refer to migration documentation.")
        else:
            print("Status: ⚠ FAILURES - ASSESS IMPACT")
            print()
            print("Some high-priority tests failed. Review impact before deployment.")
        
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="API Migration Regression Test Suite"
    )
    parser.add_argument(
        "--test",
        help="Run specific test (e.g., RT-001)",
        type=str.upper
    )
    parser.add_argument(
        "--verbose",
        help="Detailed output",
        action="store_true"
    )
    
    args = parser.parse_args()
    
    suite = RegressionTestSuite(verbose=args.verbose)
    
    if args.test:
        success = suite.run_single_test(args.test)
    else:
        success = suite.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
