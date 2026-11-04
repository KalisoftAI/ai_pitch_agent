from datetime import datetime, timedelta

from sales_fastapi.database import SessionLocal
from sales_fastapi.models import GoogleMailbox
from sales_fastapi.security import encrypt_secret


class FakeExtractor:
    calls = []

    def __init__(self, *args):
        self.args = args

    def fetch_emails(self, **kwargs):
        self.calls.append(kwargs)
        return [
            {
                "uid": "42",
                "subject": "Request for quotation",
                "from": "Buyer <buyer@example.com>",
                "date": "Thu, 25 Sep 2026 10:00:00 +0000",
                "intent": "sales",
                "body": "Please send the quotation for 100 units.",
            },
            {
                "uid": "41",
                "subject": "Newsletter",
                "from": "updates@example.com",
                "date": "Wed, 24 Sep 2026 10:00:00 +0000",
                "intent": "general",
                "body": "Monthly updates",
            },
        ]

    def disconnect(self):
        return None


def add_connection(client, headers):
    response = client.post(
        "/api/email/connections",
        json={"email_address": "owner@example.com", "password": "app-password"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_imap_fetch_returns_minimal_context(client, auth_headers, monkeypatch):
    connection_id = add_connection(client, auth_headers)
    FakeExtractor.calls = []
    monkeypatch.setattr("sales_fastapi.routers.email.EmailExtractor", FakeExtractor)

    response = client.post(
        f"/api/email/connections/{connection_id}/fetch",
        json={"query": "quotation", "intent": "sales", "limit": 10},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "imap"
    assert body["count"] == 1
    assert body["messages"][0]["context"].startswith("Please send")
    assert "body" not in body["messages"][0]
    assert FakeExtractor.calls[0]["query"] == "quotation"
    assert FakeExtractor.calls[0]["limit"] == 10


def test_imap_fetch_body_is_explicit_opt_in(client, auth_headers, monkeypatch):
    connection_id = add_connection(client, auth_headers)
    monkeypatch.setattr("sales_fastapi.routers.email.EmailExtractor", FakeExtractor)

    response = client.post(
        f"/api/email/connections/{connection_id}/fetch",
        json={"include_body": True, "context_chars": 80},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["messages"][0]["body"] == "Please send the quotation for 100 units."


def test_imap_fetch_validates_window_and_limit(client, auth_headers):
    connection_id = add_connection(client, auth_headers)

    invalid_limit = client.post(
        f"/api/email/connections/{connection_id}/fetch",
        json={"limit": 51},
        headers=auth_headers,
    )
    invalid_window = client.post(
        f"/api/email/connections/{connection_id}/fetch",
        json={"since": "2026-09-25", "until": "2026-09-01"},
        headers=auth_headers,
    )

    assert invalid_limit.status_code == 422
    assert invalid_window.status_code == 422


def test_imap_fetch_is_user_scoped(client, auth_headers):
    connection_id = add_connection(client, auth_headers)
    other = client.post("/api/auth/google", json={"id_token": "dev:other@example.com"}).json()
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}

    response = client.post(
        f"/api/email/connections/{connection_id}/fetch",
        json={},
        headers=other_headers,
    )

    assert response.status_code == 404


def test_gmail_mailbox_fetch_uses_safe_default(client, auth_headers, monkeypatch):
    user = client.get("/api/auth/me", headers=auth_headers).json()
    db = SessionLocal()
    try:
        mailbox = GoogleMailbox(
            user_id=user["id"],
            email_address="owner@gmail.com",
            access_token_encrypted=encrypt_secret("access-token"),
            refresh_token_encrypted=encrypt_secret("refresh-token"),
            token_expiry=datetime.utcnow() + timedelta(hours=1),
            scopes="https://www.googleapis.com/auth/gmail.readonly",
            is_connected=True,
        )
        db.add(mailbox)
        db.commit()
        db.refresh(mailbox)
        mailbox_id = mailbox.id
    finally:
        db.close()

    class FakeGmailExtractor:
        def __init__(self, access_token):
            self.access_token = access_token

        def fetch_emails(self, **kwargs):
            assert kwargs["include_body"] is False
            return 2, [
                {
                    "uid": "gmail-1",
                    "subject": "Procurement enquiry",
                    "from": "buyer@example.com",
                    "date": "Thu, 25 Sep 2026 10:00:00 +0000",
                    "intent": "procurement",
                    "snippet": "Please share your product details.",
                    "body": "",
                }
            ]

    monkeypatch.setattr("sales_fastapi.routers.google_email.GmailExtractor", FakeGmailExtractor)
    response = client.post(
        f"/api/email/google/mailboxes/{mailbox_id}/fetch",
        json={"intent": "procurement"},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "gmail"
    assert body["count"] == 1
    assert body["messages"][0]["context"].startswith("Please share")
    assert "body" not in body["messages"][0]


def test_google_authorization_reports_configuration(client, auth_headers, monkeypatch):
    from sales_fastapi.config import settings

    assert client.get("/api/email/google/authorize", headers=auth_headers).status_code == 503
    monkeypatch.setattr(settings, "GMAIL_OAUTH_ENABLED", True)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "client.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(
        settings, "GOOGLE_OAUTH_REDIRECT_URI", "https://app.example.test/api/email/google/callback"
    )

    response = client.get("/api/email/google/authorize", headers=auth_headers)

    assert response.status_code == 200, response.text
    assert "gmail.readonly" in response.json()["authorization_url"]
    assert response.json()["expires_in"] == 600
