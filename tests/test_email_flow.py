import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "main.py"

spec = importlib.util.spec_from_file_location("expense_tracker_main", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_send_email_uses_smtp(monkeypatch):
    calls = []

    class DummySMTP:
        def __init__(self, host, port):
            calls.append((host, port))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self):
            calls.append("starttls")

        def login(self, user, password):
            calls.append((user, password))

        def send_message(self, msg):
            calls.append(msg)

    monkeypatch.setattr(module.smtplib, "SMTP", DummySMTP)

    module.send_email("friend@example.com", "Hello", "Body")

    assert calls[0] == ("smtp.gmail.com", 587)
    assert calls[1] == "starttls"
    assert calls[2][0] == "shikharbhatia777@gmail.com"
