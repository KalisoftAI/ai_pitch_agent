from datetime import date

import pytest

from sales_fastapi.database import SessionLocal
from sales_fastapi.models import SalesOpsDailyCounter


class OfflineStorage:
    def __init__(self, bucket_name=None):
        self.bucket_name = bucket_name or "sales-crm"
        self.available = False
        self._client = None

    def list_blobs(self, prefix="", suffixes=None):
        return []

    def upload_bytes(self, blob_name, data, content_type="application/octet-stream"):
        return True


@pytest.fixture(autouse=True)
def no_real_gcs(monkeypatch):
    monkeypatch.setattr(
        "sales_fastapi.routers.sales_ops.GCSStorage", lambda **kwargs: OfflineStorage(**kwargs)
    )
    monkeypatch.setattr(
        "sales_fastapi.routers.studio.GCSStorage", lambda **kwargs: OfflineStorage(**kwargs)
    )


def test_admin_toggles_require_admin_and_cap_is_enforced(client, auth_headers):
    assert client.get("/api/v1/sales-ops/admin/toggles").status_code == 401
    response = client.get("/api/v1/sales-ops/admin/toggles", headers=auth_headers)
    assert response.status_code == 200
    toggles = response.json()["toggles"]
    assert toggles["whatsapp_auto_send_enabled"] is False
    assert toggles["human_review_required"] is True
    assert toggles["whatsapp_daily_hard_cap"] == 49

    rejected = client.patch(
        "/api/v1/sales-ops/admin/toggles",
        headers=auth_headers,
        json={"whatsapp_daily_hard_cap": 500},
    )
    assert rejected.status_code == 422

    updated = client.patch(
        "/api/v1/sales-ops/admin/toggles",
        headers=auth_headers,
        json={"whatsapp_auto_send_enabled": True},
    )
    assert updated.status_code == 200
    assert updated.json()["toggles"]["whatsapp_auto_send_enabled"] is True


