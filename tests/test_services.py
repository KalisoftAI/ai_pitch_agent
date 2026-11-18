from sales_fastapi.services import (
    check_smtp_connection,
    classify_contact,
    infer_domain,
    infer_intent,
)


def test_infer_domain():
    assert infer_domain("info@mahindraaccelo.com") == "mahindraaccelo.com"
    assert infer_domain("no-at-sign") == ""


def test_infer_intent_keywords():
    assert infer_intent("We need procurement of sheet metal") == "procurement"
    assert infer_intent("Hiring SCM manager") == "hiring"
    assert infer_intent("Request for quotation") == "sales"
    assert infer_intent("hello there") == "general"


def test_classify_contact_full():
    verdict = classify_contact("info@mahindraaccelo.com", "SCM procurement Supa MIDC")
    assert verdict["domain"] == "mahindraaccelo.com"
    assert verdict["intent"] == "procurement"
    assert verdict["context"] == "SCM procurement Supa MIDC"


def test_classify_free_email_still_returns_domain():
    verdict = classify_contact("person@gmail.com", "just saying hi")
    assert verdict["domain"] == "gmail.com"
    assert verdict["intent"] == "general"


def test_smtp_preflight_logs_in_without_sending(monkeypatch):
    events = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=15):
            self.host = host
            self.port = port
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def ehlo(self):
            return 250, b"ok"

        def has_extn(self, name):
            events.append(name)
            return True

        def starttls(self):
            events.append("starttls")

        def login(self, user, password):
            events.append("login")

        def send_message(self, message):
            raise AssertionError("preflight must not deliver mail")

    monkeypatch.setattr("sales_fastapi.services.smtplib.SMTP", FakeSMTP)
    ok, detail = check_smtp_connection("smtp.example.test", 587, "user@example.test", "secret")
    assert ok is True
    assert detail == "connected"
    assert events == ["STARTTLS", "starttls", "login"]
