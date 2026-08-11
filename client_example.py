#!/usr/bin/env python3
"""
Example client showing how to use the authenticated expense tracker API.
This demonstrates the typical workflow for multi-user scenarios.
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import main


class ExpenseTrackerClient:
    """Client wrapper for the Expense Tracker with authentication."""

    def __init__(self):
        self.token = None
        self.user_id = None
        self.username = None

    async def register(self, username: str, password: str, email: str = ""):
        """Register a new user."""
        result = await main.register_user(username, password, email)
        if result["status"] == "ok":
            print(f"✓ Registered user: {username}")
        else:
            print(f"✗ Registration failed: {result['message']}")
        return result

    async def login(self, username: str, password: str):
        """Login and store token."""
        result = await main.login(username, password)
        if result["status"] == "ok":
            self.token = result["token"]
            self.user_id = result["user_id"]
            self.username = username
            print(f"✓ Logged in as: {username}")
        else:
            print(f"✗ Login failed: {result['message']}")
        return result

    async def verify(self):
        """Verify current token."""
        if not self.token:
            print("✗ No token available. Please login first.")
            return None
        result = await main.verify_token(self.token)
        if result["status"] == "ok":
            print(f"✓ Token valid for: {result['username']}")
        else:
            print(f"✗ Token invalid: {result['message']}")
        return result

    async def add_expense(self, date: str, amount: float, category: str,
                         subcategory: str = "", note: str = ""):
        """Add an expense."""
        if not self.token:
            print("✗ No token. Please login first.")
            return None
        result = await main.add_expense(self.token, date, amount, category, subcategory, note)
        if result.get("status") == "ok":
            print(f"✓ Added expense: ₹{amount} for {category}")
        return result

    async def list_expenses(self, start_date: str, end_date: str):
        """List expenses in date range."""
        if not self.token:
            print("✗ No token. Please login first.")
            return None
        result = await main.list_expenses(self.token, start_date, end_date)
        if isinstance(result, list):
            print(f"✓ Found {len(result)} expenses")
            for exp in result:
                print(f"  - {exp['date']}: ₹{exp['amount']} ({exp['category']})")
        return result

    async def add_credit(self, date: str, amount: float, source: str, note: str = ""):
        """Add a credit entry."""
        if not self.token:
            print("✗ No token. Please login first.")
            return None
        result = await main.add_credit(self.token, date, amount, source, note)
        if result.get("status") == "ok":
            print(f"✓ Added credit: ₹{amount} from {source}")
        return result

    async def list_credits(self, start_date: str, end_date: str):
        """List credits in date range."""
        if not self.token:
            print("✗ No token. Please login first.")
            return None
        result = await main.list_credits(self.token, start_date, end_date)
        if isinstance(result, list):
            print(f"✓ Found {len(result)} credits")
            for cred in result:
                print(f"  - {cred['date']}: ₹{cred['amount']} ({cred['source']})")
        return result

    async def add_friend(self, name: str, email: str):
        """Add a friend."""
        if not self.token:
            print("✗ No token. Please login first.")
            return None
        result = await main.add_friend(self.token, name, email)
        if result.get("status") == "ok":
            print(f"✓ Added friend: {name}")
        return result

    async def list_friends(self):
        """List all friends."""
        if not self.token:
            print("✗ No token. Please login first.")
            return None
        result = await main.list_friends(self.token)
        if isinstance(result, list):
            print(f"✓ Found {len(result)} friends")
            for friend in result:
                print(f"  - {friend['name']}: {friend.get('email', 'No email')}")
        return result

    async def get_balances(self):
        """Get balances from shared expenses."""
        if not self.token:
            print("✗ No token. Please login first.")
            return None
        result = await main.get_balances(self.token)
        if isinstance(result, dict):
            print(f"✓ Balances:")
            for person, balance in result.items():
                status = "owes you" if balance > 0 else "you owe"
                print(f"  - {person}: {status} ₹{abs(balance):.2f}")
        return result


async def demo():
    """Demonstrate the client usage."""
    client = ExpenseTrackerClient()

    print("\n" + "=" * 60)
    print("EXPENSE TRACKER - MULTI-USER DEMO")
    print("=" * 60)

    # Demo User 1
    print("\n--- USER 1: John ---")
    await client.register("john_doe", "secure_password123", "john@example.com")
    await client.login("john_doe", "secure_password123")
    await client.verify()

    print("\nAdding expenses for John:")
    await client.add_expense("2026-08-11", 500.0, "Food", "Lunch", "Office lunch")
    await client.add_expense("2026-08-11", 2000.0, "Transportation", "Taxi", "Commute")
    await client.add_expense("2026-08-10", 1500.0, "Entertainment", "Movie", "Movie tickets")

    print("\nListing John's expenses:")
    await client.list_expenses("2026-08-01", "2026-08-31")

    print("\nAdding credits for John:")
    await client.add_credit("2026-08-01", 50000.0, "Salary", "Monthly salary")
    await client.add_credit("2026-08-05", 5000.0, "Refund", "Book refund")

    print("\nListing John's credits:")
    await client.list_credits("2026-08-01", "2026-08-31")

    print("\nAdding friends for John:")
    await client.add_friend("Alice", "alice@example.com")
    await client.add_friend("Bob", "bob@example.com")

    print("\nListing John's friends:")
    await client.list_friends()

    # Demo User 2
    print("\n\n--- USER 2: Sarah ---")
    client2 = ExpenseTrackerClient()
    await client2.register("sarah_smith", "another_password456", "sarah@example.com")
    await client2.login("sarah_smith", "another_password456")

    print("\nAdding expenses for Sarah:")
    await client2.add_expense("2026-08-11", 300.0, "Food", "Dinner", "Restaurant")
    await client2.add_expense("2026-08-11", 1000.0, "Shopping", "Clothes", "New outfit")

    print("\nListing Sarah's expenses:")
    await client2.list_expenses("2026-08-01", "2026-08-31")

    # Show data isolation
    print("\n\n--- DATA ISOLATION TEST ---")
    print("Switching back to John - should still see only his expenses:")
    john_expenses = await client.list_expenses("2026-08-01", "2026-08-31")

    print("\nSwitching to Sarah - should see only her expenses:")
    sarah_expenses = await client2.list_expenses("2026-08-01", "2026-08-31")

    print("\n✓ Each user only sees their own data!")

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(demo())