def test_barcode_toggle_and_scan_logging(client, auth_headers):
    payload = {
        "barcode": "KLK-SF23-500MM-0842",
        "sku": "STRETCH-FILM-23MIC",
        "net_weight_kg": 25.0,
        "customer_name": "Rajesh Kulkarni",
        "customer_email": "procurement@example.com",
        "customer_whatsapp": "+919822011111",
        "trigger_followup": True,
    }
    response = client.post(
        "/api/v1/sales-ops/erp/mobile-barcode-scan",
        headers=auth_headers,
        json=payload,
    )
    assert response.status_code == 200
    assert response.json()["event"]["followup_queued"] is True
    assert response.json()["id"] > 0

    listed = client.get("/api/v1/sales-ops/erp/barcode-scans", headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1
    assert listed.json()["items"][0]["barcode"] == payload["barcode"]

    client.patch(
        "/api/v1/sales-ops/admin/toggles",
        headers=auth_headers,
        json={"barcode_mobile_scan_enabled": False},
    )
    disabled = client.post(
        "/api/v1/sales-ops/erp/mobile-barcode-scan",
        headers=auth_headers,
        json=payload,
    )
    assert disabled.status_code == 403


def test_prepare_or_send_defaults_to_human_copy(client, auth_headers):
    response = client.post(
        "/api/v1/sales-ops/outreach/prepare-or-send",
        headers=auth_headers,
        json={
            "contact_name": "Rajesh",
            "company_name": "Chakan Auto Components",
            "phone": "+91 98220 11111",
            "catalog_url": "/api/public/catalog/catalog",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "HUMAN_COPY_AND_REVIEW"
    assert "Kalika Enterprises" in body["message_text"]
    assert body["one_click_whatsapp_url"].startswith("https://wa.me/919822011111")
    assert body["remaining_daily_quota"] == 49


def test_dispatch_preview_and_approval(client, auth_headers, monkeypatch):
    monkeypatch.setattr("sales_fastapi.routers.sales_ops.settings.SMTP_HOST", "")
    payload = {
        "contact_name": "Rajesh",
        "company_name": "Chakan Auto Components",
        "phone": "+919822011111",
        "email": "procurement@example.com",
        "channels": ["email", "whatsapp", "youtube", "instagram"],
        "catalog_url": "/api/public/catalog/catalog",
    }
    preview = client.post(
        "/api/v1/sales-ops/outreach/dispatch",
        headers=auth_headers,
        json=payload,
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["status"] == "pending_review"
    assert body["preview"]["email"]["subject"]
    assert body["preview"]["whatsapp"]["one_click_whatsapp_url"]
    assert body["preview"]["youtube_title"]
    assert body["preview"]["instagram_caption"]

    approved = client.post(
        "/api/v1/sales-ops/outreach/dispatch",
        headers=auth_headers,
        json={**payload, "approve": True},
    )
    assert approved.status_code == 200
    result = approved.json()
    assert result["status"] == "dispatched"
    assert result["channels"]["email"]["status"] == "skipped"
    assert result["channels"]["whatsapp"]["status"] == "human_copy"
    assert result["channels"]["youtube"] == "queued_preview_only"


def test_youtube_discovery_quota_guard(client, auth_headers):
    keywords = ["stretch film", "vci bags", "barcode dispatch"]
    response = client.post(
        "/api/v1/sales-ops/youtube/discover",
        headers=auth_headers,
        json={"keywords": keywords, "max_results": 5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source_mode"] == "deterministic_stub"
    assert body["quota_used_today"] == 300
    assert len(body["signals"]) == 3

    with SessionLocal() as db:
        counter = (
            db.query(SalesOpsDailyCounter)
            .filter(SalesOpsDailyCounter.day == str(date.today()))
            .first()
        )
        counter.yt_quota_used = 4000
        db.commit()

    blocked = client.post(
        "/api/v1/sales-ops/youtube/discover",
        headers=auth_headers,
        json={"keywords": ["stretch film"]},
    )
    assert blocked.status_code == 429

    trends = client.get("/api/v1/sales-ops/youtube/trends", headers=auth_headers)
    assert trends.status_code == 200
    assert len(trends.json()["items"]) == 3


def test_studio_refine_fallback_and_templates(client, auth_headers, monkeypatch):
    def fail_post(*args, **kwargs):
        raise RuntimeError("local ollama unavailable")

    monkeypatch.setattr("sales_fastapi.routers.studio.httpx.post", fail_post)
    response = client.post(
        "/api/v1/studio/refine-and-generate",
        headers=auth_headers,
        json={
            "prompt_text": "Create a factory video for stretch film and barcode dispatch",
            "model_choice": "local_gemma_4b",
            "aspect_ratio": "9:16",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source_mode"] == "deterministic_fallback"
    assert body["cost_usd"] == 0.0
    assert "118 Quotations" in body["refined_prompt"]

    templates = client.get("/api/v1/studio/templates", headers=auth_headers)
    assert templates.status_code == 200
    assert templates.json()["items"]

    refinements = client.get("/api/v1/studio/refinements", headers=auth_headers)
    assert refinements.status_code == 200
    assert len(refinements.json()["items"]) == 1


def test_studio_upload_validates_extension_and_sanitizes_name(client, auth_headers, monkeypatch):
    class FakeStorage:
        def __init__(self, bucket_name=None):
            self.bucket_name = bucket_name or "sales-crm"
            self.available = True
            self.uploaded = []

        def upload_bytes(self, blob_name, data, content_type="application/octet-stream"):
            self.uploaded.append((blob_name, data, content_type))
            return True

    storage = FakeStorage()
    monkeypatch.setattr("sales_fastapi.routers.studio.GCSStorage", lambda **kwargs: storage)

    rejected = client.post(
        "/api/v1/studio/upload",
        headers=auth_headers,
        files={"file": ("payload.exe", b"bad", "application/octet-stream")},
    )
    assert rejected.status_code == 400

    accepted = client.post(
        "/api/v1/studio/upload",
        headers=auth_headers,
        files={"file": ("factory notes.txt", b"hello", "text/plain")},
    )
    assert accepted.status_code == 200
    blob_name = accepted.json()["path"]
    assert blob_name.startswith("assets/uploads/")
    assert blob_name.endswith("_factory_notes.txt")
    assert storage.uploaded
