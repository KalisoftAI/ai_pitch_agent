import pytest
from fastapi.testclient import TestClient

from sales_fastapi.config import Settings


def test_security_headers_are_present(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "same-origin"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_oversized_request_is_rejected(client):
    response = client.post(
        "/api/auth/google",
        content=b"x" * (1_048_576 + 1),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413


def test_production_rejects_dev_auth_and_weak_security():
    with pytest.raises(ValueError, match="AUTH_DEV_MODE"):
        Settings(
            ENV="production",
            SECRET_KEY="x" * 64,
            AUTH_DEV_MODE=True,
            GOOGLE_CLIENT_ID="client",
            GOOGLE_ALLOWED_DOMAINS="kalisoftai.com",
            GOOGLE_CLOUD_PROJECT="project",
            CORS_ORIGINS="https://app.example.com",
            ALLOWED_HOSTS="*.a.run.app",
        )

    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(
            ENV="production",
            SECRET_KEY="change-this-secret",
            AUTH_DEV_MODE=False,
            GOOGLE_CLIENT_ID="client",
            GOOGLE_ALLOWED_DOMAINS="kalisoftai.com",
            GOOGLE_CLOUD_PROJECT="project",
            CORS_ORIGINS="https://app.example.com",
            ALLOWED_HOSTS="*.a.run.app",
        )


def test_untrusted_host_is_rejected(client):
    response = client.get("/api/health", headers={"host": "attacker.example"})
    assert response.status_code == 400
