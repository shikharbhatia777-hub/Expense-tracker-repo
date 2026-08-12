# Expense Tracker - E2E Test Suite Documentation

## Overview
Complete end-to-end test suite covering all functionality from user registration to exports.

---

## PHASE 1: AUTHENTICATION

### Test 1.1: Register User - Ashna
**Objective:** Create a new user account

**Steps:**
1. Call `register_user` with:
   - username: "ashna_<timestamp>"
   - password: "Test@123"
   - email: "ashna@example.com"

**Expected Output:**
```json
{
  "status": "ok",
  "user_id": <number>,
  "message": "User registered successfully"
}
```

**Pass Criteria:**
- ✅ Status is "ok"
- ✅ user_id is present and numeric

---

### Test 1.2: Register User - Shikhar
**Objective:** Create second user account

**Steps:**
1. Call `register_user` with:
   - username: "shikhar_<timestamp>"
   - password: "Test@456"
   - email: "shikhar@example.com"

**Expected Output:**
```json
{
  "status": "ok",
  "user_id": <number>,
  "message": "User registered successfully"
}
```

**Pass Criteria:**
- ✅ Status is "ok"
- ✅ user_id is present

---

### Test 1.3: Login - Ashna
**Objective:** Authenticate and get JWT token

**Steps:**
1. Call `login` with:
   - username: "ashna_<timestamp>"
   - password: "Test@123"

**Expected Output:**
```json
{
  "status": "ok",
  "token": "<jwt_token>",
  "user_id": <number>,
  "message": "Login successful"
}
```

**Pass Criteria:**
- ✅ Status is "ok"
- ✅ Token is present (long string)
- ✅ user_id is present
- ⚠️ Save token for future tests

---

### Test 1.4: Login - Shikhar
**Objective:** Authenticate second user

**Steps:**
1. Call `login` with:
   - username: "shikhar_<timestamp>"
   - password: "Test@456"

**Expected Output:** Same as Test 1.3

**Pass Criteria:**
- ✅ Status is "ok"
- ✅ Token is present
- ⚠️ Save token for future tests

---

## PHASE 2: PERSONAL EXPENSES

### Test 2.1: Add Personal Expense - Ashna (₹500 Groceries)
**Objective:** Add single user expense

**Steps:**
1. Call `add_expense` with:
   - token: <ashna_token>
   - date: "2026-08-12"
   - amount: 500
   - category: "Groceries"
   - subcategory: "Vegetables"
   - note: "Weekly shopping"

**Expected Output:**
```json
{
  "status": "ok",
  "id": <expense_id>,
  "message": "Expense added"
}
```

**Pass Criteria:**
- ✅ Status is "ok"
- ✅ expense_id is present
- ⚠️ Save expense_id for edit/delete tests

---

### Test 2.2: Add Personal Expense - Shikhar (₹300 Transport)
**Objective:** Add expense as different user

**Steps:**
1. Call `add_expense` with:
   - token: <shikhar_token>
   - date: "2026-08-12"
   - amount: 300
   - category: "Transport"
   - subcategory: "Uber"
   - note: "Office commute"

**Expected Output:** Same as Test 2.1

**Pass Criteria:**
- ✅ Status is "ok"
- ✅ expense_id is present
- ⚠️ Save expense_id

---

### Test 2.3: List Personal Expenses - Ashna
**Objective:** Retrieve user's personal expenses

**Steps:**
1. Call `list_expenses` with:
   - token: <ashna_token>
   - start_date: "2026-08-12"
   - end_date: "2026-08-12"

**Expected Output:**
```json
[
  {
    "id": <number>,
    "date": "2026-08-12",
    "amount": 500,
    "category": "Groceries",
    "subcategory": "Vegetables",
    "note": "Weekly shopping"
  }
]
```

**Pass Criteria:**
- ✅ Returns array with ≥1 items
- ✅ Contains the Groceries expense
- ✅ Amount is 500
- ✅ Shikhar's Transport expense is NOT included

---

### Test 2.4: Search Personal Expenses - 'shopping'
**Objective:** Search expenses by keyword

