import io
import zipfile
from datetime import datetime, timezone

from sales_fastapi.config import settings
from sales_fastapi.database import SessionLocal
from sales_fastapi.pipeline_templates import CATALOGUE_LINK
from sales_fastapi.models import (
    MarketingCompany,
    OutreachEngagementEvent,
    OutreachSmartTemplate,
    OutreachWhatsAppMessage,
    ProductRate,
    User,
)


def _seed_approved(client, auth_headers):
    assert client.post("/api/outreach-whatsapp/bootstrap", headers=auth_headers).status_code == 200
    rates = client.get("/api/outreach-whatsapp/rates", headers=auth_headers).json()["items"]
    rate_id = next(rate["id"] for rate in rates if rate["status"] == "pending")
    assert client.post(
        f"/api/outreach-whatsapp/rates/{rate_id}/review",
        headers=auth_headers,
        json={"decision": "approved"},
    ).status_code == 200
    templates = client.get("/api/outreach-whatsapp/templates", headers=auth_headers).json()
    template_id = next(row["id"] for row in templates if row["name"] == "Daily rate + catalogue")
    assert client.post(
        f"/api/outreach-whatsapp/templates/{template_id}/approve", headers=auth_headers
    ).status_code == 200
    return rate_id, template_id


def _add_contact():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "tester@kalisoftai.com").one()
        row = MarketingCompany(
            user_id=user.id,
            company="Aakaar Industries",
            company_key="aakaar-industries",
            contact_name="Ravi Shah",
            phone="9169166779",
            requirements="Need stretch film rate",
            marketing_approved=True,
            segment="hot",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def test_bootstrap_campaign_approve_send_and_track(client, auth_headers, monkeypatch):
    rate_id, template_id = _seed_approved(client, auth_headers)
    contact_id = _add_contact()

    created = client.post(
        "/api/outreach-whatsapp/campaigns",
        headers=auth_headers,
        json={
            "name": "Daily rate blast",
            "template_id": template_id,
            "rate_ids": [rate_id],
            "contact_ids": [contact_id],
        },
    )
    assert created.status_code == 201, created.text
    campaign = created.json()
    assert campaign["status"] == "pending_review"
    assert campaign["total"] == 1
    detail = client.get(f"/api/outreach-whatsapp/campaigns/{campaign['id']}", headers=auth_headers)
    assert detail.status_code == 200, detail.text
    assert "Aakaar Industries" in detail.json()["messages"][0]["rendered_body"]

    approved = client.post(
        f"/api/outreach-whatsapp/campaigns/{campaign['id']}/approve", headers=auth_headers
    )
    assert approved.status_code == 200, approved.text

    monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)

    def fake_send(self, to, text):
        return {"id": "provider-1"}

    monkeypatch.setattr(
        "sales_fastapi.routers.outreach_whatsapp.WechatyGateway.send_text", fake_send
    )
    sent = client.post(
        f"/api/outreach-whatsapp/campaigns/{campaign['id']}/send", headers=auth_headers
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["sent"] == 1

    db = SessionLocal()
    try:
        message = db.query(OutreachWhatsAppMessage).filter(
            OutreachWhatsAppMessage.campaign_id == campaign["id"]
        ).one()
        assert message.status == "sent"
        token = message.track_token
    finally:
        db.close()

    tracked = client.get(
        f"/api/outreach-whatsapp/public/track/{token}",
        params={"event": "catalog_download", "target": CATALOGUE_LINK},
        follow_redirects=False,
    )
    assert tracked.status_code == 302
    assert tracked.headers["location"].endswith("/api/public/catalog/catalog")

    db = SessionLocal()
    try:
        events = db.query(OutreachEngagementEvent).all()
        assert len(events) == 1
        assert events[0].event_type == "catalog_download"
    finally:
        db.close()

    dashboard = client.get("/api/outreach-whatsapp/dashboard", headers=auth_headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["totals"]["sent"] == 1
    assert dashboard.json()["totals"]["catalog_downloads"] == 1


def test_imported_contacts_are_not_approved(client, auth_headers):
    chat = (
        "19/11/26, 10:15 am - +91 91691 66779: "
        "Namaste, we need stretch film rate for 50 micron. Please share catalogue.\n"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("WhatsApp Chat with +91 91691 66779.txt", chat.encode("utf-8"))

    response = client.post(
        "/api/outreach-whatsapp/import/sales-data",
        headers=auth_headers,
        files={"files": ("whatsapp.zip", buffer.getvalue(), "application/zip")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["created"] >= 1

    db = SessionLocal()
    try:
        row = db.query(MarketingCompany).filter(MarketingCompany.company.like("%91691%")).first()
        assert row is not None
        assert row.marketing_approved is False
        assert row.source_reference == "whatsapp.zip"
        assert "stretch film" in row.requirements.lower()
    finally:
        db.close()


def test_campaign_rejects_unapproved_contacts(client, auth_headers):
    _, template_id = _seed_approved(client, auth_headers)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "tester@kalisoftai.com").one()
        row = MarketingCompany(
            user_id=user.id,
            company="Unapproved Mills",
            company_key="unapproved-mills",
            phone="9169166779",
            marketing_approved=False,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        contact_id = row.id
    finally:
        db.close()

    response = client.post(
        "/api/outreach-whatsapp/campaigns",
        headers=auth_headers,
        json={
            "name": "Should fail",
            "template_id": template_id,
            "contact_ids": [contact_id],
        },
    )
    assert response.status_code == 409
    assert "approval" in response.json()["detail"].lower()


def test_bootstrap_seeds_templates_and_rates(client, auth_headers):
    _seed_approved(client, auth_headers)
    db = SessionLocal()
    try:
        assert db.query(OutreachSmartTemplate).count() >= 3
        assert db.query(ProductRate).count() >= 2
    finally:
        db.close()
