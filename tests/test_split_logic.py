import importlib.util
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "main.py"

spec = importlib.util.spec_from_file_location("expense_tracker_main", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SplitLogicTests(unittest.TestCase):
    def test_equal_split(self):
        participants = module._build_participant_splits(570, ["Shikhar Bhatia"], "Me")
        self.assertEqual(len(participants), 1)
        self.assertEqual(participants[0]["name"], "Shikhar Bhatia")
        self.assertEqual(participants[0]["share"], 285.0)

    def test_percentage_split(self):
        participants = module._build_participant_splits(570, [{"name": "Shikhar Bhatia", "percent": 50}], "Me")
        self.assertEqual(participants[0]["share"], 285.0)

    def test_parts_split(self):
        participants = module._build_participant_splits(570, [{"name": "Shikhar Bhatia", "parts": 1}, {"name": "Dilip", "parts": 2}], "Me")
        self.assertEqual(participants[0]["share"], 190.0)
        self.assertEqual(participants[1]["share"], 380.0)

    def test_explicit_share_split(self):
        participants = module._build_participant_splits(360, [{"name": "Shikhar Bhatia", "share": 260}, {"name": "You", "share": 100}], "You")
        self.assertEqual(participants[0]["share"], 260.0)
        self.assertEqual(participants[1]["share"], 100.0)

    def test_balances_use_expense_and_settlement_tables(self):
        tmpdir = tempfile.mkdtemp()
        tmp_db = Path(tmpdir) / "expense-test.db"
        try:
            module.DB_PATH = str(tmp_db)
            module.init_db()

            with sqlite3.connect(str(tmp_db)) as conn:
                conn.execute(
                    "INSERT INTO shared_expenses(date, description, total_amount, paid_by) VALUES (?, ?, ?, ?)",
                    ("2024-01-01", "Fuel", 3000.0, "Ashna")
                )
                expense_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.execute(
                    "INSERT INTO shared_expense_participants(expense_id, participant, share_amount) VALUES (?, ?, ?)",
                    (expense_id, "Shikhar Bhatia", 1500.0)
                )
                conn.execute(
                    "INSERT INTO shared_expense_participants(expense_id, participant, share_amount) VALUES (?, ?, ?)",
                    (expense_id, "Ashna", 1500.0)
                )
                conn.execute(
                    "INSERT INTO settlements(person, amount, settlement_date, note) VALUES (?, ?, ?, ?)",
                    ("Shikhar Bhatia", 500.0, "2024-01-02", "partial")
                )

            balances = module.get_balances()

            self.assertAlmostEqual(balances["Shikhar Bhatia"], -1000.0)
            self.assertAlmostEqual(balances["Ashna"], 1500.0)
        finally:
            if tmp_db.exists():
                os.remove(tmp_db)
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