**Steps:**
1. Call `search_expenses` with:
   - token: <ashna_token>
   - keyword: "shopping"

**Expected Output:**
```json
{
  "status": "ok",
  "count": 1,
  "expenses": [
    {
      "id": <number>,
      "description": "Weekly shopping",
      ...
    }
  ]
}
```

**Pass Criteria:**
- ✅ Status is "ok"
- ✅ count ≥ 1
- ✅ Found expense contains "shopping"

---

### Test 2.5: Search Expenses - Amount Range (₹400-₹600)
**Objective:** Filter by amount

**Steps:**
1. Call `search_expenses` with:
   - token: <ashna_token>
   - min_amount: 400
   - max_amount: 600

**Expected Output:**
```json
{
  "status": "ok",
  "count": 1,
  "expenses": [amount 500 item]
}
```

**Pass Criteria:**
- ✅ Status is "ok"
- ✅ Returns 1 item (₹500 is in range)
- ✅ Amount is between 400-600

---

### Test 2.6: Edit Personal Expense - Change to ₹600
**Objective:** Modify expense amount

**Steps:**
1. Call `edit_expense` with:
   - token: <ashna_token>
   - expense_id: <from Test 2.1>
   - amount: 600

**Expected Output:**
```json
{
  "status": "ok",
  "expense_id": <number>,
  "message": "Expense updated successfully"
}
```

**Pass Criteria:**
- ✅ Status is "ok"
- ✅ expense_id matches original
- ✅ Future list_expenses should show ₹600

---

### Test 2.7: Delete Personal Expense - Transport ₹300
**Objective:** Remove expense

**Steps:**
1. Call `delete_expense` with:
   - token: <shikhar_token>
   - expense_id: <from Test 2.2>

**Expected Output:**
```json
{
  "status": "ok",
  "message": "Expense deleted successfully",
  "deleted": {
    "id": <number>,
    "amount": 300,
    "category": "Transport"
  }
}
```

**Pass Criteria:**
- ✅ Status is "ok"
- ✅ Deleted expense details returned
- ✅ Future list_expenses should NOT show this expense

---

## PHASE 3: FRIENDS

### Test 3.1: Add Friend - Ashna adds Shikhar
**Objective:** Register friend for shared expenses

**Steps:**
1. Call `add_friend` with:
   - token: <ashna_token>
   - name: "Shikhar"
   - email: "shikhar@example.com"

**Expected Output:**
```json
{
  "status": "ok",
  "message": "Friend added"
}
```

**Pass Criteria:**
- ✅ Status is "ok"

---

### Test 3.2: Add Friend - Shikhar adds Ashna
**Objective:** Add reciprocal friend

**Steps:**
1. Call `add_friend` with:
   - token: <shikhar_token>
   - name: "Ashna"
   - email: "ashna@example.com"

**Expected Output:** Same as Test 3.1

**Pass Criteria:**
- ✅ Status is "ok"

---

## PHASE 4: SHARED EXPENSES

### Test 4.1: Add Shared Expense - ₹1000 Grocery (50/50)
**Objective:** Create shared expense with equal split

**Steps:**
1. Call `add_shared_expense` with:
   - token: <ashna_token>
   - date: "2026-08-12"
   - amount: 1000
   - paid_by: "Ashna"
   - participants: ["Shikhar"]
   - description: "Weekly grocery shopping"

**Expected Output:**
```json
{
  "status": "ok",
  "expense_id": <number>,
  "splits": [
    {"name": "Shikhar", "share": 500}
  ]
}
```

**Pass Criteria:**
- ✅ Status is "ok"
- ✅ expense_id is present
- ✅ Shikhar's share is 500 (50%)
- ⚠️ Save expense_id for edit/delete tests

---

### Test 4.2: Add Shared Expense - ₹1000 Dinner (75/25 split)
**Objective:** Create shared expense with percentage split

