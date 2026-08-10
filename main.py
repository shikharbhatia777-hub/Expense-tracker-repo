from fastmcp import FastMCP
import os
import sqlite3
import smtplib
from email.mime.text import MIMEText
from collections import defaultdict

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

mcp = FastMCP("ExpenseTracker")

def init_db():
    global DB_PATH

    candidate_paths = [DB_PATH]
    if DB_PATH != os.path.join("/tmp", "expense_tracker", "expenses.db"):
        candidate_paths.append(os.path.join("/tmp", "expense_tracker", "expenses.db"))

    last_error = None
    for path in candidate_paths:
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with sqlite3.connect(path) as c:
                c.execute("""
                    CREATE TABLE IF NOT EXISTS expenses(
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL,
                        amount REAL NOT NULL,
                        category TEXT NOT NULL,
                        subcategory TEXT DEFAULT '',
                        note TEXT DEFAULT ''
                    )
                """)
                c.execute("""
            CREATE TABLE IF NOT EXISTS credits(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                source TEXT NOT NULL,
                note TEXT DEFAULT ''
            )

        """)
                c.execute("""
                CREATE TABLE IF NOT EXISTS shared_expenses(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                description TEXT,
                total_amount REAL NOT NULL,
                paid_by TEXT NOT NULL
            )
            """)
                c.execute("""
                CREATE TABLE IF NOT EXISTS shared_expense_participants(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_id INTEGER NOT NULL,
                participant TEXT NOT NULL,
                share_amount REAL NOT NULL,
                FOREIGN KEY(expense_id)
                REFERENCES shared_expenses(id)
                )
                """)
                c.execute("""
                    CREATE TABLE IF NOT EXISTS friends(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE
                    )
                    """)

                c.execute("""
                CREATE TABLE IF NOT EXISTS settlements(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person TEXT NOT NULL,
                    amount REAL NOT NULL,
                    settlement_date TEXT NOT NULL,
                    note TEXT DEFAULT ''
                )
                """)
            DB_PATH = path
            return
        except Exception as exc:
            last_error = exc

    raise RuntimeError(f"Unable to initialize database: {last_error}")
init_db()

@mcp.tool()
def add_expense(date, amount, category, subcategory="", note=""):
    '''Add a new expense entry to the database.'''
    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            "INSERT INTO expenses(date, amount, category, subcategory, note) VALUES (?,?,?,?,?)",
            (date, amount, category, subcategory, note)
        )
        return {"status": "ok", "id": cur.lastrowid}
    
@mcp.tool()
def list_expenses(start_date, end_date):
    '''List expense entries within an inclusive date range.'''
    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            """
            SELECT id, date, amount, category, subcategory, note
            FROM expenses
            WHERE date BETWEEN ? AND ?
            ORDER BY id ASC
            """,
            (start_date, end_date)
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

