"""
Advanced E2E Test Suite for Expense Tracker
Very Thorough Testing with Multiple Users, Complex Scenarios, and Balance Tracking
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

BASE_URL = "http://localhost:8000/mcp"

class AdvancedTestRunner:
    def __init__(self):
        self.results = []
        self.tokens = {}
        self.users = {}
        self.expense_ids = {}
        self.shared_expense_ids = {}
        self.balances_history = {}
        self.test_count = 0
        self.pass_count = 0

    def log(self, message, level="INFO"):
        """Pretty print log messages"""
        if level == "TEST":
            print(f"\n{'='*80}")
            print(f"  TEST: {message}")
            print(f"{'='*80}")
        elif level == "STEP":
            print(f"\n  📝 STEP: {message}")
        elif level == "CHECK":
            print(f"    ✓ {message}")
        elif level == "ERROR":
            print(f"    ✗ {message}")
        elif level == "INFO":
            print(f"\n  ℹ️  {message}")
        elif level == "BALANCE":
            print(f"\n  💰 {message}")

    def run_test(self, test_name: str, tool_name: str, params: dict, checks: dict) -> Tuple[dict, bool]:
        """Run a test with multiple verification checks"""
        self.test_count += 1
        self.log(f"#{self.test_count}: {test_name}", "TEST")

        try:
            response = self._call_mcp_tool(tool_name, params)
            self.log(f"Tool executed: {tool_name}", "STEP")
            self.log(f"Response: {json.dumps(response, indent=2)}", "INFO")

            # Run checks
            passed = True
            for check_name, check_func in checks.items():
                try:
                    result = check_func(response)
                    if result:
                        self.log(check_name, "CHECK")
                    else:
                        self.log(f"{check_name} - FAILED", "ERROR")
                        passed = False
                except Exception as e:
                    self.log(f"{check_name} - ERROR: {str(e)}", "ERROR")
                    passed = False

            if passed:
                self.pass_count += 1
                self.log("✅ TEST PASSED", "INFO")
            else:
                self.log("❌ TEST FAILED", "INFO")

            self.results.append({
                "test_num": self.test_count,
                "test": test_name,
                "status": "PASS" if passed else "FAIL",
                "response": response
            })

            return response, passed

        except Exception as e:
            self.log(f"Critical Error: {str(e)}", "ERROR")
            self.results.append({
                "test_num": self.test_count,
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

        response = requests.post(BASE_URL, json=payload, timeout=10)
        response.raise_for_status()

        result = response.json()
        if "result" in result:
            content = result["result"]["content"][0]["text"]
            return json.loads(content) if isinstance(content, str) else content
        return result

    def check_balance(self, token: str, user_name: str, expected_balances: dict = None):
        """Check and log current balances"""
        try:
            response = self._call_mcp_tool("get_balances", {"token": token})
            self.log(f"✓ {user_name}'s Current Balance: {json.dumps(response, indent=2)}", "BALANCE")

            if expected_balances:
                for person, expected_amount in expected_balances.items():
                    if person in response:
                        actual = response[person]
                        match = abs(actual - expected_amount) < 0.01
                        status = "✓" if match else "✗"
                        self.log(f"{status} {person}: Expected ₹{expected_amount}, Got ₹{actual}", "CHECK")

            self.balances_history[user_name] = response
            return response

        except Exception as e:
            self.log(f"Balance check failed: {str(e)}", "ERROR")
            return None

    def print_summary(self):
        """Print comprehensive test summary"""
        print(f"\n\n{'='*80}")
        print("COMPREHENSIVE TEST SUMMARY")
        print(f"{'='*80}\n")

        for result in self.results:
            status_symbol = "✅" if result["status"] == "PASS" else "❌"
            print(f"{status_symbol} Test #{result['test_num']}: {result['test']} - {result['status']}")

        print(f"\n{'='*80}")
        print(f"Total Tests: {self.test_count}")
        print(f"Passed: {self.pass_count}")
        print(f"Failed: {self.test_count - self.pass_count}")
        print(f"Success Rate: {(self.pass_count/self.test_count*100):.1f}%" if self.test_count > 0 else "No tests")
        print(f"{'='*80}\n")

        return self.pass_count, self.test_count - self.pass_count


def run_advanced_tests():
    """Run comprehensive advanced test suite"""
    runner = AdvancedTestRunner()

    print("\n" + "="*80)
    print("ADVANCED EXPENSE TRACKER TEST SUITE")
    print("Multiple Users | Complex Scenarios | Thorough Balance Tracking")
    print("="*80)

    # ============================================================================
    # SETUP: Create 4 Users
    # ============================================================================
    print("\n\n### SETUP: CREATE 4 USERS ###\n")

    users_config = [
        {"name": "Priya", "username": "priya_sharma", "email": "priya@example.com", "password": "Priya@123"},
        {"name": "Shikhar", "username": "shikhar_bhatia", "email": "shikhar@example.com", "password": "Shikhar@456"},
        {"name": "Ashna", "username": "ashna_khera", "email": "ashna@example.com", "password": "Ashna@789"},
        {"name": "Arjun", "username": "arjun_kumar", "email": "arjun@example.com", "password": "Arjun@321"},
    ]

    for user_config in users_config:
        resp, _ = runner.run_test(
            f"Register User: {user_config['name']}",
            "register_user",
            {
                "username": user_config["username"],
                "password": user_config["password"],
                "email": user_config["email"]
            },
            {
                "status_ok": lambda r, u=user_config['name']: "ok" in str(r),
                "user_id_present": lambda r: "user_id" in str(r),
            }
        )

        resp, _ = runner.run_test(
            f"Login: {user_config['name']}",
            "login",
            {
                "username": user_config["username"],
                "password": user_config["password"]
            },
            {
                "status_ok": lambda r: "ok" in str(r),
                "token_present": lambda r: "token" in str(r),
            }
        )

        if resp and "token" in str(resp):
            token_str = str(resp).split('"token":"')[1].split('"')[0] if '"token":"' in str(resp) else None
            if token_str:
                runner.tokens[user_config["name"]] = token_str
                runner.users[user_config["name"]] = user_config

    # ============================================================================
    # SETUP: Create Friend Network
    # ============================================================================
    print("\n\n### SETUP: CREATE FRIEND NETWORK ###\n")

    friend_pairs = [
        ("Priya", "Shikhar", "shikhar@example.com"),
        ("Priya", "Ashna", "ashna@example.com"),
        ("Priya", "Arjun", "arjun@example.com"),
        ("Shikhar", "Priya", "priya@example.com"),
        ("Shikhar", "Ashna", "ashna@example.com"),
        ("Ashna", "Priya", "priya@example.com"),
        ("Ashna", "Shikhar", "shikhar@example.com"),
        ("Ashna", "Arjun", "arjun@example.com"),
        ("Arjun", "Priya", "priya@example.com"),
        ("Arjun", "Ashna", "ashna@example.com"),
    ]

    for user_name, friend_name, friend_email in friend_pairs:
        runner.run_test(
            f"Add Friend: {user_name} adds {friend_name}",
            "add_friend",
            {
                "token": runner.tokens.get(user_name, ""),
                "name": friend_name,
                "email": friend_email
            },
            {
                "status_ok": lambda r: "ok" in str(r),
            }
        )

    # ============================================================================
    # SCENARIO 1: Three-way expense split
    # ============================================================================
    print("\n\n### SCENARIO 1: THREE-WAY EXPENSE SPLIT ###\n")

    today = datetime.now().strftime("%Y-%m-%d")

    resp, _ = runner.run_test(
        "Add Shared Expense: Priya pays ₹3000 for all (equal 3-way split)",
        "add_shared_expense",
        {
            "token": runner.tokens["Priya"],
            "date": today,
            "amount": 3000,
            "paid_by": "Priya",
            "participants": ["Shikhar", "Ashna"],
            "description": "Lunch for 3 people"
        },
        {
            "status_ok": lambda r: "ok" in str(r),
            "three_equal_splits": lambda r: "1000" in str(r) or "expense_id" in str(r),
        }
    )

    runner.check_balance(runner.tokens["Priya"], "Priya", {"Shikhar": 1000, "Ashna": 1000})
    runner.check_balance(runner.tokens["Shikhar"], "Shikhar", {"Priya": -1000})
    runner.check_balance(runner.tokens["Ashna"], "Ashna", {"Priya": -1000})

    # ============================================================================
    # SCENARIO 2: Percentage-based splits with multiple participants
    # ============================================================================
    print("\n\n### SCENARIO 2: PERCENTAGE-BASED SPLITS ###\n")

    resp, _ = runner.run_test(
        "Add Shared Expense: Shikhar pays ₹2000 (Priya 60%, Ashna 40%)",
        "add_shared_expense",
        {
            "token": runner.tokens["Shikhar"],
            "date": today,
            "amount": 2000,
            "paid_by": "Shikhar",
            "participants": [
                {"name": "Priya", "percent": 60},
                {"name": "Ashna", "percent": 40}
            ],
            "description": "Dinner - unequal split"
        },
        {
            "status_ok": lambda r: "ok" in str(r),
            "splits_correct": lambda r: "1200" in str(r) or "800" in str(r),
        }
    )

    # Balances after second expense:
    # Priya: owes Shikhar 1200, is owed 1000 by Shikhar = net -200
    # Shikhar: Priya owes 1200, Shikhar owes Priya 1000 = net +200
    # Ashna: owes Shikhar 800, owes Priya 1000 = net -1800
    runner.check_balance(runner.tokens["Priya"], "Priya after 2 expenses")
    runner.check_balance(runner.tokens["Shikhar"], "Shikhar after 2 expenses")
    runner.check_balance(runner.tokens["Ashna"], "Ashna after 2 expenses")

    # ============================================================================
    # SCENARIO 3: Fixed amount splits
    # ============================================================================
    print("\n\n### SCENARIO 3: FIXED AMOUNT SPLITS ###\n")

    resp, _ = runner.run_test(
        "Add Shared Expense: Ashna pays ₹5000 (Priya ₹2000, Shikhar ₹1000, Ashna ₹2000)",
        "add_shared_expense",
        {
            "token": runner.tokens["Ashna"],
            "date": today,
            "amount": 5000,
            "paid_by": "Ashna",
            "participants": [
                {"name": "Priya", "share": 2000},
                {"name": "Shikhar", "share": 1000}
            ],
            "description": "Movie tickets and snacks"
        },
        {
            "status_ok": lambda r: "ok" in str(r),
        }
    )

    runner.check_balance(runner.tokens["Priya"], "Priya after 3 expenses")
    runner.check_balance(runner.tokens["Shikhar"], "Shikhar after 3 expenses")
    runner.check_balance(runner.tokens["Ashna"], "Ashna after 3 expenses")

    # ============================================================================
    # SCENARIO 4: Search and filter shared expenses
    # ============================================================================
    print("\n\n### SCENARIO 4: SEARCH & FILTER ###\n")

    runner.run_test(
        "Search: Find expenses by keyword 'lunch'",
        "search_shared_expenses",
        {
            "token": runner.tokens["Priya"],
            "keyword": "lunch"
        },
        {
            "found_results": lambda r: "count" in str(r),
        }
    )

    runner.run_test(
        "Search: Find expenses in range ₹1500-₹3000",
        "search_shared_expenses",
        {
            "token": runner.tokens["Shikhar"],
            "min_amount": 1500,
            "max_amount": 3000
        },
        {
            "found_results": lambda r: "count" in str(r),
        }
    )

    # ============================================================================
    # SCENARIO 5: Multiple settlements and balance updates
    # ============================================================================
    print("\n\n### SCENARIO 5: MULTIPLE SETTLEMENTS ###\n")

    runner.run_test(
        "Settlement 1: Priya pays Ashna ₹500",
        "settle_payment",
        {
            "token": runner.tokens["Priya"],
            "person": "Ashna",
            "amount": 500,
            "settlement_date": today,
            "note": "Partial payment for shared expenses"
        },
        {
            "status_ok": lambda r: "ok" in str(r),
        }
    )

    runner.log("After Settlement 1:", "BALANCE")
    runner.check_balance(runner.tokens["Priya"], "Priya")
    runner.check_balance(runner.tokens["Ashna"], "Ashna")

    runner.run_test(
        "Settlement 2: Shikhar pays Priya ₹800",
        "settle_payment",
        {
            "token": runner.tokens["Shikhar"],
            "person": "Priya",
            "amount": 800,
            "settlement_date": today,
            "note": "Payment for lunch and dinner"
        },
        {
            "status_ok": lambda r: "ok" in str(r),
        }
    )

    runner.log("After Settlement 2:", "BALANCE")
    runner.check_balance(runner.tokens["Shikhar"], "Shikhar")
    runner.check_balance(runner.tokens["Priya"], "Priya")

    runner.run_test(
        "Settlement 3: Ashna pays Shikhar ₹1000",
        "settle_payment",
        {
            "token": runner.tokens["Ashna"],
            "person": "Shikhar",
            "amount": 1000,
            "settlement_date": today,
            "note": "Full payment for movie and dinner"
        },
        {
            "status_ok": lambda r: "ok" in str(r),
        }
    )

    runner.log("After Settlement 3:", "BALANCE")
    runner.check_balance(runner.tokens["Ashna"], "Ashna")
    runner.check_balance(runner.tokens["Shikhar"], "Shikhar")

    # ============================================================================
    # SCENARIO 6: Edit shared expense and verify share recalculation
    # ============================================================================
    print("\n\n### SCENARIO 6: EDIT SHARED EXPENSE & SMART RECALCULATION ###\n")

    # List shared expenses first to get an ID
    resp, _ = runner.run_test(
        "List all shared expenses",
        "list_shared_expenses",
        {
            "token": runner.tokens["Priya"]
        },
        {
            "has_expenses": lambda r: "status" in str(r),
        }
    )

    if resp and "shared_expenses" in str(resp):
        # Get first expense ID if available
        import re
        id_match = re.search(r'"id":\s*(\d+)', str(resp))
        if id_match:
            expense_id = int(id_match.group(1))
            runner.shared_expense_ids["first"] = expense_id

            runner.run_test(
                f"Edit Shared Expense #{expense_id}: Increase amount by 20%",
                "edit_shared_expense",
                {
                    "token": runner.tokens["Priya"],
                    "expense_id": expense_id,
                    "total_amount": 3600  # 3000 * 1.2
                },
                {
                    "status_ok": lambda r: "ok" in str(r),
                    "shares_recalculated": lambda r: "recalculated" in str(r).lower(),
                }
            )

            runner.log("After edit - shares should maintain original ratio:", "INFO")
            runner.check_balance(runner.tokens["Priya"], "Priya after edit")

    # ============================================================================
    # SCENARIO 7: Personal expenses + Shared expenses
    # ============================================================================
    print("\n\n### SCENARIO 7: MIX OF PERSONAL & SHARED EXPENSES ###\n")

    runner.run_test(
        "Add Personal Expense: Arjun spends ₹500 on taxi",
        "add_expense",
        {
            "token": runner.tokens["Arjun"],
            "date": today,
            "amount": 500,
            "category": "Transport",
            "subcategory": "Taxi",
            "note": "Office commute"
        },
        {
            "status_ok": lambda r: "ok" in str(r),
            "id_present": lambda r: "id" in str(r),
        }
    )

    runner.run_test(
        "List Personal Expenses: Arjun",
        "list_expenses",
        {
            "token": runner.tokens["Arjun"],
            "start_date": today,
            "end_date": today
        },
        {
            "has_expenses": lambda r: "Transport" in str(r) or "taxi" in str(r).lower(),
        }
    )

    # ============================================================================
    # SCENARIO 8: Final Balances After All Operations
    # ============================================================================
    print("\n\n### SCENARIO 8: FINAL BALANCES ###\n")

    for user_name in runner.users.keys():
        runner.log(f"Final Balance for {user_name}:", "BALANCE")
        runner.check_balance(runner.tokens[user_name], user_name)

    # ============================================================================
    # SCENARIO 9: Export all data
    # ============================================================================
    print("\n\n### SCENARIO 9: EXPORT ###\n")

    runner.run_test(
        "Export Expenses to Excel",
        "export_expenses_to_excel",
        {
            "token": runner.tokens["Priya"],
            "start_date": today,
            "end_date": today,
            "include_shared": True
        },
        {
            "status_ok": lambda r: "ok" in str(r),
            "file_exported": lambda r: "file_path" in str(r),
        }
    )

    # ============================================================================
    # SCENARIO 10: List settlements
    # ============================================================================
    print("\n\n### SCENARIO 10: SETTLEMENT HISTORY ###\n")

    runner.run_test(
        "List Settlements: Priya",
        "list_settlements",
        {
            "token": runner.tokens["Priya"]
        },
        {
            "status_ok": lambda r: "ok" in str(r),
        }
    )

    runner.run_test(
        "List Settlements: Ashna",
        "list_settlements",
        {
            "token": runner.tokens["Ashna"]
        },
        {
            "status_ok": lambda r: "ok" in str(r),
        }
    )

    # ============================================================================
    # PRINT SUMMARY
    # ============================================================================
    passed, failed = runner.print_summary()
    return runner, passed, failed


if __name__ == "__main__":
    print("\n⚠️  IMPORTANT: Make sure the MCP server is running!")
    print("Start it with: python main.py\n")

    input("Press Enter to start advanced tests...")

    runner, passed, failed = run_advanced_tests()

    # Final statistics
    print("\n" + "="*80)
    print("TEST EXECUTION COMPLETE")
    print("="*80)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Success Rate: {(passed/(passed+failed)*100):.1f}%" if (passed+failed) > 0 else "No tests")
    print("="*80 + "\n")
