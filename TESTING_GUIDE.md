# Expense Tracker - Testing Guide

## Quick Summary

You have **3 test suites** available:

### 1. **Basic Test Suite** (`test_suite.py`)
- 26 golden test cases
- Tests all core functionality
- Single user flow

**To run locally:**
```bash
# Terminal 1: Start MCP server
python main.py

# Terminal 2: Run tests  
python test_suite.py
```

---

### 2. **Advanced Test Suite** (`test_suite_advanced.py`)
- Very thorough testing
- 4 unique users: Priya, Shikhar, Ashna, Arjun
- 10 complex scenarios:
  1. Three-way expense split
  2. Percentage-based splits
  3. Fixed amount splits
  4. Search & filter
  5. Multiple settlements with balance updates
  6. Smart share recalculation on edit
  7. Mix of personal + shared expenses
  8. Final balance verification
  9. Excel export
  10. Settlement history

**To run locally:**
```bash
# Terminal 1: Start MCP server
python main.py

# Terminal 2: Run tests
python test_suite_advanced.py
```

---

### 3. **Deployed Test Suite** (`test_deployed.py`)
- Tests your live Render deployment
- URL: `https://expense-tracker-repo-vpox.onrender.com/mcp`
- Note: This requires special session handling via Claude Desktop

**Best approach:** Use Claude Desktop directly

---

## Testing via Claude Desktop (Recommended)

The easiest way to test your deployed API is directly in Claude Desktop:

1. **Open Claude Desktop**
2. **Make sure your MCP connector is configured** to use:
   ```
   https://expense-tracker-repo-vpox.onrender.com/mcp
   ```

3. **Run these commands in order:**

### Test Sequence:

#### Step 1: Register Users
```
Register User: Priya
- username: test_user_1
- password: Test@123
- email: priya@example.com
```

#### Step 2: Register Second User
```
Register User: Ashna
- username: test_user_2
- password: Test@456
- email: ashna@example.com
```

#### Step 3: Login
```
Login as Priya
- username: test_user_1
- password: Test@123
[Save the token]
```

#### Step 4: Add Personal Expense
```
Add Personal Expense
- token: [from step 3]
- date: 2026-08-12
- amount: 500
- category: Groceries
- subcategory: Vegetables
- note: Weekly shopping
```

#### Step 5: Add Friend
```
Add Friend
- token: [from step 3]
- name: Ashna
- email: ashna@example.com
```

#### Step 6: Create Shared Expense
```
Add Shared Expense
- token: [from step 3]
- date: 2026-08-12
- amount: 1000
- paid_by: Priya
- participants: ["Ashna"]
- description: Lunch for both
```

#### Step 7: Check Balance
```
Get Balances
- token: [from step 3]
Expected: Ashna owes ₹500
```

#### Step 8: Record Settlement
```
Settle Payment
- token: [from step 3]
- person: Ashna
- amount: 500
- settlement_date: 2026-08-12
- note: Payment for lunch
```

#### Step 9: Verify Updated Balance
```
Get Balances
- token: [from step 3]
Expected: Ashna balance should now be ₹0 (or close to it)
```

#### Step 10: List Settlements
```
List Settlements
- token: [from step 3]
Should show the ₹500 settlement
```

---

## Test Documentation

See `TEST_CASES.md` for detailed test specifications including:
- Expected outputs for each test
- Pass criteria
- Manual testing steps
- 26 golden test cases

---

## What to Test

### Core Features
- ✅ User registration and authentication
- ✅ Personal expense management (add, edit, delete, search)
- ✅ Shared expense management with 3 split types
  - Equal split (50/50)
  - Percentage split (60/40, etc.)
  - Fixed amount split (₹500, ₹1000, etc.)
- ✅ Smart share recalculation when editing expenses
- ✅ Balance calculations across multiple users
- ✅ Settlements and running balance updates
- ✅ Search and filter functionality
- ✅ Excel export
- ✅ Settlement history

### Expected Behaviors

**1. Equal Split (Default)**
```
Amount: ₹1000
Participants: 2 people
Each pays: ₹500
```

**2. Percentage Split**
```
Amount: ₹1000
Person A: 60% = ₹600
Person B: 40% = ₹400
```

**3. Fixed Amount Split**
```
Amount: ₹2000
Person A: ₹500
Person B: ₹1500
```

**4. Smart Recalculation**
```
Original: ₹1000 (50/50) = ₹500 each
Edit to: ₹1200
New split: 50/50 = ₹600 each
(Ratio maintained!)
```

**5. Balance Calculation**
```
If Person A pays ₹1000 and Person B's share is ₹600:
Person B owes Person A: ₹600 (negative balance for B)
Person A is owed: ₹600 (positive balance for A)
```

**6. Settlement**
```
Original: B owes A ₹600
Settlement: B pays A ₹300
Updated: B owes A ₹300
```

---

## Files Reference

| File | Purpose | Tests |
|------|---------|-------|
| `main.py` | Core API | - |
| `test_suite.py` | Basic E2E tests | 26 tests |
| `test_suite_advanced.py` | Advanced scenarios | 50+ tests |
| `test_deployed.py` | Deployed API tests | 20 tests |
| `TEST_CASES.md` | Manual test cases | 26 detailed cases |

---

## Troubleshooting

### Issue: "Token expired"
**Solution:** Register a new user and get a fresh token

### Issue: "Friend not found"
**Solution:** Make sure you added the friend BEFORE creating a shared expense

### Issue: "Expense not found"
**Solution:** Use the expense ID from the creation response

### Issue: "Balance doesn't match"
**Solution:** Check if there are any settled amounts affecting the calculation

### Issue: "Email not sent"
**Solution:** Make sure:
1. SENDGRID_API_KEY is set in environment
2. SMTP_FROM is a verified sender on SendGrid
3. Friend has an email registered

---

## Success Criteria

All of the following should work:

✅ Register multiple users
✅ Login and get token
✅ Add personal expenses
✅ Add friends
✅ Create shared expenses with equal split
✅ Create shared expenses with percentage split
✅ Create shared expenses with fixed amount split
✅ Edit shared expense and verify smart recalculation
✅ Delete shared expense
✅ Search expenses by keyword
✅ Filter by amount range
✅ Get balance calculations
✅ Record settlements
✅ View settlement history
✅ Export to Excel
✅ Verify balance updates after settlement

---

## Performance Notes

- First request after 15 minutes of inactivity may take 5-10 seconds (Render free tier cold start)
- Subsequent requests should be fast (<1 second)
- Balance calculations may take 1-2 seconds for complex multi-user scenarios
- Excel export takes 2-3 seconds

---

Happy Testing! 🚀