@mcp.tool()
def summarize(start_date, end_date, category=None):
    '''Summarize expenses by category within an inclusive date range.'''
    with sqlite3.connect(DB_PATH) as c:
        query = (
            """
            SELECT category, SUM(amount) AS total_amount
            FROM expenses
            WHERE date BETWEEN ? AND ?
            """
        )
        params = [start_date, end_date]

        if category:
            query += " AND category = ?"
            params.append(category)

        query += " GROUP BY category ORDER BY category ASC"

        cur = c.execute(query, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
@mcp.tool()
def delete_expense(
    date: str,
    amount: float,
    category: str,
    subcategory: str = None
):
    """Delete an expense using details instead of ID."""

    with sqlite3.connect(DB_PATH) as c:
        query = """
        SELECT id, date, amount, category, subcategory, note
        FROM expenses
        WHERE date=? AND amount=? AND category=?
        """

        params = [date, amount, category]

        if subcategory:
            query += " AND subcategory=?"
            params.append(subcategory)

        rows = c.execute(query, params).fetchall()

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

        c.execute(
            "DELETE FROM expenses WHERE id=?",
            (expense_id,)
        )

        return {
            "status": "ok",
            "deleted_id": expense_id
        }

@mcp.tool()
def edit_expense(
    old_date: str,
    old_amount: float,
    old_category: str,
    new_date: str = None,
    new_amount: float = None,
    new_category: str = None,
    new_subcategory: str = None,
    new_note: str = None
):
    """Edit an existing expense using known details."""

    with sqlite3.connect(DB_PATH) as c:
        rows = c.execute(
            """
            SELECT id, date, amount, category, subcategory, note
            FROM expenses
            WHERE date=? AND amount=? AND category=?
            """,
            (old_date, old_amount, old_category)
        ).fetchall()

        if len(rows) == 0:
            return {
                "status": "error",
                "message": "No matching expense found."
            }

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

        c.execute(
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

        return {
            "status": "ok",
            "expense_id": expense[0],
            "message": "Expense updated successfully"
        }

@mcp.tool()
def add_credit(
    date: str,
    amount: float,
    source: str,
    note: str = ""
):
    """
    Record incoming money such as salary, reimbursement,
    cashback, refund, bonus, etc.
    """

    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            """
            INSERT INTO credits(date, amount, source, note)
            VALUES (?, ?, ?, ?)
            """,
            (date, amount, source, note)
        )

        return {
            "status": "ok",
            "credit_id": cur.lastrowid,
            "message": "Credit added successfully"
        }

@mcp.tool()
def list_credits(
    start_date: str,
    end_date: str
):
    """
    List all credited amounts within a date range.
    """

    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            """
            SELECT
                id,
                date,
                amount,
                source,
                note
            FROM credits
            WHERE date BETWEEN ? AND ?
            ORDER BY date ASC
            """,
            (start_date, end_date)
        )

        cols = [d[0] for d in cur.description]

        return [
            dict(zip(cols, row))
            for row in cur.fetchall()
        ]

#################################################################################3
@mcp.tool()
def add_friend(name: str, email: str):
    """Add a friend."""

    with sqlite3.connect(DB_PATH) as c:
        c.execute(
            """
            INSERT INTO friends(name,email)
            VALUES (?,?)
            """,
            (name, email)
        )

    return {
        "status": "ok",
        "message": f"{name} added"
    }

@mcp.tool()
def update_friend_email(name: str, new_email: str):
    """Update the email address for an existing friend."""

    with sqlite3.connect(DB_PATH) as c:
        row = c.execute(
            "SELECT id FROM friends WHERE LOWER(name)=LOWER(?)",
            (name,)
        ).fetchone()

        if not row:
            return {"status": "error", "message": f"Friend '{name}' not found"}

        c.execute(
            "UPDATE friends SET email=? WHERE LOWER(name)=LOWER(?)",
            (new_email, name)
        )

    return {
        "status": "ok",
        "message": f"Email updated for {name}"
    }

@mcp.tool()
def list_friends():
    """List all friends."""

    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            "SELECT id,name,email FROM friends"
        )

        cols = [d[0] for d in cur.description]

        return [
            dict(zip(cols, row))
            for row in cur.fetchall()
        ]

def send_email(recipient, subject, body):
    if not recipient:
        print("Email skipped: no recipient provided")
        return False

    if not SMTP_PASSWORD:
        print("Email skipped: SMTP_PASSWORD is not configured")
        return False

    try:
        text = body if body else ""
        msg = MIMEText(text, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = recipient

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, recipient, msg.as_string())

        print(f"Email sent to {recipient}")
        return True

    except Exception as e:
        print(f"Email failed: {e}")
        return False

def _normalize_payer_name(paid_by: str):
    if not paid_by:
        return "You"
    lowered = str(paid_by).strip().lower()
    if lowered in {"me", "i", "myself", "my", "self"}:
        return "You"
    return str(paid_by).strip()


