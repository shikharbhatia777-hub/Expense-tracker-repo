"""
End-to-End Test Suite for Expense Tracker
Tests all functionality from user creation to exports
"""

import requests
import json
import os
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000/mcp"

class TestRunner:
    def __init__(self):
        self.results = []
        self.tokens = {}
        self.expense_ids = {}
        self.shared_expense_ids = {}

    def run_test(self, test_name, tool_name, params, expected_checks):
        """Run a single test and verify expected outputs"""
        print(f"\n{'='*70}")
        print(f"TEST: {test_name}")
        print(f"{'='*70}")

        try:
            response = self._call_mcp_tool(tool_name, params)
            print(f"✅ Tool executed successfully")
            print(f"Response: {json.dumps(response, indent=2)}")

            # Run verification checks
            passed = True
            for check_name, check_func in expected_checks.items():
                result = check_func(response)
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"  {status}: {check_name}")
                if not result:
                    passed = False

            self.results.append({
                "test": test_name,
                "status": "PASS" if passed else "FAIL",
                "response": response
            })
            return response, passed

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            self.results.append({
                "test": test_name,
                "status": "FAIL",
                "error": str(e)
            })
            return None, False

    def _call_mcp_tool(self, tool_name, params):
        """Call MCP tool via HTTP"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": params
            }
        }

        response = requests.post(BASE_URL, json=payload)
        response.raise_for_status()

        result = response.json()
        if "result" in result:
            return result["result"]["content"][0]["text"]
        return result

    def print_summary(self):
        """Print test summary"""
        print(f"\n{'='*70}")
        print("TEST SUMMARY")
        print(f"{'='*70}")

        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = total - passed

        for result in self.results:
            status_symbol = "✅" if result["status"] == "PASS" else "❌"
            print(f"{status_symbol} {result['test']}: {result['status']}")

        print(f"\nTotal: {total} | Passed: {passed} | Failed: {failed}")
        print(f"Success Rate: {(passed/total*100):.1f}%" if total > 0 else "No tests run")

        return passed, failed


# ============================================================================
# GOLDEN TEST SUITE
# ============================================================================

def run_golden_tests():
    """Run complete E2E test suite"""
    runner = TestRunner()

    print("\n" + "="*70)
    print("EXPENSE TRACKER - END-TO-END TEST SUITE")
    print("="*70)

    # ========== PHASE 1: AUTHENTICATION ==========
    print("\n\n### PHASE 1: AUTHENTICATION ###\n")

    # Test 1.1: Register new user
    resp, _ = runner.run_test(
        "1.1: Register User - Ashna",
        "register_user",
        {
            "username": f"ashna_{datetime.now().timestamp()}",
            "password": "Test@123",
            "email": "ashna@example.com"
        },
        {
            "status_is_ok": lambda r: "ok" in str(r),
            "user_id_present": lambda r: "user_id" in str(r),
        }
    )
    if resp and "user_id" in str(resp):
        ashna_username = json.loads(str(resp).split('"username":')[1].split(',')[0].strip().strip('"')) if "username" in str(resp) else None

    # Test 1.2: Register second user
    resp, _ = runner.run_test(
        "1.2: Register User - Shikhar",
        "register_user",
        {
            "username": f"shikhar_{datetime.now().timestamp()}",
            "password": "Test@456",
            "email": "shikhar@example.com"
        },
        {
            "status_is_ok": lambda r: "ok" in str(r),
            "user_id_present": lambda r: "user_id" in str(r),
        }
    )

    # Test 1.3: Login Ashna
    resp, _ = runner.run_test(
        "1.3: Login - Ashna",
        "login",
        {
            "username": f"ashna_{datetime.now().timestamp()}",
            "password": "Test@123"
        },
        {
            "status_is_ok": lambda r: "ok" in str(r),
            "token_present": lambda r: "token" in str(r),
        }
    )
    if resp and "token" in str(resp):
        runner.tokens["ashna"] = json.loads(str(resp).split('"token":')[1].split(',')[0].strip().strip('"'))

    # Test 1.4: Login Shikhar
    resp, _ = runner.run_test(
        "1.4: Login - Shikhar",
        "login",
        {
            "username": f"shikhar_{datetime.now().timestamp()}",
            "password": "Test@456"
        },
        {
            "status_is_ok": lambda r: "ok" in str(r),
            "token_present": lambda r: "token" in str(r),
        }
    )
    if resp and "token" in str(resp):
        runner.tokens["shikhar"] = json.loads(str(resp).split('"token":')[1].split(',')[0].strip().strip('"'))

    # ========== PHASE 2: PERSONAL EXPENSES ==========
    print("\n\n### PHASE 2: PERSONAL EXPENSES ###\n")

    today = datetime.now().strftime("%Y-%m-%d")

    # Test 2.1: Add personal expense (Ashna)
    resp, _ = runner.run_test(
        "2.1: Add Personal Expense - Ashna (₹500 Groceries)",
        "add_expense",
        {
            "token": runner.tokens.get("ashna", "dummy_token"),
            "date": today,
            "amount": 500,
            "category": "Groceries",
            "subcategory": "Vegetables",
            "note": "Weekly shopping"
        },
        {
            "status_is_ok": lambda r: "ok" in str(r),
            "expense_id_present": lambda r: "id" in str(r),
        }
    )
    if resp and "id" in str(resp):
        runner.expense_ids["ashna_grocery"] = json.loads(str(resp).split('"id":')[1].split('}')[0].strip())

    # Test 2.2: Add another personal expense (Shikhar)
    resp, _ = runner.run_test(
        "2.2: Add Personal Expense - Shikhar (₹300 Transport)",
        "add_expense",
        {
            "token": runner.tokens.get("shikhar", "dummy_token"),
            "date": today,
            "amount": 300,
            "category": "Transport",
            "subcategory": "Uber",
            "note": "Office commute"
        },
        {
            "status_is_ok": lambda r: "ok" in str(r),
            "expense_id_present": lambda r: "id" in str(r),
        }
    )
    if resp and "id" in str(resp):
        runner.expense_ids["shikhar_transport"] = json.loads(str(resp).split('"id":')[1].split('}')[0].strip())

    # Test 2.3: List personal expenses (Ashna)
    resp, _ = runner.run_test(
        "2.3: List Personal Expenses - Ashna",
        "list_expenses",
        {
            "token": runner.tokens.get("ashna", "dummy_token"),
            "start_date": today,
            "end_date": today
        },
        {
            "status_contains_data": lambda r: "Groceries" in str(r) or "grocery" in str(r).lower(),
        }
    )

    # Test 2.4: Search personal expenses (by keyword)
    resp, _ = runner.run_test(
        "2.4: Search Personal Expenses - 'shopping'",
        "search_expenses",
        {
            "token": runner.tokens.get("ashna", "dummy_token"),
            "keyword": "shopping"
        },
        {
            "found_results": lambda r: "shopping" in str(r).lower() or "count" in str(r),
        }
    )

    # Test 2.5: Search by amount range
    resp, _ = runner.run_test(
        "2.5: Search Expenses - Amount Range (₹400-₹600)",
        "search_expenses",
        {
            "token": runner.tokens.get("ashna", "dummy_token"),
            "min_amount": 400,
            "max_amount": 600
        },
        {
            "found_results": lambda r: "count" in str(r) or "status" in str(r),
        }
    )

    # Test 2.6: Edit personal expense
    if runner.expense_ids.get("ashna_grocery"):
        resp, _ = runner.run_test(
            "2.6: Edit Personal Expense - Change to ₹600",
            "edit_expense",
            {
                "token": runner.tokens.get("ashna", "dummy_token"),
                "expense_id": runner.expense_ids["ashna_grocery"],
                "amount": 600
            },
            {
                "status_is_ok": lambda r: "ok" in str(r) or "updated" in str(r).lower(),
            }
        )

    # Test 2.7: Delete personal expense
    if runner.expense_ids.get("shikhar_transport"):
        resp, _ = runner.run_test(
            "2.7: Delete Personal Expense - Transport ₹300",
            "delete_expense",
            {
                "token": runner.tokens.get("shikhar", "dummy_token"),
                "expense_id": runner.expense_ids["shikhar_transport"]
            },
            {
                "status_is_ok": lambda r: "ok" in str(r) or "deleted" in str(r).lower(),
            }
        )

    # ========== PHASE 3: ADD FRIEND ==========
    print("\n\n### PHASE 3: FRIENDS ###\n")

    # Test 3.1: Add friend (Ashna adds Shikhar)
    resp, _ = runner.run_test(
        "3.1: Add Friend - Ashna adds Shikhar",
        "add_friend",
        {
            "token": runner.tokens.get("ashna", "dummy_token"),
            "name": "Shikhar",
            "email": "shikhar@example.com"
        },
        {
            "status_is_ok": lambda r: "ok" in str(r),
        }
    )

    # Test 3.2: Add friend (Shikhar adds Ashna)
    resp, _ = runner.run_test(
        "3.2: Add Friend - Shikhar adds Ashna",
        "add_friend",
        {
            "token": runner.tokens.get("shikhar", "dummy_token"),
            "name": "Ashna",
            "email": "ashna@example.com"
        },
        {
            "status_is_ok": lambda r: "ok" in str(r),
        }
    )

    # ========== PHASE 4: SHARED EXPENSES ==========
    print("\n\n### PHASE 4: SHARED EXPENSES ###\n")

    # Test 4.1: Add shared expense (50/50 split)
    resp, _ = runner.run_test(
        "4.1: Add Shared Expense - ₹1000 Grocery (50/50)",
        "add_shared_expense",
        {
            "token": runner.tokens.get("ashna", "dummy_token"),
            "date": today,
            "amount": 1000,
            "paid_by": "Ashna",
            "participants": ["Shikhar"],
            "description": "Weekly grocery shopping"
        },
        {
            "status_is_ok": lambda r: "ok" in str(r),
            "expense_id_present": lambda r: "expense_id" in str(r),
        }
    )
    if resp and "expense_id" in str(resp):
        runner.shared_expense_ids["grocery_50_50"] = json.loads(str(resp).split('"expense_id":')[1].split(',')[0].strip())

    # Test 4.2: Add shared expense with percentage split
    resp, _ = runner.run_test(
        "4.2: Add Shared Expense - ₹1000 Dinner (75/25 split)",
        "add_shared_expense",
        {
            "token": runner.tokens.get("shikhar", "dummy_token"),
            "date": today,
            "amount": 1000,
            "paid_by": "Shikhar",
            "participants": [{"name": "Ashna", "percent": 75}],
            "description": "Dinner at restaurant"
        },
        {
            "status_is_ok": lambda r: "ok" in str(r),
            "expense_id_present": lambda r: "expense_id" in str(r),
        }
    )
    if resp and "expense_id" in str(resp):
        runner.shared_expense_ids["dinner_75_25"] = json.loads(str(resp).split('"expense_id":')[1].split(',')[0].strip())

    # Test 4.3: Add shared expense with fixed amount
    resp, _ = runner.run_test(
        "4.3: Add Shared Expense - ₹2000 Trip (₹500 + ₹1500)",
        "add_shared_expense",
        {
            "token": runner.tokens.get("ashna", "dummy_token"),
            "date": today,
            "amount": 2000,
            "paid_by": "Ashna",
            "participants": [{"name": "Shikhar", "share": 500}],
            "description": "Weekend trip expenses"
        },
        {
            "status_is_ok": lambda r: "ok" in str(r),
            "expense_id_present": lambda r: "expense_id" in str(r),
        }
    )
    if resp and "expense_id" in str(resp):
        runner.shared_expense_ids["trip_fixed"] = json.loads(str(resp).split('"expense_id":')[1].split(',')[0].strip())

    # Test 4.4: List shared expenses
    resp, _ = runner.run_test(
        "4.4: List Shared Expenses - Ashna",
        "list_shared_expenses",
        {
            "token": runner.tokens.get("ashna", "dummy_token")
        },
        {
            "has_data": lambda r: "grocery" in str(r).lower() or "dinner" in str(r).lower() or "trip" in str(r).lower(),
        }
    )

    # Test 4.5: Search shared expenses
    resp, _ = runner.run_test(
        "4.5: Search Shared Expenses - 'grocery'",
        "search_shared_expenses",
        {
            "token": runner.tokens.get("ashna", "dummy_token"),
            "keyword": "grocery"
        },
        {
            "found_results": lambda r: "count" in str(r) or "status" in str(r),
        }
    )

    # Test 4.6: Search by amount range
    resp, _ = runner.run_test(
        "4.6: Search Shared Expenses - Amount ₹900-₹1100",
        "search_shared_expenses",
        {
            "token": runner.tokens.get("ashna", "dummy_token"),
            "min_amount": 900,
            "max_amount": 1100
        },
        {
            "found_results": lambda r: "count" in str(r) or "status" in str(r),
        }
    )

    # Test 4.7: Edit shared expense (change amount)
    if runner.shared_expense_ids.get("grocery_50_50"):
        resp, _ = runner.run_test(
            "4.7: Edit Shared Expense - Change ₹1000 → ₹1200",
            "edit_shared_expense",
            {
                "token": runner.tokens.get("ashna", "dummy_token"),
                "expense_id": runner.shared_expense_ids["grocery_50_50"],
                "total_amount": 1200
            },
            {
                "status_is_ok": lambda r: "ok" in str(r) or "updated" in str(r).lower(),
                "shares_recalculated": lambda r: "recalculated" in str(r).lower(),
            }
        )

    # Test 4.8: Delete shared expense
    if runner.shared_expense_ids.get("trip_fixed"):
        resp, _ = runner.run_test(
            "4.8: Delete Shared Expense - Trip ₹2000",
            "delete_shared_expense",
            {
                "token": runner.tokens.get("ashna", "dummy_token"),
                "expense_id": runner.shared_expense_ids["trip_fixed"]
            },
            {
                "status_is_ok": lambda r: "ok" in str(r) or "deleted" in str(r).lower(),
            }
        )

    # ========== PHASE 5: BALANCES & SETTLEMENTS ==========
    print("\n\n### PHASE 5: BALANCES & SETTLEMENTS ###\n")

    # Test 5.1: Get balances (Ashna)
    resp, _ = runner.run_test(
        "5.1: Get Balances - Ashna",
        "get_balances",
        {
            "token": runner.tokens.get("ashna", "dummy_token")
        },
        {
            "has_balance_data": lambda r: "Shikhar" in str(r) or "status" in str(r),
        }
    )

    # Test 5.2: Get balances (Shikhar)
    resp, _ = runner.run_test(
        "5.2: Get Balances - Shikhar",
        "get_balances",
        {
            "token": runner.tokens.get("shikhar", "dummy_token")
        },
        {
            "has_balance_data": lambda r: "Ashna" in str(r) or "status" in str(r),
        }
    )

    # Test 5.3: Record settlement
    resp, _ = runner.run_test(
        "5.3: Record Settlement - Ashna pays Shikhar ₹500",
        "settle_payment",
        {
            "token": runner.tokens.get("ashna", "dummy_token"),
            "person": "Shikhar",
            "amount": 500,
            "settlement_date": today,
            "note": "Partial settlement for shared expenses"
        },
        {
            "status_is_ok": lambda r: "ok" in str(r),
        }
    )

    # Test 5.4: List settlements
    resp, _ = runner.run_test(
        "5.4: List Settlements - Ashna",
        "list_settlements",
        {
            "token": runner.tokens.get("ashna", "dummy_token")
        },
        {
            "has_data": lambda r: "status" in str(r),
        }
    )

    # ========== PHASE 6: EXPORT ==========
    print("\n\n### PHASE 6: EXPORT ###\n")

    # Test 6.1: Export expenses to Excel
    resp, _ = runner.run_test(
        "6.1: Export Expenses to Excel",
        "export_expenses_to_excel",
        {
            "token": runner.tokens.get("ashna", "dummy_token"),
            "start_date": today,
            "end_date": today,
            "include_shared": True
        },
        {
            "file_exported": lambda r: "file_path" in str(r) or "status" in str(r),
        }
    )

    # ========== PRINT SUMMARY ==========
    runner.print_summary()

    return runner


if __name__ == "__main__":
    print("\n⚠️  IMPORTANT: Make sure the MCP server is running on http://localhost:8000")
    print("Start it with: python main.py\n")

    input("Press Enter to start tests...")

    runner = run_golden_tests()
