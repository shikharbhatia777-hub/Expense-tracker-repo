from fastmcp import FastMCP
import asyncio
import os
import aiosqlite
import aiofiles
from email.mime.text import MIMEText
import jwt
import hashlib
import secrets
from datetime import datetime, timedelta, timezone as tz

try:
    import aiosmtplib
except ImportError:
    aiosmtplib = None

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


def _resolve_writable_path(filename: str, env_var: str):
    explicit_path = os.getenv(env_var)
    if explicit_path:
        return explicit_path

    preferred_paths = [
        os.path.join(os.getcwd(), filename),
        os.path.join(os.getcwd(), "data", filename),
        os.path.join("/tmp", "expense_tracker", filename),
    ]

    for path in preferred_paths:
        try:
            parent_dir = os.path.dirname(path) or "."
            os.makedirs(parent_dir, exist_ok=True)
            if os.access(parent_dir, os.W_OK):
                return path
        except Exception:
            continue

    return os.path.join(os.getcwd(), filename)


DB_PATH = _resolve_writable_path("expenses.db", "DB_PATH")
CATEGORIES_PATH = _resolve_writable_path("categories.json", "CATEGORIES_PATH")
ENV_PATH = _resolve_writable_path(".env", "ENV_PATH")

if load_dotenv is not None:
    load_dotenv(ENV_PATH)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "shikharbhatia777@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USERNAME)

JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_urlsafe(32))
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))

mcp = FastMCP("ExpenseTracker")
db_lock = asyncio.Lock()
_db_initialized = False
_current_user_id = None


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


async def _run_with_connection(operation):
    await _ensure_db_initialized()
    async with aiosqlite.connect(DB_PATH) as conn:
        return await operation(conn)


async def _execute_fetchall(conn, query, params=()):
    cursor = await conn.execute(query, params)
    return await cursor.fetchall()


async def _execute_fetchone(conn, query, params=()):
    cursor = await conn.execute(query, params)
    return await cursor.fetchone()