**Steps:**
1. Call `add_shared_expense` with:
   - token: <shikhar_token>
   - date: "2026-08-12"
   - amount: 1000
   - paid_by: "Shikhar"
   - participants: [{"name": "Ashna", "percent": 75}]
   - description: "Dinner at restaurant"

**Expected Output:**
```json
{
  "status": "ok",
  "expense_id": <number>,
  "splits": [
    {"name": "Ashna", "share": 750}
  ]
}
```

**Pass Criteria:**
- ✅ Status is "ok"
- ✅ Ashna's share is 750 (75%)
- ⚠️ Save expense_id

---

### Test 4.3: Add Shared Expense - ₹2000 Trip (₹500 + ₹1500)
**Objective:** Create shared expense with fixed amounts

**Steps:**
1. Call `add_shared_expense` with:
   - token: <ashna_token>
   - date: "2026-08-12"
   - amount: 2000
   - paid_by: "Ashna"
   - participants: [{"name": "Shikhar", "share": 500}]
   - description: "Weekend trip expenses"

**Expected Output:**
```json
{
  "status": "ok",
  "expense_id": <number>,
  "splits": [
    {"name": "Shikhar", "share": 500}
  ]
}
```

**Pass Criteria:**
- ✅ Status is "ok"
- ✅ Shikhar's share is 500 (fixed)
- ✅ Ashna's implied share is 1500
- ⚠️ Save expense_id

---

### Test 4.4: List Shared Expenses - Ashna
**Objective:** Retrieve all shared expenses

**Steps:**
1. Call `list_shared_expenses` with:
   - token: <ashna_token>

**Expected Output:**
```json
{
  "status": "ok",
  "shared_expenses": [
    {
      "id": <number>,
      "date": "2026-08-12",
      "description": "Weekly grocery shopping",
      "total_amount": 1000,
      "paid_by": "Ashna",
      "participants": [{"name": "Shikhar", "share": 500}]
    },
    ...
  ]
}
```

**Pass Criteria:**
- ✅ Status is "ok"
- ✅ Contains ≥3 shared expenses
- ✅ All 3 test expenses present (Grocery, Dinner, Trip)

---

### Test 4.5: Search Shared Expenses - 'grocery'
**Objective:** Filter shared expenses by keyword

**Steps:**
1. Call `search_shared_expenses` with:
   - token: <ashna_token>
   - keyword: "grocery"

**Expected Output:**
```json
{
  "status": "ok",
  "count": 1,
  "shared_expenses": [grocery expense]
}
```

**Pass Criteria:**
- ✅ Status is "ok"
- ✅ count is 1
- ✅ Found expense contains "grocery"

---

### Test 4.6: Search Shared Expenses - Amount ₹900-₹1100
**Objective:** Filter by amount range

**Steps:**
1. Call `search_shared_expenses` with:
   - token: <ashna_token>
   - min_amount: 900
   - max_amount: 1100

**Expected Output:**
```json
{
  "status": "ok",
  "count": 2,
  "shared_expenses": [Grocery and Dinner]
}
```

**Pass Criteria:**
- ✅ Status is "ok"
- ✅ count is 2 (₹1000 amounts)
- ✅ Trip (₹2000) not included

---

### Test 4.7: Edit Shared Expense - Change ₹1000 → ₹1200
**Objective:** Modify expense and verify smart share recalculation

**Steps:**
1. Call `edit_shared_expense` with:
   - token: <ashna_token>
   - expense_id: <from Test 4.1>
   - total_amount: 1200

**Expected Output:**
```json
{
  "status": "ok",
  "expense_id": <number>,
  "message": "Shared expense updated successfully",
  "shares_recalculated": true
}
```

**Pass Criteria:**
- ✅ Status is "ok"
- ✅ shares_recalculated is true
- ✅ When listed, Shikhar's share should now be 600 (50% of ₹1200)
- ✅ Ashna's share should be 600

---

### Test 4.8: Delete Shared Expense - Trip ₹2000
**Objective:** Remove shared expense

**Steps:**
1. Call `delete_shared_expense` with:
   - token: <ashna_token>
   - expense_id: <from Test 4.3>

