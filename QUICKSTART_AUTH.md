# Quick Start Guide - Authentication

## For Developers

### 1. Start the Server
```bash
python main.py
```

The MCP server will start on `http://0.0.0.0:8000`

### 2. Quick Test
```bash
python client_example.py
```

This runs a complete demo showing:
- User registration
- Login
- Adding expenses/credits
- Data isolation (each user sees only their data)

## For API Integration

### Step 1: Register a User
```python
from main import register_user, login, add_expense, list_expenses

# Register
result = await register_user("myuser", "mypassword", "my@email.com")
# {"status": "ok", "user_id": 1, "message": "User registered successfully"}
```

### Step 2: Login to Get Token
```python
# Login
result = await login("myuser", "mypassword")
# {
#   "status": "ok",
#   "token": "eyJhbGciOiJIUzI1NiIs...",
#   "user_id": 1,
#   "message": "Login successful"
# }

token = result["token"]
```

### Step 3: Use Token for Operations
```python
# Add expense
await add_expense(token, "2026-08-11", 500, "Food", "Lunch")

# List expenses
expenses = await list_expenses(token, "2026-08-01", "2026-08-31")
```

## Environment Setup

Optional `.env` file:
```env
JWT_SECRET=your-secret-key-here
JWT_EXPIRY_HOURS=24
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your@gmail.com
SMTP_PASSWORD=your-app-password
```

## Key Points

✅ **Token Format**: JWT tokens are long strings starting with `eyJ...`

✅ **Token Usage**: Pass token as **first parameter** to all operations

✅ **Token Expiry**: Default 24 hours. Get new token by logging in again

✅ **Data Isolation**: Each user only accesses their own data - enforced at database level

✅ **Password Security**: Passwords hashed with PBKDF2-SHA256, never stored as plain text

## Common Operations

```python
# Expenses
await add_expense(token, date, amount, category, subcategory, note)
await list_expenses(token, start_date, end_date)
await delete_expense(token, date, amount, category)
await edit_expense(token, old_date, old_amount, old_category, new_date, ...)
await summarize(token, start_date, end_date, category)

# Credits
await add_credit(token, date, amount, source, note)
await list_credits(token, start_date, end_date)

# Friends (for shared expenses)
await add_friend(token, name, email)
await list_friends(token)
await update_friend_email(token, name, new_email)

# Shared expenses
await add_shared_expense(token, date, amount, paid_by, participants, description)
await settle_payment(token, person, amount, settlement_date, note)
await get_balances(token)
```

## Testing Authentication

All three users can be tested independently:

```python
# User 1
token1 = (await login("user1", "pass1"))["token"]
await add_expense(token1, "2026-08-11", 100, "Food")

# User 2
token2 = (await login("user2", "pass2"))["token"]
await add_expense(token2, "2026-08-11", 200, "Groceries")

# Each sees only their expenses
print(await list_expenses(token1, "2026-08-01", "2026-08-31"))  # 1 expense
print(await list_expenses(token2, "2026-08-01", "2026-08-31"))  # 1 expense
```

## Troubleshooting

| Error | Solution |
|-------|----------|
| "Invalid or expired token" | Log in again to get a new token |
| "Username already exists" | Choose a different username |
| "Invalid username or password" | Check credentials (case-sensitive) |
| "Invalid token" when calling operation | Ensure token is complete string (not cut off) |

## For Deployment

1. **Set JWT_SECRET in production** (not random):
   ```bash
   export JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
   ```

2. **Use HTTPS only** for token transmission

3. **Store tokens securely** on client (not in localStorage if possible)

4. **Implement rate limiting** on login endpoint

5. **Monitor** for unusual authentication patterns

For more details, see [AUTHENTICATION.md](AUTHENTICATION.md)