def _calculate_balances(conn):
    balances = {}

    expense_rows = conn.execute(
        "SELECT id, paid_by FROM shared_expenses"
    ).fetchall()

    for expense_id, paid_by in expense_rows:
        participant_rows = conn.execute(
            "SELECT participant, share_amount FROM shared_expense_participants WHERE expense_id=?",
            (expense_id,)
        ).fetchall()

        if not participant_rows:
            continue

        payer_name = _normalize_payer_name(paid_by)
        others_total = 0.0

        for participant, share_amount in participant_rows:
            participant_name = _normalize_payer_name(participant)
            share_value = round(float(share_amount), 2)

            if participant_name.lower() == payer_name.lower():
                continue

            balances[participant_name] = balances.get(participant_name, 0.0) - share_value
            others_total += share_value

        if payer_name:
            balances[payer_name] = balances.get(payer_name, 0.0) + round(others_total, 2)

    settlement_rows = conn.execute(
        "SELECT person, amount FROM settlements"
    ).fetchall()

    for person, amount in settlement_rows:
        person_name = _normalize_payer_name(person)
        amount_value = round(float(amount), 2)
        current_balance = balances.get(person_name, 0.0)

        if current_balance > 0:
            balances[person_name] = round(current_balance - amount_value, 2)
        elif current_balance < 0:
            balances[person_name] = round(current_balance + amount_value, 2)
        else:
            balances[person_name] = 0.0

    return {name: round(balance, 2) for name, balance in balances.items()}


def _coerce_number(value):
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