async def init_db():
    global DB_PATH

    candidate_paths = [DB_PATH]
    if DB_PATH != os.path.join("/tmp", "expense_tracker", "expenses.db"):
        candidate_paths.append(os.path.join("/tmp", "expense_tracker", "expenses.db"))

    last_error = None
    for path in candidate_paths:
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

            async def _setup():
                async with aiosqlite.connect(path) as c:
                    await c.execute("PRAGMA journal_mode=WAL")
                    await c.execute("""
                        CREATE TABLE IF NOT EXISTS users(
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT UNIQUE NOT NULL,
                            email TEXT UNIQUE,
                            password_hash TEXT NOT NULL,
                            created_at TEXT NOT NULL
                        )
                    """)
                    await c.execute("""
                        CREATE TABLE IF NOT EXISTS expenses(
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            date TEXT NOT NULL,
                            amount REAL NOT NULL,
                            category TEXT NOT NULL,
                            subcategory TEXT DEFAULT '',
                            note TEXT DEFAULT '',
                            FOREIGN KEY(user_id) REFERENCES users(id)
                        )
                    """)
                    await c.execute("""
                        CREATE TABLE IF NOT EXISTS credits(
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            date TEXT NOT NULL,
                            amount REAL NOT NULL,
                            source TEXT NOT NULL,
                            note TEXT DEFAULT '',
                            FOREIGN KEY(user_id) REFERENCES users(id)
                        )
                    """)
                    await c.execute("""
                        CREATE TABLE IF NOT EXISTS shared_expenses(
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            date TEXT NOT NULL,
                            description TEXT,
                            total_amount REAL NOT NULL,
                            paid_by TEXT NOT NULL,
                            FOREIGN KEY(user_id) REFERENCES users(id)
                        )
                    """)
                    await c.execute("""
                        CREATE TABLE IF NOT EXISTS shared_expense_participants(
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            expense_id INTEGER NOT NULL,
                            participant TEXT NOT NULL,
                            share_amount REAL NOT NULL,
                            FOREIGN KEY(expense_id)
                            REFERENCES shared_expenses(id)
                        )
                    """)
                    await c.execute("""
                        CREATE TABLE IF NOT EXISTS friends(
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            name TEXT NOT NULL,
                            email TEXT,
                            FOREIGN KEY(user_id) REFERENCES users(id),
                            UNIQUE(user_id, name)
                        )
                    """)
                    await c.execute("""
                        CREATE TABLE IF NOT EXISTS settlements(
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            person TEXT NOT NULL,
                            amount REAL NOT NULL,
                            settlement_date TEXT NOT NULL,
                            note TEXT DEFAULT '',
                            FOREIGN KEY(user_id) REFERENCES users(id)
                        )
                    """)
                    await c.commit()

            await _setup()
            DB_PATH = path
            return
        except Exception as exc:
            last_error = exc

    raise RuntimeError(f"Unable to initialize database: {last_error}")


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
        conn, "SELECT id, paid_by FROM shared_expenses WHERE user_id=?", (user_id,)
    )

    for expense_id, paid_by in expense_rows:
        participant_rows = await _execute_fetchall(
            conn, "SELECT participant, share_amount FROM shared_expense_participants WHERE expense_id=?",
            (expense_id,)
        )

        if not participant_rows:
            continue

        payer_name = await _normalize_payer_name(paid_by)
        others_total = 0.0

        for participant, share_amount in participant_rows:
            participant_name = await _normalize_payer_name(participant)
            share_value = round(float(share_amount), 2)

            if participant_name.lower() == payer_name.lower():
                continue

            balances[participant_name] = balances.get(participant_name, 0.0) - share_value
            others_total += share_value

        if payer_name:
            balances[payer_name] = balances.get(payer_name, 0.0) + round(others_total, 2)

    # Get user's name from username for participant lookup
    user_row = await _execute_fetchone(conn, "SELECT username FROM users WHERE id=?", (user_id,))
    username = user_row[0] if user_row else None

    # Include expenses where this user is a participant
    if username:
        participant_expenses = await _execute_fetchall(
            conn, """
            SELECT se.id, se.paid_by, sep.share_amount
            FROM shared_expense_participants sep
            JOIN shared_expenses se ON sep.expense_id = se.id
            WHERE LOWER(sep.participant) = LOWER(?)
            """, (username,)
        )

        for expense_id, paid_by, share_amount in participant_expenses:
            payer_name = await _normalize_payer_name(paid_by)
            share_value = round(float(share_amount), 2)

            if username.lower() != payer_name.lower():
                balances[payer_name] = balances.get(payer_name, 0.0) + share_value

    settlement_rows = await _execute_fetchall(
        conn, "SELECT person, amount FROM settlements WHERE user_id=?", (user_id,)
    )

    for person, amount in settlement_rows:
        person_name = await _normalize_payer_name(person)
        amount_value = round(float(amount), 2)
        current_balance = balances.get(person_name, 0.0)

        if current_balance > 0:
            balances[person_name] = round(current_balance - amount_value, 2)
        elif current_balance < 0:
            balances[person_name] = round(current_balance + amount_value, 2)
        else:
            balances[person_name] = 0.0

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
        print("Email skipped: no recipient provided")
        return False

    if not SMTP_PASSWORD:
        print("Email skipped: SMTP_PASSWORD is not configured")
        return False

    if not aiosmtplib:
        print("Email skipped: aiosmtplib not installed")
        return False

    try:
        text = body if body else ""
        msg = MIMEText(text, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = recipient

        async with aiosmtplib.SMTP(hostname=SMTP_HOST, port=SMTP_PORT) as smtp:
            await smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            await smtp.send_message(msg)

        print(f"Email sent to {recipient}")
        return True
    except Exception as e:
        print(f"Email failed: {e}")
        return False


async def _ensure_db_initialized():
    global _db_initialized
    if not _db_initialized:
        await init_db()
        _db_initialized = True


@mcp.tool(description="Register a new user with username and password.")
async def register_user(username: str, password: str, email: str = ""):
    async with db_lock:
        async def _op(conn):
            existing = await _execute_fetchone(conn, "SELECT id FROM users WHERE username=?", (username,))
            if existing:
                return {"status": "error", "message": "Username already exists"}

            password_hash = _hash_password(password)
            created_at = datetime.now(tz.utc).isoformat()

            cur = await conn.execute(
                "INSERT INTO users(username, email, password_hash, created_at) VALUES (?,?,?,?)",
                (username, email, password_hash, created_at)
            )
            await conn.commit()
            return {"status": "ok", "user_id": cur.lastrowid, "message": "User registered successfully"}

        return await _run_with_connection(_op)


@mcp.tool(description="Login with username and password to get a JWT token.")
async def login(username: str, password: str):
    async def _op(conn):
        user = await _execute_fetchone(conn, "SELECT id, password_hash FROM users WHERE username=?", (username,))
        if not user:
            return {"status": "error", "message": "Invalid username or password"}

        user_id, password_hash = user
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
        user = await _execute_fetchone(conn, "SELECT id, username, email FROM users WHERE id=?", (payload['user_id'],))
        if not user:
            return {"status": "error", "message": "User not found"}

        user_id, username, email = user
        return {"status": "ok", "user_id": user_id, "username": username, "email": email}

    return await _run_with_connection(_op)


@mcp.tool(description="Add a new regular expense entry to the database.")
async def add_expense(token: str, date, amount, category, subcategory="", note=""):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async with db_lock:
        async def _op(conn):
            cur = await conn.execute(
                "INSERT INTO expenses(user_id, date, amount, category, subcategory, note) VALUES (?,?,?,?,?,?)",
                (payload['user_id'], date, amount, category, subcategory, note)
            )
            await conn.commit()
            return {"status": "ok", "id": cur.lastrowid}

        return await _run_with_connection(_op)


@mcp.tool(description="List expense entries within an inclusive date range.")
async def list_expenses(token: str, start_date, end_date):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async def _op(conn):
        cur = await conn.execute(
            """
            SELECT id, date, amount, category, subcategory, note
            FROM expenses
            WHERE user_id=? AND date BETWEEN ? AND ?
            ORDER BY id ASC
            """,
            (payload['user_id'], start_date, end_date)
        )
        cols = [d[0] for d in cur.description]
        rows = await cur.fetchall()
        return [dict(zip(cols, r)) for r in rows]

    return await _run_with_connection(_op)


@mcp.tool(description="Summarize expenses by category within an inclusive date range.")
async def summarize(token: str, start_date, end_date, category=None):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async def _op(conn):
        query = """
            SELECT category, SUM(amount) AS total_amount
            FROM expenses
            WHERE user_id=? AND date BETWEEN ? AND ?
        """
        params = [payload['user_id'], start_date, end_date]

        if category:
            query += " AND category = ?"
            params.append(category)

        query += " GROUP BY category ORDER BY category ASC"

        cur = await conn.execute(query, params)
        cols = [d[0] for d in cur.description]
        rows = await cur.fetchall()
        return [dict(zip(cols, r)) for r in rows]

    return await _run_with_connection(_op)


@mcp.tool(description="Delete an expense using its known details instead of an ID.")
async def delete_expense(token: str, date: str, amount: float, category: str, subcategory: str = None):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async def _op(conn):
        query = """
        SELECT id, date, amount, category, subcategory, note
        FROM expenses
        WHERE user_id=? AND date=? AND amount=? AND category=?
        """

        params = [payload['user_id'], date, amount, category]

        if subcategory:
            query += " AND subcategory=?"
            params.append(subcategory)

        rows = await _execute_fetchall(conn, query, params)

        if len(rows) == 0:
            return {"status": "error", "message": "No matching expense found"}

        if len(rows) > 1:
            return {
                "status": "multiple_matches",
                "matches": [
                    {
                        "id": r[0],
                        "date": r[1],
                        "amount": r[2],
                        "category": r[3],
                        "subcategory": r[4],
                        "note": r[5]
                    }
                    for r in rows
                ]
            }

        expense_id = rows[0][0]
        await conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
        await conn.commit()
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
            WHERE user_id=? AND date=? AND amount=? AND category=?
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
                        "id": r[0],
                        "date": r[1],
                        "amount": r[2],
                        "category": r[3],
                        "subcategory": r[4],
                        "note": r[5]
                    }
                    for r in rows
                ]
            }

        expense = rows[0]
        await conn.execute(
            """
            UPDATE expenses
            SET date=?,
                amount=?,
                category=?,
                subcategory=?,
                note=?
            WHERE id=?
            """,
            (
                new_date if new_date is not None else expense[1],
                new_amount if new_amount is not None else expense[2],
                new_category if new_category is not None else expense[3],
                new_subcategory if new_subcategory is not None else expense[4],
                new_note if new_note is not None else expense[5],
                expense[0]
            )
        )
        await conn.commit()
        return {"status": "ok", "expense_id": expense[0], "message": "Expense updated successfully"}

    return await _run_with_connection(_op)


