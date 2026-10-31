def test_dev_login_and_me(client):
    resp = client.post("/api/auth/google", json={"id_token": "dev:owner@kalisoftai.com"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["expires_in"] > 0

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "owner@kalisoftai.com"
    assert me.json()["domain"] == "kalisoftai.com"


def test_dev_login_requires_email(client):
    resp = client.post("/api/auth/google", json={"id_token": "dev:"})
    assert resp.status_code == 400


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_rejects_bad_token(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


def test_dev_login_restricted_to_allowlist(client, monkeypatch):
    from sales_fastapi.config import settings

    monkeypatch.setattr(settings, "AUTH_DEV_ALLOWED_EMAILS", "ai.solutions@kalisoftai.in")

    allowed = client.post("/api/auth/google", json={"id_token": "dev:ai.solutions@kalisoftai.in"})
    assert allowed.status_code == 200, allowed.text

    blocked = client.post("/api/auth/google", json={"id_token": "dev:someone@else.com"})
    assert blocked.status_code == 403


# ---------------------------------------------------------------------------
# Real Google ID-token flow (Google verification library is mocked)
# ---------------------------------------------------------------------------
def _mock_google(monkeypatch, claims=None, error=None):
    """Mock google.oauth2.id_token.verify_oauth2_token for the real-token path."""
    from sales_fastapi import security
    from sales_fastapi.config import settings

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client.apps.googleusercontent.com")

    def fake_verify(token, request, audience):
        if error is not None:
            raise error
        return claims

    monkeypatch.setattr(security.google_id_token, "verify_oauth2_token", fake_verify)


def _claims(email, **overrides):
    base = {
        "sub": f"google-sub-{email}",
        "email": email,
        "email_verified": True,
        "name": email.split("@")[0].title(),
        "picture": "",
    }
    base.update(overrides)
    return base


def _user_count(email):
    from sales_fastapi.database import SessionLocal
    from sales_fastapi.models import User

    db = SessionLocal()
    try:
        return db.query(User).filter(User.email == email).count()
    finally:
        db.close()


def test_google_allowlist_allows_ai_solutions(client, monkeypatch):
    _mock_google(monkeypatch, _claims("ai.solutions@kalisoftai.in"))
    resp = client.post("/api/auth/google", json={"id_token": "real-token"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "ai.solutions@kalisoftai.in"
    # ai.solutions@kalisoftai.in is in ADMIN_EMAILS (test env) -> admin APIs work
    users = client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert users.status_code == 200


def test_google_allowlist_allows_kalika_gmail_without_auto_admin(client, monkeypatch):
    _mock_google(monkeypatch, _claims("kalikaenterprises@gmail.com"))
    resp = client.post("/api/auth/google", json={"id_token": "real-token"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["role"] == "sales"
    # Not in ADMIN_EMAILS and role != admin -> admin-only API must reject
    users = client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert users.status_code == 403


def test_google_blocks_random_gmail(client, monkeypatch):
    _mock_google(monkeypatch, _claims("random.person@gmail.com"))
    resp = client.post("/api/auth/google", json={"id_token": "real-token"})
    assert resp.status_code == 403
    assert "not authorized" in resp.json()["detail"]
    # No account may be created for an unauthorized email
    assert _user_count("random.person@gmail.com") == 0


def test_google_allowlist_takes_precedence_over_domain(client, monkeypatch):
    # Same workspace domain but NOT in the allowlist -> still blocked.
    _mock_google(monkeypatch, _claims("someone@kalisoftai.in"))
    resp = client.post("/api/auth/google", json={"id_token": "real-token"})
    assert resp.status_code == 403
    assert _user_count("someone@kalisoftai.in") == 0


def test_google_rejects_invalid_token(client, monkeypatch):
    _mock_google(monkeypatch, error=ValueError("wrong signature"))
    resp = client.post("/api/auth/google", json={"id_token": "bad-token"})
    assert resp.status_code == 401


def test_google_rejects_expired_token(client, monkeypatch):
    _mock_google(monkeypatch, error=ValueError("Token expired"))
    resp = client.post("/api/auth/google", json={"id_token": "expired-token"})
    assert resp.status_code == 401


def test_google_rejects_unverified_email(client, monkeypatch):
    _mock_google(monkeypatch, _claims("ai.solutions@kalisoftai.in", email_verified=False))
    resp = client.post("/api/auth/google", json={"id_token": "real-token"})
    assert resp.status_code == 403


def test_google_missing_client_config(client, monkeypatch):
    from sales_fastapi.config import settings

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    resp = client.post("/api/auth/google", json={"id_token": "real-token"})
    assert resp.status_code == 503


def test_google_no_duplicate_account_for_existing_user(client, monkeypatch):
    claims = _claims("kalikaenterprises@gmail.com")
    _mock_google(monkeypatch, claims)
    first = client.post("/api/auth/google", json={"id_token": "real-token"})
    assert first.status_code == 200
    second = client.post("/api/auth/google", json={"id_token": "real-token"})
    assert second.status_code == 200
    assert _user_count("kalikaenterprises@gmail.com") == 1
    me1 = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {first.json()['access_token']}"},
    )
    me2 = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {second.json()['access_token']}"},
    )
    assert me1.json()["id"] == me2.json()["id"]


def test_google_normalizes_email_case_and_spaces(client, monkeypatch):
    _mock_google(monkeypatch, _claims("  KalikaEnterprises@Gmail.com "))
    resp = client.post("/api/auth/google", json={"id_token": "real-token"})
    assert resp.status_code == 200, resp.text
    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {resp.json()['access_token']}"},
    )
    assert me.json()["email"] == "kalikaenterprises@gmail.com"


def test_password_login_unaffected_by_google_allowlist(client, auth_headers):
    created = client.post(
        "/api/users",
        headers=auth_headers,
        json={
            "email": "pwtest@kalisoftai.com",
            "name": "Pw Test",
            "password": "secret123",
            "role": "sales",
        },
    )
    assert created.status_code == 201, created.text
    resp = client.post(
        "/api/auth/password",
        json={"username": "pwtest@kalisoftai.com", "password": "secret123"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"]