**Expected Output:**
```json
{
  "status": "ok",
  "message": "Shared expense deleted successfully",
  "deleted": {
    "id": <number>,
    "description": "Weekend trip expenses",
    "total_amount": 2000
  }
}
```

**Pass Criteria:**
- ✅ Status is "ok"
- ✅ Deleted expense details returned
- ✅ Future list_shared_expenses should NOT show this expense

---

## PHASE 5: BALANCES & SETTLEMENTS

### Test 5.1: Get Balances - Ashna
**Objective:** Check balance sheet

**Steps:**
1. Call `get_balances` with:
   - token: <ashna_token>

**Expected Output:**
```json
{
  "status": "ok",
  "Shikhar": -1350  // Shikhar owes Ashna ₹1350
}
```

**Pass Criteria:**
- ✅ Status is "ok"
- ✅ Contains "Shikhar" entry
- ✅ Balance is negative (Shikhar owes)
- ⚠️ Exact amount depends on all previous operations

---

### Test 5.2: Get Balances - Shikhar
**Objective:** Check balance from other side

**Steps:**
1. Call `get_balances` with:
   - token: <shikhar_token>

**Expected Output:**
```json
{
  "status": "ok",
  "Ashna": 1350  // Ashna is owed ₹1350
}
```

**Pass Criteria:**
- ✅ Status is "ok"
- ✅ Contains "Ashna" entry
- ✅ Balance is positive (Ashna owes money)
- ✅ Mirrors Ashna's balance (opposite sign)

---

### Test 5.3: Record Settlement - Ashna pays Shikhar ₹500
**Objective:** Record partial settlement

**Steps:**
1. Call `settle_payment` with:
   - token: <ashna_token>
   - person: "Shikhar"
   - amount: 500
   - settlement_date: "2026-08-12"
   - note: "Partial settlement for shared expenses"

**Expected Output:**
```json
{
  "status": "ok",
  "message": "Settlement recorded"
}
```

**Pass Criteria:**
- ✅ Status is "ok"
- ✅ After this, balance should reduce by ₹500

---

### Test 5.4: List Settlements - Ashna
**Objective:** View settlement history

**Steps:**
1. Call `list_settlements` with:
   - token: <ashna_token>

**Expected Output:**
```json
{
  "status": "ok",
  "settlements": [
    {
      "id": <number>,
      "person": "Shikhar",
      "amount": 500,
      "date": "2026-08-12",
      "note": "Partial settlement for shared expenses"
    }
  ]
}
```

**Pass Criteria:**
- ✅ Status is "ok"
- ✅ Contains the settlement made in Test 5.3
- ✅ Amount is 500
- ✅ Person is "Shikhar"

---

## PHASE 6: EXPORT

### Test 6.1: Export Expenses to Excel
**Objective:** Export all expenses

**Steps:**
1. Call `export_expenses_to_excel` with:
   - token: <ashna_token>
   - start_date: "2026-08-12"
   - end_date: "2026-08-12"
   - include_shared: true

**Expected Output:**
```json
{
  "status": "ok",
  "message": "Excel file exported successfully",
  "file_path": "/tmp/expenses_ashna_20260812_120000.xlsx",
  "file_size": <bytes>,
  "sheets": ["Expenses", "Shared Expenses"]
}
```

**Pass Criteria:**
- ✅ Status is "ok"
- ✅ file_path is present
- ✅ file_size > 0
- ✅ Contains both sheets

---

## Summary of Expected Outcomes

| Phase | Tests | Purpose |
|-------|-------|---------|
| 1 | 4 | User authentication |
| 2 | 7 | Personal expense management |
| 3 | 2 | Friend management |
| 4 | 8 | Shared expense management |
| 5 | 4 | Balances and settlements |
| 6 | 1 | Export functionality |
| **Total** | **26** | **End-to-end coverage** |

---

## Running the Tests

```bash
# Start MCP server
python main.py

# In another terminal, run tests
python test_suite.py
```

Expected output will show:
- ✅ PASS for each successful test
- ❌ FAIL for any failures
- Summary with pass/fail count

