# JWT Authentication Implementation

Your Expense Tracker now has user authentication enabled! Each user can only access their own data.

## Overview

- **JWT Tokens**: Stateless authentication using JSON Web Tokens
- **Password Hashing**: Passwords are hashed with PBKDF2-SHA256 (100,000 iterations) for security
- **User Isolation**: Each expense, credit, friend, and settlement is tied to a specific user
- **Token Expiry**: Tokens expire after 24 hours (configurable via `JWT_EXPIRY_HOURS` env var)

## Authentication Flow

```
1. User registers → register_user() creates account with hashed password
2. User logs in → login() validates credentials and returns JWT token
3. User includes token in every request → Token is verified before accessing data
4. Token verified → Operation performs and returns user-specific data
```

## Configuration

Add these to your `.env` file (optional - defaults are secure):

```env
JWT_SECRET=your-secret-key-here
JWT_EXPIRY_HOURS=24
```

**Important**: Set `JWT_SECRET` to a strong random string in production. Generate one with:
```python
import secrets
print(secrets.token_urlsafe(32))
```

## API Usage

### 1. Register New User

```python
result = await register_user("john_doe", "secure_password", "john@example.com")
# Returns: {"status": "ok", "user_id": 1, "message": "User registered successfully"}
```

### 2. Login

```python
result = await login("john_doe", "secure_password")
# Returns: {
#   "status": "ok",
#   "token": "eyJhbGciOiJIUzI1NiIs...",
#   "user_id": 1,
#   "message": "Login successful"
# }
```

Save the `token` - you'll need it for all other operations.

### 3. Verify Token

```python
result = await verify_token(token)
# Returns: {
#   "status": "ok",
#   "user_id": 1,
#   "username": "john_doe",
#   "email": "john@example.com"
# }
```

### 4. All Operations Now Require Token

Every expense operation now needs the token as the first parameter:

```python
# Add expense
await add_expense(token, "2026-08-11", 500.0, "Food", "Dinner", "Restaurant")

# List expenses
await list_expenses(token, "2026-08-01", "2026-08-31")

# Summarize
await summarize(token, "2026-08-01", "2026-08-31", category="Food")

# Delete expense
await delete_expense(token, "2026-08-11", 500.0, "Food")

# Edit expense
await edit_expense(token, "2026-08-11", 500.0, "Food", new_amount=600.0)

# Add credit
await add_credit(token, "2026-08-11", 50000.0, "Salary", "Monthly salary")

# List credits
await list_credits(token, "2026-08-01", "2026-08-31")

# Add friend
await add_friend(token, "Alice", "alice@example.com")

# List friends
await list_friends(token)

# Update friend email
await update_friend_email(token, "Alice", "newalice@example.com")

# Add shared expense
await add_shared_expense(
    token,
    "2026-08-11",
    3000.0,
    "You",
    [{"name": "Alice", "share": 1000.0}, {"name": "Bob", "share": 1000.0}],
    "Movie tickets"
)

# Settle payment
await settle_payment(token, "Alice", 1000.0, "2026-08-11", "Paid for movie")

# Get balances
await get_balances(token)
```

## Database Schema Changes

### New `users` Table
```sql
CREATE TABLE users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
)
```

### Updated Tables
All existing tables now have `user_id` field and foreign key:
- `expenses` → `user_id`
- `credits` → `user_id`
- `shared_expenses` → `user_id`
- `friends` → `user_id` (also made name unique per user, not globally)
- `settlements` → `user_id`

This ensures each user only sees their own data.

## Security Best Practices

✅ **What We Do**
- Hash passwords with PBKDF2-SHA256 (100,000 iterations)
- Use JWT tokens with expiration
- Validate tokens on every request
- Each user only accesses their own data

✅ **What You Should Do**
- Always use HTTPS in production
- Store JWT_SECRET securely (environment variable, not in code)
- Regenerate JWT_SECRET periodically
- Use strong passwords (minimum 12 characters recommended)
- Implement rate limiting on login endpoint
- Log authentication attempts in production

## Troubleshooting

### "Invalid or expired token" error
- Token may have expired (default 24 hours). Log in again to get a new token
- Token may be malformed. Ensure you're passing the complete token string

### "Username already exists" error
- Username is taken. Choose a different username

### "Invalid username or password" error
- Check spelling of username
- Verify password is correct (case-sensitive)

### Data isolation issues
- If you see another user's data, it's a bug - report it immediately
- Each operation filters by `user_id` from the token

## Migration from Old Database

If you had expenses in the old database (before authentication):
1. Create a default admin user
2. Run migration script to assign old expenses to admin user
3. Other users register separately

Contact support for migration assistance if needed.

## Example Client Implementation

```python
# login.py
import asyncio
from main import register_user, login, add_expense, list_expenses

async def main():
    # Register
    await register_user("myuser", "mypassword", "my@email.com")
    
    # Login
    login_result = await login("myuser", "mypassword")
    token = login_result["token"]
    
    # Use token for operations
    await add_expense(token, "2026-08-11", 100, "Food")
    expenses = await list_expenses(token, "2026-08-01", "2026-08-31")
    print(expenses)

asyncio.run(main())
```

## Environment Variables

```env
# Optional - defaults to secure random value
JWT_SECRET=your-secret-key

# Optional - token expiry in hours (default: 24)
JWT_EXPIRY_HOURS=24

# Existing SMTP settings still work
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```
