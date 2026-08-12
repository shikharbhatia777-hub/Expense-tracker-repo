from fastmcp import FastMCP
import asyncio
import os
import asyncpg
import aiofiles
import jwt
import hashlib
import secrets
import queue
import threading
from datetime import datetime, timedelta, timezone as tz

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
except ImportError:
    SendGridAPIClient = None
    Mail = None

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_DB = os.getenv("POSTGRES_DB", "postgres")

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@expensetracker.com")

JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_urlsafe(32))
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))

mcp = FastMCP("ExpenseTracker")
db_lock = asyncio.Lock()
_db_initialized = False
_current_user_id = None
_db_pool = None
_email_queue = queue.Queue()
_email_worker_task = None


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(32)
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}${password_hash.hex()}"


def _verify_password(password: str, hashed: str) -> bool:
    try:
        salt, password_hash = hashed.split('$')
        computed_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return computed_hash.hex() == password_hash
    except:
        return False


def _create_token(user_id: int) -> str:
    now = datetime.now(tz.utc)
    payload = {
        'user_id': user_id,
        'exp': now + timedelta(hours=JWT_EXPIRY_HOURS),
        'iat': now
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')


def _verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def _get_connection():
    global _db_pool
    if _db_pool is None:
        raise RuntimeError("Database pool not initialized")
    return _db_pool

async def _run_with_connection(operation):
    await _ensure_db_initialized()
    conn = await _get_connection()
    return await operation(conn)


async def _execute_fetchall(conn, query, params=()):
    return await conn.fetch(query, *params)


async def _execute_fetchone(conn, query, params=()):
    return await conn.fetchrow(query, *params)


async def init_db():
    global _db_pool

    try:
        _db_pool = await asyncpg.create_pool(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB,
            min_size=5,
            max_size=20,
            command_timeout=10,
            statement_cache_size=0,
        )

        conn = await _db_pool.acquire()
        try:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users(
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS expenses(
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT DEFAULT '',
                    note TEXT DEFAULT '',
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS credits(
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    source TEXT NOT NULL,
                    note TEXT DEFAULT '',
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS shared_expenses(
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    description TEXT,
                    total_amount REAL NOT NULL,
                    paid_by TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS shared_expense_participants(
                    id SERIAL PRIMARY KEY,
                    expense_id INTEGER NOT NULL,
                    participant TEXT NOT NULL,
                    share_amount REAL NOT NULL,
                    FOREIGN KEY(expense_id)
                    REFERENCES shared_expenses(id)
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS friends(
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    email TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    UNIQUE(user_id, name)
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS settlements(
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    person TEXT NOT NULL,
                    amount REAL NOT NULL,
                    settlement_date TEXT NOT NULL,
                    note TEXT DEFAULT '',
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """)
        finally:
            await _db_pool.release(conn)

    except Exception as e:
        raise RuntimeError(f"Unable to initialize database: {e}")


async def _normalize_payer_name(paid_by: str):
    if not paid_by:
        return "You"
    lowered = str(paid_by).strip().lower()
    if lowered in {"me", "i", "myself", "my", "self"}:
        return "You"
    return str(paid_by).strip()


def _normalize_payer_name_sync(paid_by: str):
    return asyncio.run(_normalize_payer_name(paid_by))


async def _calculate_balances(conn, user_id: int):
    balances = {}

    expense_rows = await _execute_fetchall(
        conn, "SELECT id, paid_by FROM shared_expenses WHERE user_id=$1", (user_id,)
    )

    for expense_row in expense_rows:
        expense_id, paid_by = expense_row['id'], expense_row['paid_by']
        participant_rows = await _execute_fetchall(
            conn, "SELECT participant, share_amount FROM shared_expense_participants WHERE expense_id=$1",
            (expense_id,)
        )

        if not participant_rows:
            continue

        payer_name = await _normalize_payer_name(paid_by)
        others_total = 0.0

        for participant_row in participant_rows:
            participant, share_amount = participant_row['participant'], participant_row['share_amount']
            participant_name = await _normalize_payer_name(participant)
            share_value = round(float(share_amount), 2)

            if participant_name.lower() == payer_name.lower():
                continue

            balances[participant_name] = balances.get(participant_name, 0.0) - share_value
            others_total += share_value

        if payer_name:
            balances[payer_name] = balances.get(payer_name, 0.0) + round(others_total, 2)

    # Get user's name from username for participant lookup
    user_row = await _execute_fetchone(conn, "SELECT username FROM users WHERE id=$1", (user_id,))
    username = user_row['username'] if user_row else None

    # Include expenses where this user is a participant
    if username:
        participant_expenses = await _execute_fetchall(
            conn, """
            SELECT se.id, se.paid_by, sep.share_amount
            FROM shared_expense_participants sep
            JOIN shared_expenses se ON sep.expense_id = se.id
            WHERE LOWER(sep.participant) = LOWER($1)
            """, (username,)
        )

        for expense_row in participant_expenses:
            paid_by, share_amount = expense_row['paid_by'], expense_row['share_amount']
            payer_name = await _normalize_payer_name(paid_by)
            share_value = round(float(share_amount), 2)

            if username.lower() != payer_name.lower():
                balances[payer_name] = balances.get(payer_name, 0.0) + share_value

    settlement_rows = await _execute_fetchall(
        conn, "SELECT person, amount FROM settlements WHERE user_id=$1", (user_id,)
    )

    for settlement_row in settlement_rows:
        person, amount = settlement_row['person'], settlement_row['amount']
        person_name = await _normalize_payer_name(person)
        amount_value = round(float(amount), 2)
        current_balance = balances.get(person_name, 0.0)

        # When a person settles with you, reduce what they owe you
        # Settlement reduces the balance (you receive money from them)
        balances[person_name] = round(current_balance - amount_value, 2)

    return {name: round(balance, 2) for name, balance in balances.items()}


async def _coerce_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("%"):
            return float(text[:-1])
        return float(text)
    return None


async def _build_participant_splits(amount: float, participants: list, paid_by: str):
    if not participants:
        return []

    normalized = []
    for entry in participants:
        if isinstance(entry, str):
            normalized.append({"name": entry, "percent": None, "parts": None, "share": None})
        elif isinstance(entry, dict):
            normalized.append({
                "name": entry.get("name") or entry.get("participant") or entry.get("person"),
                "percent": await _coerce_number(entry.get("percent") or entry.get("percentage")),
                "parts": await _coerce_number(entry.get("parts") or entry.get("ratio") or entry.get("weight")),
                "share": await _coerce_number(entry.get("share") or entry.get("amount") or entry.get("value") or entry.get("owed") or entry.get("pay_amount"))
            })
        else:
            normalized.append({"name": str(entry), "percent": None, "parts": None, "share": None})

    if paid_by in [item["name"] for item in normalized]:
        total_people = len(normalized)
    else:
        total_people = len(normalized) + 1

    def _round_money(value: float):
        return round(value + 1e-9, 2)

    equal_share = _round_money(amount / total_people)

    result = []
    for item in normalized:
        name = item.get("name")
        if not name:
            continue
        percent = item.get("percent")
        parts = item.get("parts")
        share_amount = item.get("share")
        if share_amount is not None:
            share = _round_money(float(share_amount))
        elif percent is not None:
            share = _round_money(amount * float(percent) / 100.0)
        elif parts is not None:
            total_parts = sum(float(x.get("parts") or 0) for x in normalized if isinstance(x, dict) and x.get("parts") is not None)
            if total_parts <= 0:
                share = equal_share
            else:
                share = _round_money(amount * float(parts) / total_parts)
        else:
            share = equal_share
        result.append({"name": name, "share": share})

    return result


async def _build_email_summary(paid_by: str, amount: float, description: str, participant_splits: list, balances: dict, recipient_name: str):
    payer_name = await _normalize_payer_name(paid_by)
    recipient_display = recipient_name or "there"
    recipient_share = None

    for entry in participant_splits:
        if entry["name"].lower() == recipient_display.lower():
            recipient_share = entry["share"]
            break

    recipient_balance = None
    if balances is not None:
        for person, balance in balances.items():
            if str(person).lower() == recipient_display.lower():
                recipient_balance = balance
                break

    lines = []
    lines.append(f"Hi {recipient_display},")
    lines.append("")
    lines.append(f"{payer_name} paid ₹{amount:.2f} for:")
    lines.append("")
    lines.append(description)
    lines.append("")
    lines.append(f"Your share for this expense: ₹{recipient_share:.2f}" if recipient_share is not None else "Your share for this expense: ₹0.00")
    lines.append("")
    lines.append("Shared expense summary:")
    for entry in participant_splits:
        lines.append(f"- {entry['name']}: ₹{entry['share']:.2f}")
    lines.append("")
    lines.append("Please settle whenever convenient.")
    lines.append("")
    lines.append("Thank you.")
    return "\n".join(lines)


async def send_email(recipient, subject, body):
    if not recipient:
        print("[EMAIL] ❌ Skipped: no recipient provided")
        return False

    if not SENDGRID_API_KEY:
        print("[EMAIL] ❌ Skipped: SENDGRID_API_KEY not configured")
        return False

    if not SendGridAPIClient or not Mail:
        print("[EMAIL] ❌ Skipped: SendGrid library not installed")
        return False

    try:
        print(f"[EMAIL] 📧 Preparing email to {recipient}...")
        message = Mail(
            from_email=SMTP_FROM,
            to_emails=recipient,
            subject=subject,
            plain_text_content=body
        )
        print(f"[EMAIL] 🔑 Using API key: {SENDGRID_API_KEY[:20]}...")
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        print(f"[EMAIL] ✅ Email sent to {recipient} (Status: {response.status_code})")
        return True
    except Exception as e:
        print(f"[EMAIL] ❌ Failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def queue_email(recipient, subject, body):
    try:
        print(f"[QUEUE] 📬 Queuing email to {recipient}")
        print(f"[QUEUE] 📝 Subject: {subject}")
        _email_queue.put((recipient, subject, body), block=False)
        print(f"[QUEUE] ✅ Email queued successfully (Queue size now: {_email_queue.qsize()})")
    except queue.Full:
        print(f"[QUEUE] ❌ Queue full, dropping email to {recipient}")
    except Exception as e:
        print(f"[QUEUE] ❌ Error queuing: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


def run_email_worker():
    print("[WORKER] 🚀 Email worker started")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    print(f"[WORKER] 📊 Queue size at start: {_email_queue.qsize()}")
    while True:
        try:
            print(f"[WORKER] ⏳ Waiting for email (queue size: {_email_queue.qsize()})...")
            recipient, subject, body = _email_queue.get(timeout=1)
            print(f"[WORKER] 📨 Got email from queue! Processing to {recipient}")
            loop.run_until_complete(send_email(recipient, subject, body))
            print(f"[WORKER] ✅ Email processed successfully")
        except queue.Empty:
            pass
        except Exception as e:
            print(f"[WORKER] ❌ Critical Error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()


async def _ensure_db_initialized():
    global _db_initialized, _email_worker_task
    if not _db_initialized:
        await init_db()
        _db_initialized = True

    # Start email worker if not already running
    if _email_worker_task is None:
        print("[INIT] 🚀 Starting email worker thread...")
        _email_worker_task = threading.Thread(target=run_email_worker, daemon=True)
        _email_worker_task.start()
        print("[INIT] ✅ Email worker thread created")


@mcp.tool(description="Register a new user with username and password.")
async def register_user(username: str, password: str, email: str = ""):
    async with db_lock:
        async def _op(conn):
            existing = await _execute_fetchone(conn, "SELECT id FROM users WHERE username=$1", (username,))
            if existing:
                return {"status": "error", "message": "Username already exists"}

            password_hash = _hash_password(password)
            created_at = datetime.now(tz.utc).isoformat()

            user_id = await conn.fetchval(
                "INSERT INTO users(username, email, password_hash, created_at) VALUES ($1,$2,$3,$4) RETURNING id",
                username, email, password_hash, created_at
            )
            return {"status": "ok", "user_id": user_id, "message": "User registered successfully"}

        return await _run_with_connection(_op)


@mcp.tool(description="Login with username and password to get a JWT token.")
async def login(username: str, password: str):
    async def _op(conn):
        user = await _execute_fetchone(conn, "SELECT id, password_hash FROM users WHERE username=$1", (username,))
        if not user:
            return {"status": "error", "message": "Invalid username or password"}

        user_id, password_hash = user['id'], user['password_hash']
        if not _verify_password(password, password_hash):
            return {"status": "error", "message": "Invalid username or password"}

        token = _create_token(user_id)
        return {"status": "ok", "token": token, "user_id": user_id, "message": "Login successful"}

    return await _run_with_connection(_op)


@mcp.tool(description="Verify a JWT token and return user information.")
async def verify_token(token: str):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async def _op(conn):
        user = await _execute_fetchone(conn, "SELECT id, username, email FROM users WHERE id=$1", (payload['user_id'],))
        if not user:
            return {"status": "error", "message": "User not found"}

        return {"status": "ok", "user_id": user['id'], "username": user['username'], "email": user['email']}

    return await _run_with_connection(_op)


@mcp.tool(description="Add a new regular expense entry to the database.")
async def add_expense(token: str, date, amount, category, subcategory="", note=""):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async with db_lock:
        async def _op(conn):
            expense_id = await conn.fetchval(
                "INSERT INTO expenses(user_id, date, amount, category, subcategory, note) VALUES ($1,$2,$3,$4,$5,$6) RETURNING id",
                payload['user_id'], date, amount, category, subcategory, note
            )
            return {"status": "ok", "id": expense_id}

        return await _run_with_connection(_op)


@mcp.tool(description="List expense entries within an inclusive date range.")
async def list_expenses(token: str, start_date, end_date):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async def _op(conn):
        rows = await _execute_fetchall(
            conn,
            """
            SELECT id, date, amount, category, subcategory, note
            FROM expenses
            WHERE user_id=$1 AND date BETWEEN $2 AND $3
            ORDER BY id ASC
            """,
            (payload['user_id'], start_date, end_date)
        )
        return [dict(r) for r in rows]

    return await _run_with_connection(_op)


@mcp.tool(description="Summarize expenses by category within an inclusive date range.")
async def summarize(token: str, start_date, end_date, category=None):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async def _op(conn):
        if category:
            rows = await _execute_fetchall(
                conn,
                """
                SELECT category, SUM(amount) AS total_amount
                FROM expenses
                WHERE user_id=$1 AND date BETWEEN $2 AND $3 AND category = $4
                GROUP BY category ORDER BY category ASC
                """,
                (payload['user_id'], start_date, end_date, category)
            )
        else:
            rows = await _execute_fetchall(
                conn,
                """
                SELECT category, SUM(amount) AS total_amount
                FROM expenses
                WHERE user_id=$1 AND date BETWEEN $2 AND $3
                GROUP BY category ORDER BY category ASC
                """,
                (payload['user_id'], start_date, end_date)
            )
        return [dict(r) for r in rows]

    return await _run_with_connection(_op)


@mcp.tool(description="Delete an expense using its known details instead of an ID.")
async def delete_expense(token: str, date: str, amount: float, category: str, subcategory: str = None):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async def _op(conn):
        if subcategory:
            rows = await _execute_fetchall(
                conn,
                """
                SELECT id, date, amount, category, subcategory, note
                FROM expenses
                WHERE user_id=$1 AND date=$2 AND amount=$3 AND category=$4 AND subcategory=$5
                """,
                (payload['user_id'], date, amount, category, subcategory)
            )
        else:
            rows = await _execute_fetchall(
                conn,
                """
                SELECT id, date, amount, category, subcategory, note
                FROM expenses
                WHERE user_id=$1 AND date=$2 AND amount=$3 AND category=$4
                """,
                (payload['user_id'], date, amount, category)
            )

        if len(rows) == 0:
            return {"status": "error", "message": "No matching expense found"}

        if len(rows) > 1:
            return {
                "status": "multiple_matches",
                "matches": [
                    {
                        "id": r['id'],
                        "date": r['date'],
                        "amount": r['amount'],
                        "category": r['category'],
                        "subcategory": r['subcategory'],
                        "note": r['note']
                    }
                    for r in rows
                ]
            }

        expense_id = rows[0]['id']
        await conn.execute("DELETE FROM expenses WHERE id=$1", expense_id)
        return {"status": "ok", "deleted_id": expense_id}

    return await _run_with_connection(_op)


@mcp.tool(description="Edit an existing expense using known details.")
async def edit_expense(token: str, old_date: str, old_amount: float, old_category: str, new_date: str = None, new_amount: float = None, new_category: str = None, new_subcategory: str = None, new_note: str = None):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async def _op(conn):
        rows = await _execute_fetchall(
            conn,
            """
            SELECT id, date, amount, category, subcategory, note
            FROM expenses
            WHERE user_id=$1 AND date=$2 AND amount=$3 AND category=$4
            """,
            (payload['user_id'], old_date, old_amount, old_category)
        )

        if len(rows) == 0:
            return {"status": "error", "message": "No matching expense found."}

        if len(rows) > 1:
            return {
                "status": "multiple_matches",
                "matches": [
                    {
                        "id": r['id'],
                        "date": r['date'],
                        "amount": r['amount'],
                        "category": r['category'],
                        "subcategory": r['subcategory'],
                        "note": r['note']
                    }
                    for r in rows
                ]
            }

        expense = rows[0]
        await conn.execute(
            """
            UPDATE expenses
            SET date=$1,
                amount=$2,
                category=$3,
                subcategory=$4,
                note=$5
            WHERE id=$6
            """,
            new_date if new_date is not None else expense['date'],
            new_amount if new_amount is not None else expense['amount'],
            new_category if new_category is not None else expense['category'],
            new_subcategory if new_subcategory is not None else expense['subcategory'],
            new_note if new_note is not None else expense['note'],
            expense['id']
        )
        return {"status": "ok", "expense_id": expense['id'], "message": "Expense updated successfully"}

    return await _run_with_connection(_op)


@mcp.tool(description="Record incoming money such as salary, reimbursement, cashback, refund, or bonus.")
async def add_credit(token: str, date: str, amount: float, source: str, note: str = ""):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async with db_lock:
        async def _op(conn):
            credit_id = await conn.fetchval(
                """
                INSERT INTO credits(user_id, date, amount, source, note)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                payload['user_id'], date, amount, source, note
            )
            return {"status": "ok", "credit_id": credit_id, "message": "Credit added successfully"}

        return await _run_with_connection(_op)


@mcp.tool(description="List all credited amounts within a date range.")
async def list_credits(token: str, start_date: str, end_date: str):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async def _op(conn):
        rows = await _execute_fetchall(
            conn,
            """
            SELECT id, date, amount, source, note
            FROM credits
            WHERE user_id=$1 AND date BETWEEN $2 AND $3
            ORDER BY date ASC
            """,
            (payload['user_id'], start_date, end_date)
        )
        return [dict(row) for row in rows]

    return await _run_with_connection(_op)


@mcp.tool(description="Add a friend to the expense tracker so shared-expense emails can be sent to them.")
async def add_friend(token: str, name: str, email: str):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async with db_lock:
        async def _op(conn):
            await conn.execute("INSERT INTO friends(user_id,name,email) VALUES ($1,$2,$3)", payload['user_id'], name, email)
            return {"status": "ok", "message": f"{name} added"}

        return await _run_with_connection(_op)


@mcp.tool(description="Update the email address for an existing friend.")
async def update_friend_email(token: str, name: str, new_email: str):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async with db_lock:
        async def _op(conn):
            row = await _execute_fetchone(conn, "SELECT id FROM friends WHERE user_id=$1 AND LOWER(name)=LOWER($2)", (payload['user_id'], name))
            if not row:
                return {"status": "error", "message": f"Friend '{name}' not found"}
            await conn.execute("UPDATE friends SET email=$1 WHERE user_id=$2 AND LOWER(name)=LOWER($3)", new_email, payload['user_id'], name)
            return {"status": "ok", "message": f"Email updated for {name}"}

        return await _run_with_connection(_op)


@mcp.tool(description="List the friends that are currently registered in the tracker.")
async def list_friends(token: str):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async def _op(conn):
        # Get current user info
        user_row = await _execute_fetchone(conn, "SELECT email, username FROM users WHERE id=$1", (payload['user_id'],))
        if not user_row:
            return []

        user_email, username = user_row['email'], user_row['username']

        # Get explicit friends (added by this user)
        explicit_rows = await _execute_fetchall(
            conn,
            "SELECT id, name, email FROM friends WHERE user_id=$1",
            (payload['user_id'],)
        )
        explicit_friends = [{'id': r['id'], 'name': r['name'], 'email': r['email']} for r in explicit_rows]

        # Get implicit friends (people who added this user as a friend)
        implicit_rows = await _execute_fetchall(
            conn, """
            SELECT DISTINCT f.user_id FROM friends f
            WHERE (
                (f.email IS NOT NULL AND LOWER(f.email) = LOWER($1))
                OR (f.name IS NOT NULL AND LOWER(f.name) = LOWER($2))
            )
            AND f.user_id != $3
            """,
            (user_email or '', username, payload['user_id'])
        )

        implicit_friends = []
        seen_emails = {f['email'] for f in explicit_friends if f['email']}

        for row in implicit_rows:
            adder_user_id = row['user_id']
            adder_row = await _execute_fetchone(
                conn,
                "SELECT username, email FROM users WHERE id=$1",
                (adder_user_id,)
            )
            if adder_row:
                adder_username, adder_email = adder_row['username'], adder_row['email']
                if adder_email and adder_email not in seen_emails:
                    implicit_friends.append({
                        'id': None,
                        'name': adder_username,
                        'email': adder_email
                    })
                    seen_emails.add(adder_email)

        return explicit_friends + implicit_friends

    return await _run_with_connection(_op)


@mcp.tool(description="Create a shared expense and split it among participants, including optional email notifications.")
async def add_shared_expense(token: str, date: str, amount: float, paid_by: str, participants: list, description: str = ""):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    participant_splits = await _build_participant_splits(amount, participants, paid_by)
    payer_name = await _normalize_payer_name(paid_by)

    async with db_lock:
        async def _op(conn):
            expense_id = await conn.fetchval(
                """
                INSERT INTO shared_expenses(user_id, date, description, total_amount, paid_by)
                VALUES ($1,$2,$3,$4,$5)
                RETURNING id
                """,
                payload['user_id'], date, description, amount, payer_name
            )

            for entry in participant_splits:
                await conn.execute(
                    """
                    INSERT INTO shared_expense_participants(expense_id, participant, share_amount)
                    VALUES ($1,$2,$3)
                    """,
                    expense_id, entry["name"], entry["share"]
                )

            balances = await _calculate_balances(conn, payload['user_id'])

            for entry in participant_splits:
                person = entry["name"]
                print(f"[EXPENSE] 🔍 Looking up email for participant: {person}")
                email_row = await _execute_fetchone(
                    conn, "SELECT email FROM friends WHERE user_id=$1 AND LOWER(name)=LOWER($2)",
                    (payload['user_id'], person)
                )

                if email_row and email_row['email']:
                    print(f"[EXPENSE] 📧 Found email: {email_row['email']}")
                    email_summary = await _build_email_summary(paid_by, amount, description, participant_splits, balances, person)
                    queue_email(email_row['email'], f"Expense Split: {description}", email_summary)
                else:
                    print(f"[EXPENSE] ⚠️  No email found for {person}")

            # Send email to the payer (current user) as well
            user_row = await _execute_fetchone(
                conn, "SELECT email FROM users WHERE id=$1",
                (payload['user_id'],)
            )
            if user_row and user_row['email']:
                print(f"[EXPENSE] 📧 Found payer email: {user_row['email']}")
                email_summary = await _build_email_summary(paid_by, amount, description, participant_splits, balances, "You")
                queue_email(user_row['email'], f"Expense Split: {description}", email_summary)
            else:
                print(f"[EXPENSE] ⚠️  No email found for payer")

            return {"status": "ok", "expense_id": expense_id, "splits": participant_splits}

        result = await _run_with_connection(_op)

    return result


@mcp.tool(description="List all shared expenses for the current user with participant details.")
async def list_shared_expenses(token: str, start_date: str = None, end_date: str = None):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async def _op(conn):
        if start_date and end_date:
            rows = await _execute_fetchall(
                conn,
                """
                SELECT id, date, description, total_amount, paid_by
                FROM shared_expenses
                WHERE user_id=$1 AND date BETWEEN $2 AND $3
                ORDER BY date DESC
                """,
                (payload['user_id'], start_date, end_date)
            )
        else:
            rows = await _execute_fetchall(
                conn,
                """
                SELECT id, date, description, total_amount, paid_by
                FROM shared_expenses
                WHERE user_id=$1
                ORDER BY date DESC
                """,
                (payload['user_id'],)
            )

        result = []
        for row in rows:
            expense_id = row['id']
            participants = await _execute_fetchall(
                conn,
                """
                SELECT participant, share_amount
                FROM shared_expense_participants
                WHERE expense_id=$1
                ORDER BY participant ASC
                """,
                (expense_id,)
            )

            result.append({
                "id": expense_id,
                "date": row['date'],
                "description": row['description'],
                "total_amount": row['total_amount'],
                "paid_by": row['paid_by'],
                "participants": [{"name": p['participant'], "share": p['share_amount']} for p in participants]
            })

        return result

    return await _run_with_connection(_op)


@mcp.tool(description="Record a settlement payment and notify the involved parties.")
async def settle_payment(token: str, person: str, amount: float, settlement_date: str, note: str = ""):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    email_tasks = []

    async with db_lock:
        async def _op(conn):
            await conn.execute(
                """
                INSERT INTO settlements(user_id, person, amount, settlement_date, note)
                VALUES ($1,$2,$3,$4,$5)
                """,
                payload['user_id'], person, amount, settlement_date, note
            )

            friend_row = await _execute_fetchone(conn, "SELECT email FROM friends WHERE user_id=$1 AND LOWER(name)=LOWER($2)", (payload['user_id'], person))
            if friend_row and friend_row['email']:
                queue_email(friend_row['email'], "Settlement recorded", f"Hi {person},\n\nA settlement of ₹{amount:.2f} was recorded on {settlement_date}.\n\nNote: {note or 'No note provided'}\n")

            return {"status": "ok", "message": "Settlement recorded"}

        result = await _run_with_connection(_op)

    return result


@mcp.tool(description="Calculate the net balance for each person from shared expenses and settlements.")
async def get_balances(token: str):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async def _op(conn):
        return await _calculate_balances(conn, payload['user_id'])

    return await _run_with_connection(_op)


@mcp.tool(description="List all settlement records made by the current user.")
async def list_settlements(token: str):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async def _op(conn):
        settlements = await _execute_fetchall(
            conn,
            "SELECT id, person, amount, settlement_date, note FROM settlements WHERE user_id=$1 ORDER BY settlement_date DESC",
            (payload['user_id'],)
        )
        return {
            "status": "ok",
            "settlements": [
                {
                    "id": s['id'],
                    "person": s['person'],
                    "amount": s['amount'],
                    "date": s['settlement_date'],
                    "note": s['note']
                }
                for s in settlements
            ]
        }

    return await _run_with_connection(_op)


@mcp.resource("expense://categories", mime_type="application/json")
async def categories():
    categories_file = os.path.join(os.getcwd(), "categories.json")
    if not os.path.exists(categories_file):
        return "[]"
    async with aiofiles.open(categories_file, "r", encoding="utf-8") as f:
        return await f.read()


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
