import re

from sales_fastapi.config import settings


class FakeMailSender:
    calls = []
    credentials = []

    def __init__(self, host, port, user, password):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        FakeMailSender.credentials.append({"user": user, "password": password})

    def send(self, to, subject, body, from_email=None, *, html=False, retries=2):
        FakeMailSender.calls.append({"to": to, "subject": subject, "body": body, "html": html})
        return {"sent": True, "to": to, "message_id": "fake@kalika.local"}


class FakeExtractor:
    def __init__(self, *args):
        self.args = args

    def connect(self):
        return None

    def disconnect(self):
        return None


def _headers(client, email):
    token = client.post("/api/auth/google", json={"id_token": f"dev:{email}"}).json()
    return {"Authorization": f"Bearer {token['access_token']}"}


def _connection(client, headers, email="owner@example.com"):
    response = client.post(
        "/api/email/connections",
        json={"email_address": email, "password": "app-password", "smtp_host": "smtp.example.test"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _template(client, headers, body):
    response = client.post(
        "/api/templates",
        json={
            "name": "Mail tracking template",
            "channel": "email",
            "strategy": "cold_outreach",
            "subject": "Hello {{company}}",
            "body": body,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _setup_campaign(client, headers, monkeypatch, body, connection_id=None, sender_key=None):
    FakeMailSender.calls = []
    FakeMailSender.credentials = []
    monkeypatch.setattr("sales_fastapi.routers.campaigns.MailSender", FakeMailSender)
    monkeypatch.setattr(
        "sales_fastapi.routers.campaigns.check_smtp_connection", lambda *a, **k: (True, "connected")
    )
    monkeypatch.setattr(settings, "TRACKING_BASE_URL", "https://mail.example.test")

    contact = client.post(
        "/api/contacts",
        json={"email": "buyer@acme.test", "company": "Acme", "name": "Ravi"},
        headers=headers,
    ).json()
    template_id = _template(client, headers, body)
    payload = {
        "name": "Template send",
        "channel": "email",
        "template_id": template_id,
        "use_ai": False,
        "auto_send": True,
        "filter": {"contact_ids": [contact["id"]]},
    }
    if connection_id is not None:
        payload["connection_id"] = connection_id
    if sender_key is not None:
        payload["sender_key"] = sender_key
    response = client.post("/api/campaigns", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_html_template_send_tracks_open_and_counts_are_consistent(
    client, auth_headers, monkeypatch
):
    connection_id = _connection(client, auth_headers)
    campaign = _setup_campaign(
        client,
        auth_headers,
        monkeypatch,
        "<html><body>Hello {{company}}</body></html>",
        connection_id,
    )

    assert campaign["status"] == "completed"
    assert campaign["sent_count"] == 1
    assert FakeMailSender.calls[0]["html"] is True
    assert "Hello Acme" in FakeMailSender.calls[0]["body"]

    match = re.search(
        r"https://mail\.example\.test/api/campaigns/track/open/([A-Za-z0-9.]+)",
        FakeMailSender.calls[0]["body"],
    )
    assert match is not None
    token = match.group(1)

    head = client.head(f"/api/campaigns/track/open/{token}")
    assert head.status_code == 200
    detail = client.get(f"/api/campaigns/{campaign['id']}", headers=auth_headers).json()
    assert detail["opened_count"] == 0

    opened = client.get(f"/api/campaigns/track/open/{token}")
    assert opened.status_code == 200
    assert opened.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
    client.get(f"/api/campaigns/track/open/{token}")

    detail = client.get(f"/api/campaigns/{campaign['id']}", headers=auth_headers).json()
    assert detail["opened_count"] == 1
    assert detail["messages"][0]["status"] == "opened"
    assert detail["messages"][0]["opened_at"] is not None

    listed = client.get("/api/campaigns", headers=auth_headers).json()
    assert listed[0]["opened_count"] == 1

    analytics = client.get("/api/campaigns/analytics", headers=auth_headers).json()
    assert analytics["totals"]["opened"] == 1

    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
    client.get(f"/api/campaigns/track/open/{tampered}")
    detail = client.get(f"/api/campaigns/{campaign['id']}", headers=auth_headers).json()
    assert detail["opened_count"] == 1


def test_plain_text_template_is_wrapped_for_tracking(client, auth_headers, monkeypatch):
    connection_id = _connection(client, auth_headers)
    campaign = _setup_campaign(
        client, auth_headers, monkeypatch, "Hello {{company}}", connection_id
    )

    body = FakeMailSender.calls[0]["body"]
    assert FakeMailSender.calls[0]["html"] is True
    assert body.startswith("<html><body>Hello Acme")
    assert "/api/campaigns/track/open/" in body
    assert campaign["sent_count"] == 1


def test_email_send_fails_fast_without_connection(client, auth_headers):
    contact = client.post(
        "/api/contacts",
        json={"email": "buyer@acme.test", "company": "Acme", "name": "Ravi"},
        headers=auth_headers,
    ).json()
    created = client.post(
        "/api/campaigns",
        json={
            "name": "No connection",
            "channel": "email",
            "template_id": _template(client, auth_headers, "<p>Hello</p>"),
            "use_ai": False,
            "filter": {"contact_ids": [contact["id"]]},
        },
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    campaign = created.json()
    client.post(f"/api/campaigns/{campaign['id']}/approve", headers=auth_headers)

    failed = client.post(f"/api/campaigns/{campaign['id']}/send", headers=auth_headers)
    assert failed.status_code == 400
    assert "No email connection" in failed.json()["detail"]
    detail = client.get(f"/api/campaigns/{campaign['id']}", headers=auth_headers).json()
    assert detail["messages"][0]["status"] == "approved"


def test_connection_test_checks_smtp_without_sending(client, auth_headers, monkeypatch):
    connection_id = _connection(client, auth_headers)
    monkeypatch.setattr("sales_fastapi.routers.email.EmailExtractor", FakeExtractor)
    monkeypatch.setattr(
        "sales_fastapi.routers.email.check_smtp_connection", lambda *a, **k: (True, "connected")
    )

    class NoSend:
        def __init__(self, *args):
            raise AssertionError("test endpoint must not send mail")

    monkeypatch.setattr("sales_fastapi.routers.email.MailSender", NoSend)
    response = client.post(f"/api/email/connections/{connection_id}/test", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["smtp"] == "connected"
    assert response.json()["imap"] == "connected"
    assert response.json()["is_connected"] is True


def test_all_user_mail_provisioning_and_status_are_admin_only(client, auth_headers, monkeypatch):
    other_headers = _headers(client, "other@example.com")
    _headers(client, "kalika@kalika.local")
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")
    monkeypatch.setattr(settings, "IMAP_HOST", "imap.example.test")
    monkeypatch.setattr(settings, "IMAP_PORT", 993)
    monkeypatch.setattr(settings, "IMAP_USER", "")
    monkeypatch.setattr(settings, "GMAIL_ADDRESS", "")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD", "")
    monkeypatch.setattr(settings, "GMAIL_ADDRESS_KALISOFTAI", "kalisoftai@example.test")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD_KALISOFTAI", "kalisoftai-pass-test")
    monkeypatch.setattr(settings, "GMAIL_ADDRESS_KALIKA", "kalika@example.test")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD_KALIKA", "kalika-pass-test")

    checked = []

    def fake_check(host, port, user, password):
        checked.append((user, password))
        return True, "connected"

    monkeypatch.setattr("sales_fastapi.routers.email.check_smtp_connection", fake_check)

    provisioned = client.post("/api/email/default-connection/all", headers=auth_headers)
    assert provisioned.status_code == 200, provisioned.text
    result = provisioned.json()
    assert result["count"] >= 3
    assert all(item["smtp_ok"] for item in result["results"])
    assert all(item["created"] for item in result["results"])
    assert all("password" not in str(item).lower() for item in result["results"])
    assert {item["organization"] for item in result["results"]} == {"kalisoftai", "kalika"}
    assert {user for user, _ in checked} == {"kalisoftai@example.test", "kalika@example.test"}
    assert all(
        password
        == ("kalika-pass-test" if user == "kalika@example.test" else "kalisoftai-pass-test")
        for user, password in checked
    )

    status = client.get("/api/email/smtp-status/all", headers=auth_headers)
    assert status.status_code == 200, status.text
    emails = {item["user_email"] for item in status.json()["results"]}
    assert {"tester@kalisoftai.com", "other@example.com", "kalika@kalika.local"}.issubset(emails)
    assert "password" not in status.text.lower()

    assert (
        client.post("/api/email/default-connection/all", headers=other_headers).status_code == 403
    )
    assert client.get("/api/email/smtp-status/all", headers=other_headers).status_code == 403


def test_gmail_credentials_are_isolated_by_organization(monkeypatch):
    monkeypatch.setattr(settings, "GMAIL_ADDRESS_KALISOFTAI", "kalisoftai@example.test")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD_KALISOFTAI", "kalisoftai-pass-test")
    monkeypatch.setattr(settings, "GMAIL_ADDRESS_KALIKA", "kalika@example.test")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD_KALIKA", "kalika-pass-test")
    monkeypatch.setattr(settings, "SMTP_USER", "kalisoftai@example.test")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "explicit-pass-test")

    assert settings.gmail_organization("kalika@kalika.local", "") == "kalika"
    assert settings.gmail_organization("kalika@example.test", "") == "kalika"
    assert settings.gmail_organization("tester@kalisoftai.com", "kalisoftai.com") == "kalisoftai"
    assert settings.gmail_credentials("kalika") == ("kalika@example.test", "kalika-pass-test")
    assert settings.gmail_credentials("kalisoftai") == (
        "kalisoftai@example.test",
        "explicit-pass-test",
    )


def test_gmail_senders_expose_both_kalika_accounts(monkeypatch):
    monkeypatch.setattr(settings, "GMAIL_ADDRESS", "")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD", "")
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")
    monkeypatch.setattr(settings, "GMAIL_ADDRESS_KALISOFTAI", "kalisoftai@example.test")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD_KALISOFTAI", "kalisoftai-pass-test")
    monkeypatch.setattr(settings, "GMAIL_ADDRESS_KALIKA", "kalika@example.test")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD_KALIKA", "kalika-pass-test")
    monkeypatch.setattr(settings, "GMAIL_ADDRESS_KALIKA2", "kalika-primary@example.test")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD_KALIKA2", "kalika-primary-pass-test")

    senders = settings.gmail_senders("kalika@kalika.local", "")
    assert senders == [
        {
            "key": "kalika",
            "email_address": "kalika@example.test",
            "label": "Kalika sales",
            "is_default": True,
        },
        {
            "key": "kalika2",
            "email_address": "kalika-primary@example.test",
            "label": "Kalika primary",
            "is_default": False,
        },
    ]
    assert settings.gmail_organization("kalika-primary@example.test", "") == "kalika"
    assert settings.gmail_credentials_for_key("kalika", "kalika2") == (
        "kalika-primary@example.test",
        "kalika-primary-pass-test",
    )
    assert len(settings.gmail_senders("tester@kalisoftai.com", "kalisoftai.com")) == 1


def test_sender_options_endpoint_hides_passwords(client, monkeypatch):
    monkeypatch.setattr(settings, "GMAIL_ADDRESS", "")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD", "")
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")
    monkeypatch.setattr(settings, "GMAIL_ADDRESS_KALISOFTAI", "kalisoftai@example.test")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD_KALISOFTAI", "kalisoftai-pass-test")
    monkeypatch.setattr(settings, "GMAIL_ADDRESS_KALIKA", "kalika@example.test")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD_KALIKA", "kalika-pass-test")
    monkeypatch.setattr(settings, "GMAIL_ADDRESS_KALIKA2", "kalika-primary@example.test")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD_KALIKA2", "kalika-primary-pass-test")

    headers = _headers(client, "kalika@kalika.local")
    response = client.get("/api/email/senders", headers=headers)
    assert response.status_code == 200, response.text
    assert [row["key"] for row in response.json()] == ["kalika", "kalika2"]
    assert "pass" not in response.text


def test_campaign_uses_selected_sender_key(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "GMAIL_ADDRESS", "")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD", "")
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")
    monkeypatch.setattr(settings, "GMAIL_ADDRESS_KALISOFTAI", "kalisoftai@example.test")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD_KALISOFTAI", "kalisoftai-pass-test")
    monkeypatch.setattr(settings, "GMAIL_ADDRESS_KALIKA", "kalika@example.test")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD_KALIKA", "kalika-pass-test")
    monkeypatch.setattr(settings, "GMAIL_ADDRESS_KALIKA2", "kalika-primary@example.test")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD_KALIKA2", "kalika-primary-pass-test")

    headers = _headers(client, "kalika@kalika.local")
    connection_id = _connection(client, headers, "kalika@example.test")
    campaign = _setup_campaign(
        client,
        headers,
        monkeypatch,
        "<p>Hello</p>",
        connection_id,
        sender_key="kalika2",
    )
    assert campaign["status"] == "completed"
    assert FakeMailSender.credentials[0] == {
        "user": "kalika-primary@example.test",
        "password": "kalika-primary-pass-test",
    }
    connections = client.get("/api/email/connections", headers=headers).json()
    assert any(row["email_address"] == "kalika-primary@example.test" for row in connections)


def test_campaign_uses_user_organization_smtp_account(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "GMAIL_ADDRESS", "")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD", "")
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")
    monkeypatch.setattr(settings, "GMAIL_ADDRESS_KALISOFTAI", "kalisoftai@example.test")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD_KALISOFTAI", "kalisoftai-pass-test")
    monkeypatch.setattr(settings, "GMAIL_ADDRESS_KALIKA", "kalika@example.test")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD_KALIKA", "kalika-pass-test")

    kalika_headers = _headers(client, "kalika@kalika.local")
    kalika_conn = client.post("/api/email/default-connection", headers=kalika_headers).json()
    assert kalika_conn["email_address"] == "kalika@example.test"
    kalika_campaign = _setup_campaign(
        client, kalika_headers, monkeypatch, "<p>Hello</p>", kalika_conn["id"]
    )
    assert kalika_campaign["status"] == "completed"
    assert FakeMailSender.credentials[0] == {
        "user": "kalika@example.test",
        "password": "kalika-pass-test",
    }

    kalisoftai_conn = client.post("/api/email/default-connection", headers=auth_headers).json()
    assert kalisoftai_conn["email_address"] == "kalisoftai@example.test"
    kalisoftai_campaign = _setup_campaign(
        client, auth_headers, monkeypatch, "<p>Hello</p>", kalisoftai_conn["id"]
    )
    assert kalisoftai_campaign["status"] == "completed"
    assert FakeMailSender.credentials[0] == {
        "user": "kalisoftai@example.test",
        "password": "kalisoftai-pass-test",
    }


def test_gmail_credentials_fall_back_to_legacy_password(monkeypatch):
    monkeypatch.setattr(settings, "GMAIL_ADDRESS", "legacy@example.test")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD", "legacy-pass-test")
    monkeypatch.setattr(settings, "GMAIL_ADDRESS_KALISOFTAI", "kalisoftai@example.test")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD_KALISOFTAI", "")
    monkeypatch.setattr(settings, "GMAIL_ADDRESS_KALIKA", "kalika@example.test")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD_KALIKA", "")
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")

    assert settings.gmail_credentials("kalika") == ("kalika@example.test", "legacy-pass-test")
    assert settings.gmail_credentials("kalisoftai") == (
        "kalisoftai@example.test",
        "legacy-pass-test",
    )


def test_campaign_uses_env_password_for_stale_stored_connection(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "GMAIL_ADDRESS", "")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD", "")
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")
    monkeypatch.setattr(settings, "GMAIL_ADDRESS_KALISOFTAI", "kalisoftai@example.test")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD_KALISOFTAI", "kalisoftai-pass-test")
    monkeypatch.setattr(settings, "GMAIL_ADDRESS_KALIKA", "kalika@example.test")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD_KALIKA", "kalika-pass-test")

    headers = _headers(client, "kalika@kalika.local")
    stale = client.post(
        "/api/email/connections",
        json={
            "email_address": "kalika@example.test",
            "password": "stale-pass-test",
            "smtp_host": "smtp.gmail.com",
        },
        headers=headers,
    )
    assert stale.status_code == 201, stale.text
    campaign = _setup_campaign(
        client, headers, monkeypatch, "<p>Hello</p>", stale.json()["id"]
    )
    assert campaign["status"] == "completed"
    assert FakeMailSender.credentials[0] == {
        "user": "kalika@example.test",
        "password": "kalika-pass-test",
    }


def test_campaign_uses_org_env_address_over_different_stored_connection(
    client, auth_headers, monkeypatch
):
    monkeypatch.setattr(settings, "GMAIL_ADDRESS", "")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD", "")
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")
    monkeypatch.setattr(settings, "GMAIL_ADDRESS_KALISOFTAI", "kalisoftai@example.test")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD_KALISOFTAI", "kalisoftai-pass-test")
    monkeypatch.setattr(settings, "GMAIL_ADDRESS_KALIKA", "sales.kalika@example.test")
    monkeypatch.setattr(settings, "GMAIL_APP_PASSWORD_KALIKA", "kalika-pass-test")

    headers = _headers(client, "kalika@kalika.local")
    stale = client.post(
        "/api/email/connections",
        json={
            "email_address": "old-kalika@example.test",
            "password": "stale-pass-test",
            "smtp_host": "smtp.gmail.com",
        },
        headers=headers,
    )
    assert stale.status_code == 201, stale.text
    campaign = _setup_campaign(
        client, headers, monkeypatch, "<p>Hello</p>", stale.json()["id"]
    )
    assert campaign["status"] == "completed"
    assert FakeMailSender.credentials[0] == {
        "user": "sales.kalika@example.test",
        "password": "kalika-pass-test",
    }
    connections = client.get("/api/email/connections", headers=headers).json()
    assert any(row["email_address"] == "sales.kalika@example.test" for row in connections)