@mcp.tool(description="Record incoming money such as salary, reimbursement, cashback, refund, or bonus.")
async def add_credit(token: str, date: str, amount: float, source: str, note: str = ""):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async with db_lock:
        async def _op(conn):
            cur = await conn.execute(
                """
                INSERT INTO credits(user_id, date, amount, source, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (payload['user_id'], date, amount, source, note)
            )
            await conn.commit()
            return {"status": "ok", "credit_id": cur.lastrowid, "message": "Credit added successfully"}

        return await _run_with_connection(_op)


@mcp.tool(description="List all credited amounts within a date range.")
async def list_credits(token: str, start_date: str, end_date: str):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async def _op(conn):
        cur = await conn.execute(
            """
            SELECT id, date, amount, source, note
            FROM credits
            WHERE user_id=? AND date BETWEEN ? AND ?
            ORDER BY date ASC
            """,
            (payload['user_id'], start_date, end_date)
        )
        cols = [d[0] for d in cur.description]
        rows = await cur.fetchall()
        return [dict(zip(cols, row)) for row in rows]

    return await _run_with_connection(_op)


@mcp.tool(description="Add a friend to the expense tracker so shared-expense emails can be sent to them.")
async def add_friend(token: str, name: str, email: str):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async with db_lock:
        async def _op(conn):
            await conn.execute("INSERT INTO friends(user_id,name,email) VALUES (?,?,?)", (payload['user_id'], name, email))
            await conn.commit()
            return {"status": "ok", "message": f"{name} added"}

        return await _run_with_connection(_op)


@mcp.tool(description="Update the email address for an existing friend.")
async def update_friend_email(token: str, name: str, new_email: str):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async with db_lock:
        async def _op(conn):
            row = await _execute_fetchone(conn, "SELECT id FROM friends WHERE user_id=? AND LOWER(name)=LOWER(?)", (payload['user_id'], name))
            if not row:
                return {"status": "error", "message": f"Friend '{name}' not found"}
            await conn.execute("UPDATE friends SET email=? WHERE user_id=? AND LOWER(name)=LOWER(?)", (new_email, payload['user_id'], name))
            await conn.commit()
            return {"status": "ok", "message": f"Email updated for {name}"}

        return await _run_with_connection(_op)


@mcp.tool(description="List the friends that are currently registered in the tracker.")
async def list_friends(token: str):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async def _op(conn):
        # Get current user info
        user_row = await _execute_fetchone(conn, "SELECT email, username FROM users WHERE id=?", (payload['user_id'],))
        if not user_row:
            return []

        user_email, username = user_row

        # Get explicit friends (added by this user)
        explicit_rows = await _execute_fetchall(
            conn,
            "SELECT id, name, email FROM friends WHERE user_id=?",
            (payload['user_id'],)
        )
        explicit_friends = [{'id': r[0], 'name': r[1], 'email': r[2]} for r in explicit_rows]

        # Get implicit friends (people who added this user as a friend)
        # Find all friend entries where the email or name matches this user
        implicit_rows = await _execute_fetchall(
            conn, """
            SELECT DISTINCT f.user_id FROM friends f
            WHERE (
                (f.email IS NOT NULL AND LOWER(f.email) = LOWER(?))
                OR (f.name IS NOT NULL AND LOWER(f.name) = LOWER(?))
            )
            AND f.user_id != ?
            """,
            (user_email or '', username, payload['user_id'])
        )

        implicit_friends = []
        seen_emails = {f['email'] for f in explicit_friends if f['email']}

        for (adder_user_id,) in implicit_rows:
            adder_row = await _execute_fetchone(
                conn,
                "SELECT username, email FROM users WHERE id=?",
                (adder_user_id,)
            )
            if adder_row:
                adder_username, adder_email = adder_row
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

    email_tasks = []

    async with db_lock:
        async def _op(conn):
            cur = await conn.execute(
                """
                INSERT INTO shared_expenses(user_id, date, description, total_amount, paid_by)
                VALUES (?,?,?,?,?)
                """,
                (payload['user_id'], date, description, amount, payer_name)
            )
            expense_id = cur.lastrowid

            for entry in participant_splits:
                await conn.execute(
                    """
                    INSERT INTO shared_expense_participants(expense_id, participant, share_amount)
                    VALUES (?,?,?)
                    """,
                    (expense_id, entry["name"], entry["share"])
                )

            balances = await _calculate_balances(conn, payload['user_id'])

            for entry in participant_splits:
                person = entry["name"]
                email_row = await _execute_fetchone(
                    conn, "SELECT email FROM friends WHERE user_id=? AND LOWER(name)=LOWER(?)",
                    (payload['user_id'], person)
                )

                if email_row and email_row[0]:
                    email_summary = await _build_email_summary(paid_by, amount, description, participant_splits, balances, person)
                    email_tasks.append(send_email(email_row[0], f"Expense Split: {description}", email_summary))

            await conn.commit()
            return {"status": "ok", "expense_id": expense_id, "splits": participant_splits}

        result = await _run_with_connection(_op)

    if email_tasks:
        await asyncio.gather(*email_tasks, return_exceptions=True)

    return result


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
                VALUES (?,?,?,?,?)
                """,
                (payload['user_id'], person, amount, settlement_date, note)
            )

            friend_row = await _execute_fetchone(conn, "SELECT email FROM friends WHERE user_id=? AND LOWER(name)=LOWER(?)", (payload['user_id'], person))
            if friend_row and friend_row[0]:
                email_tasks.append(send_email(friend_row[0], "Settlement recorded", f"Hi {person},\n\nA settlement of ₹{amount:.2f} was recorded on {settlement_date}.\n\nNote: {note or 'No note provided'}\n"))

            await conn.commit()
            return {"status": "ok", "message": "Settlement recorded"}

        result = await _run_with_connection(_op)

    if person and person.lower() != "you":
        email_tasks.append(send_email(SMTP_USERNAME, "Settlement recorded", f"Hi there,\n\nA settlement of ₹{amount:.2f} was recorded for {person} on {settlement_date}.\n\nNote: {note or 'No note provided'}\n"))

    if email_tasks:
        await asyncio.gather(*email_tasks, return_exceptions=True)

    return result


@mcp.tool(description="Calculate the net balance for each person from shared expenses and settlements.")
async def get_balances(token: str):
    payload = _verify_token(token)
    if not payload:
        return {"status": "error", "message": "Invalid or expired token"}

    async def _op(conn):
        return await _calculate_balances(conn, payload['user_id'])

    return await _run_with_connection(_op)


@mcp.resource("expense://categories", mime_type="application/json")
async def categories():
    async with aiofiles.open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
        return await f.read()


if __name__ == "__main__":
    mcp.run()