def _build_participant_splits(amount: float, participants: list, paid_by: str):
    if not participants:
        return []

    normalized = []
    for entry in participants:
        if isinstance(entry, str):
            normalized.append({"name": entry, "percent": None, "parts": None, "share": None})
        elif isinstance(entry, dict):
            normalized.append({
                "name": entry.get("name") or entry.get("participant") or entry.get("person"),
                "percent": _coerce_number(entry.get("percent") or entry.get("percentage")),
                "parts": _coerce_number(entry.get("parts") or entry.get("ratio") or entry.get("weight")),
                "share": _coerce_number(entry.get("share") or entry.get("amount") or entry.get("value") or entry.get("owed") or entry.get("pay_amount"))
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


def _build_email_summary(paid_by: str, amount: float, description: str, participant_splits: list, balances: dict, recipient_name: str):
    payer_name = _normalize_payer_name(paid_by)
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

    settle_amount = None
    if recipient_balance is not None:
        settle_amount = abs(recipient_balance) if recipient_balance < 0 else 0.0
    elif recipient_share is not None:
        settle_amount = recipient_share

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

@mcp.tool()
def edit_shared_expense(
    expense_id: int,
    new_date: str = None,
    new_amount: float = None,
    new_paid_by: str = None,
    new_description: str = None,
    new_participants: list = None
):
    """Edit an existing shared expense and its participant shares."""
    with sqlite3.connect(DB_PATH) as c:
        rows = c.execute(
            "SELECT id, date, description, total_amount, paid_by FROM shared_expenses WHERE id=?",
            (expense_id,)
        ).fetchall()
        if not rows:
            return {"status": "error", "message": "Shared expense not found"}

        expense = rows[0]
        date_value = new_date if new_date is not None else expense[1]
        description_value = new_description if new_description is not None else expense[2]
        amount_value = new_amount if new_amount is not None else expense[3]
        paid_by_value = new_paid_by if new_paid_by is not None else expense[4]

        c.execute(
            "DELETE FROM shared_expense_participants WHERE expense_id=?",
            (expense_id,)
        )

        c.execute(
            "UPDATE shared_expenses SET date=?, description=?, total_amount=?, paid_by=? WHERE id=?",
            (date_value, description_value, amount_value, paid_by_value, expense_id)
        )

        if new_participants is not None:
            participant_splits = _build_participant_splits(amount_value, new_participants, paid_by_value)
            for entry in participant_splits:
                c.execute(
                    "INSERT INTO shared_expense_participants(expense_id, participant, share_amount) VALUES (?,?,?)",
                    (expense_id, entry["name"], entry["share"])
                )
        else:
            participant_splits = []

        return {
            "status": "ok",
            "expense_id": expense_id,
            "splits": participant_splits
        }

@mcp.tool()
def delete_shared_expense(expense_id: int):
    """Delete a shared expense and all of its participant rows."""
    with sqlite3.connect(DB_PATH) as c:
        rows = c.execute("SELECT id FROM shared_expenses WHERE id=?", (expense_id,)).fetchall()
        if not rows:
            return {"status": "error", "message": "Shared expense not found"}

        c.execute("DELETE FROM shared_expense_participants WHERE expense_id=?", (expense_id,))
        c.execute("DELETE FROM shared_expenses WHERE id=?", (expense_id,))

        return {"status": "ok", "deleted_expense_id": expense_id}

@mcp.tool()
def list_shared_expenses():
    """List all shared expense records."""
    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            "SELECT id, date, description, total_amount, paid_by FROM shared_expenses ORDER BY id ASC"
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

@mcp.tool()
def add_shared_expense(
    date: str,
    amount: float,
    paid_by: str,
    participants: list,
    description: str = ""
):
    """
    Split expense equally or by percentage/parts.
    """

    participant_splits = _build_participant_splits(amount, participants, paid_by)
    payer_name = _normalize_payer_name(paid_by)

    with sqlite3.connect(DB_PATH) as c:

        cur = c.execute(
            """
            INSERT INTO shared_expenses(
                date,
                description,
                total_amount,
                paid_by
            )
            VALUES (?,?,?,?)
            """,
            (
                date,
                description,
                amount,
                payer_name
            )
        )

        expense_id = cur.lastrowid

        for entry in participant_splits:
            person = entry["name"]

            c.execute(
                """
                INSERT INTO shared_expense_participants(
                    expense_id,
                    participant,
                    share_amount
                )
                VALUES (?,?,?)
                """,
                (
                    expense_id,
                    person,
                    entry["share"]
                )
            )

        balances = _calculate_balances(c)

        for entry in participant_splits:
            person = entry["name"]
            email_row = c.execute(
                """
                SELECT email
                FROM friends
                WHERE LOWER(name)=LOWER(?)
                """,
                (person,)
            ).fetchone()

            if email_row and email_row[0]:
                send_email(
                    email_row[0],
                    f"Expense Split: {description}",
                    _build_email_summary(
                        paid_by,
                        amount,
                        description,
                        participant_splits,
                        balances,
                        person
                    )
                )

    return {
        "status": "ok",
        "expense_id": expense_id,
        "splits": participant_splits
    }

@mcp.tool()
def settle_payment(
    person: str,
    amount: float,
    settlement_date: str,
    note: str = ""
):
    """Record settlement and notify both parties."""

    with sqlite3.connect(DB_PATH) as c:
        c.execute(
            """
            INSERT INTO settlements(
                person,
                amount,
                settlement_date,
                note
            )
            VALUES (?,?,?,?)
            """,
            (
                person,
                amount,
                settlement_date,
                note
            )
        )

        friend_row = c.execute(
            "SELECT email FROM friends WHERE LOWER(name)=LOWER(?)",
            (person,)
        ).fetchone()

        if friend_row and friend_row[0]:
            send_email(
                friend_row[0],
                "Settlement recorded",
                f"Hi {person},\n\nA settlement of ₹{amount:.2f} was recorded on {settlement_date}.\n\nNote: {note or 'No note provided'}\n"
            )

    if person and person.lower() != "you":
        send_email(
            SMTP_USERNAME,
            "Settlement recorded",
            f"Hi there,\n\nA settlement of ₹{amount:.2f} was recorded for {person} on {settlement_date}.\n\nNote: {note or 'No note provided'}\n"
        )

    return {
        "status": "ok",
        "message": "Settlement recorded"
    }

@mcp.tool()
def get_balances():

    with sqlite3.connect(DB_PATH) as c:
        balances = _calculate_balances(c)

    return balances


@mcp.resource("expense://categories", mime_type="application/json")
def categories():
    # Read fresh each time so you can edit the file without restarting
    with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    #mcp.run()
    mcp.run(transport="http", host="0.0.0.0", port=8000)