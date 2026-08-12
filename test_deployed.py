"""
Direct Test Suite for Deployed Expense Tracker on Render
Tests the live API at: https://expense-tracker-repo-vpox.onrender.com/mcp
"""

import requests
import json
from datetime import datetime

# Use the deployed Render URL
DEPLOYED_URL = "https://expense-tracker-repo-vpox.onrender.com/mcp"

class DeployedTestRunner:
    def __init__(self):
        self.results = []
        self.tokens = {}
        self.test_count = 0
        self.pass_count = 0

    def run_test(self, test_name, tool_name, params):
        """Run a single test against deployed API"""
        self.test_count += 1
        print("\n" + "="*80)
        print(f"TEST #{self.test_count}: {test_name}")
        print("="*80)

        try:
            response = self._call_tool(tool_name, params)
            print(f"[PASS] Tool executed: {tool_name}")
            print(f"Response: {json.dumps(response, indent=2)}")
            self.pass_count += 1
            self.results.append({"test": test_name, "status": "PASS", "response": response})
            return response, True
        except Exception as e:
            print(f"[FAIL] Error: {str(e)}")
            self.results.append({"test": test_name, "status": "FAIL", "error": str(e)})
            return None, False

    def _call_tool(self, tool_name, params):
        """Call tool on deployed MCP server"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": params
            }
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }

        print(f"Calling: {tool_name}")
        print(f"URL: {DEPLOYED_URL}")

        response = requests.post(DEPLOYED_URL, json=payload, headers=headers, timeout=30)

        if response.status_code != 200:
            print(f"HTTP Status: {response.status_code}")
            print(f"Response: {response.text}")

        response.raise_for_status()

        result = response.json()
        if "result" in result:
            content = result["result"]["content"][0]["text"]
            if isinstance(content, str):
                return json.loads(content)
            return content
        return result

    def print_summary(self):
        """Print test summary"""
        print("\n\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)

        for result in self.results:
            status = "[PASS]" if result["status"] == "PASS" else "[FAIL]"
            print(f"{status} {result['test']}")

        failed = self.test_count - self.pass_count
        print(f"\nTotal: {self.test_count} | Passed: {self.pass_count} | Failed: {failed}")
        if self.test_count > 0:
            print(f"Success Rate: {(self.pass_count/self.test_count*100):.1f}%")
        print("="*80 + "\n")


def run_deployed_tests():
    """Run comprehensive tests on deployed system"""
    runner = DeployedTestRunner()

    print("\n" + "="*80)
    print("EXPENSE TRACKER - DEPLOYED TEST SUITE")
    print(f"URL: {DEPLOYED_URL}")
    print("="*80)

    today = datetime.now().strftime("%Y-%m-%d")

    # ========== PHASE 1: REGISTER & LOGIN ==========
    print("\n\n[PHASE 1] AUTHENTICATION\n")

    # Test 1: Register first user
    resp, passed = runner.run_test(
        "Register User: Priya",
        "register_user",
        {
            "username": "test_priya_001",
            "password": "Test@123",
            "email": "test.priya@example.com"
        }
    )

    # Test 2: Register second user
    resp, passed = runner.run_test(
        "Register User: Ashna",
        "register_user",
        {
            "username": "test_ashna_001",
            "password": "Test@456",
            "email": "test.ashna@example.com"
        }
    )

    # Test 3: Login first user
    resp, passed = runner.run_test(
        "Login: Priya",
        "login",
        {
            "username": "test_priya_001",
            "password": "Test@123"
        }
    )

    if resp and "token" in str(resp):
        try:
            token_str = json.loads(str(resp).replace("'", '"'))["token"]
            runner.tokens["priya"] = token_str
            print(f"[TOKEN SAVED] Priya token: {token_str[:20]}...")
        except:
            print("[WARNING] Could not parse Priya token")

    # Test 4: Login second user
    resp, passed = runner.run_test(
        "Login: Ashna",
        "login",
        {
            "username": "test_ashna_001",
            "password": "Test@456"
        }
    )

    if resp and "token" in str(resp):
        try:
            token_str = json.loads(str(resp).replace("'", '"'))["token"]
            runner.tokens["ashna"] = token_str
            print(f"[TOKEN SAVED] Ashna token: {token_str[:20]}...")
        except:
            print("[WARNING] Could not parse Ashna token")

    # ========== PHASE 2: PERSONAL EXPENSES ==========
    print("\n\n[PHASE 2] PERSONAL EXPENSES\n")

    if runner.tokens.get("priya"):
        # Test 5: Add expense
        resp, passed = runner.run_test(
            "Add Expense: Priya (500 Groceries)",
            "add_expense",
            {
                "token": runner.tokens["priya"],
                "date": today,
                "amount": 500,
                "category": "Groceries",
                "subcategory": "Vegetables",
                "note": "Weekly shopping"
            }
        )

        # Test 6: List expenses
        resp, passed = runner.run_test(
            "List Expenses: Priya",
            "list_expenses",
            {
                "token": runner.tokens["priya"],
                "start_date": today,
                "end_date": today
            }
        )

        # Test 7: Search expenses
        resp, passed = runner.run_test(
            "Search Expenses: keyword 'shopping'",
            "search_expenses",
            {
                "token": runner.tokens["priya"],
                "keyword": "shopping"
            }
        )

    # ========== PHASE 3: FRIENDS ==========
    print("\n\n[PHASE 3] FRIENDS\n")

    if runner.tokens.get("priya"):
        runner.run_test(
            "Add Friend: Priya adds Ashna",
            "add_friend",
            {
                "token": runner.tokens["priya"],
                "name": "Ashna",
                "email": "test.ashna@example.com"
            }
        )

    if runner.tokens.get("ashna"):
        runner.run_test(
            "Add Friend: Ashna adds Priya",
            "add_friend",
            {
                "token": runner.tokens["ashna"],
                "name": "Priya",
                "email": "test.priya@example.com"
            }
        )

    # ========== PHASE 4: SHARED EXPENSES ==========
    print("\n\n[PHASE 4] SHARED EXPENSES\n")

    if runner.tokens.get("priya"):
        # Test: Add shared expense (equal split)
        resp, passed = runner.run_test(
            "Add Shared Expense: Priya pays 1000 (50/50 split with Ashna)",
            "add_shared_expense",
            {
                "token": runner.tokens["priya"],
                "date": today,
                "amount": 1000,
                "paid_by": "Priya",
                "participants": ["Ashna"],
                "description": "Lunch for both"
            }
        )

        # Test: List shared expenses
        resp, passed = runner.run_test(
            "List Shared Expenses: Priya",
            "list_shared_expenses",
            {
                "token": runner.tokens["priya"]
            }
        )

        # Test: Search shared expenses
        resp, passed = runner.run_test(
            "Search Shared Expenses: keyword 'lunch'",
            "search_shared_expenses",
            {
                "token": runner.tokens["priya"],
                "keyword": "lunch"
            }
        )

    # ========== PHASE 5: BALANCES & SETTLEMENTS ==========
    print("\n\n[PHASE 5] BALANCES & SETTLEMENTS\n")

    if runner.tokens.get("priya"):
        # Test: Get balances
        resp, passed = runner.run_test(
            "Get Balances: Priya",
            "get_balances",
            {
                "token": runner.tokens["priya"]
            }
        )

        # Test: Record settlement
        resp, passed = runner.run_test(
            "Record Settlement: Priya receives 500 from Ashna",
            "settle_payment",
            {
                "token": runner.tokens["priya"],
                "person": "Ashna",
                "amount": 500,
                "settlement_date": today,
                "note": "Payment for lunch"
            }
        )

        # Test: Get updated balances
        resp, passed = runner.run_test(
            "Get Balances After Settlement: Priya",
            "get_balances",
            {
                "token": runner.tokens["priya"]
            }
        )

        # Test: List settlements
        resp, passed = runner.run_test(
            "List Settlements: Priya",
            "list_settlements",
            {
                "token": runner.tokens["priya"]
            }
        )

    # ========== PHASE 6: EXPORT ==========
    print("\n\n[PHASE 6] EXPORT\n")

    if runner.tokens.get("priya"):
        resp, passed = runner.run_test(
            "Export Expenses to Excel",
            "export_expenses_to_excel",
            {
                "token": runner.tokens["priya"],
                "start_date": today,
                "end_date": today,
                "include_shared": True
            }
        )

    # ========== PRINT SUMMARY ==========
    runner.print_summary()
    return runner


if __name__ == "__main__":
    print("\n[INFO] Testing Deployed Expense Tracker")
    print(f"[INFO] URL: {DEPLOYED_URL}\n")

    try:
        runner = run_deployed_tests()
    except Exception as e:
        print(f"\n[CRITICAL ERROR] {str(e)}")
        print("\n[TIPS]")
        print("1. Make sure Render deployment is active")
        print("2. Check URL is correct")
        print("3. Wait a moment if it's sleeping (Render free tier sleeps)")
        print("4. Run again in 30 seconds if it was sleeping\n")
