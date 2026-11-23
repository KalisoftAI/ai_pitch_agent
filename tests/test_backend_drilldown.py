from sales_fastapi.gmail_sync import _normalize_message, message_out
from sales_fastapi.media_inventory import media_inventory
from sales_fastapi.models import GmailMessage, GmailSyncState, GoogleMailbox


def _mailbox(db):
    mailbox = GoogleMailbox(
        user_id=1,
        email_address="kalikaenterprises@gmail.com",
        access_token_encrypted="",
        is_connected=True,
    )
    db.add(mailbox)
    db.commit()
    db.refresh(mailbox)
    return mailbox


def test_normalize_gmail_message_extracts_jsw_client_and_attachment_details():
    mailbox = GoogleMailbox(id=4, user_id=1, email_address="kalikaenterprises@gmail.com")
    full = {
        "id": "msg-1",
        "threadId": "thread-1",
        "snippet": "Please share the Cummins DG price list.",
        "internalDate": "1795249462000",
        "labelIds": ["INBOX"],
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Request for Price List - Cummins DG"},
                {"name": "From", "value": "Dhiraj Zatale <dhiraj.zatale@jsw.in>"},
                {"name": "To", "value": "kalikaenterprises@gmail.com"},
                {"name": "Date", "value": "Sat, 21 Nov 2026 10:00:00 +0530"},
            ],
            "mimeType": "multipart/mixed",
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": "UGxlYXNlIHNoYXJlIHRoZSBwcmljZSBsaXN0Lg=="},
                },
                {
                    "filename": "rate-sheet.pdf",
                    "mimeType": "application/pdf",
                    "body": {"attachmentId": "att-1", "size": 1234},
                },
            ],
        },
    }

    row, attachments = _normalize_message(mailbox, full, gcs_bucket="kalika_enterprises")

    assert row["client"] == "JSW (Dhiraj Zatale)"
    assert row["thread_id"] == "thread-1"
    assert row["body"] == "Please share the price list."
    assert attachments[0]["name"] == "rate-sheet.pdf"
    assert attachments[0]["attachment_id"] == "att-1"


def test_gmail_drilldown_rows_and_sync_state(db_session):
    mailbox = _mailbox(db_session)
    state = GmailSyncState(
        user_id=1, mailbox_id=mailbox.id, history_id="123", message_ids=["m1"], stats={}
    )
    row = GmailMessage(
        user_id=1,
        mailbox_id=mailbox.id,
        message_id="m1",
        thread_id="t1",
        subject="Rate enquiry",
        sender_email="rpatil@instorindia.com",
        intent="quote_request",
        client="Instor India (R. Patil)",
        body="Please send rates",
        attachments=[{"name": "rfq.pdf", "gcs_path": "attachments/rfq.pdf"}],
    )
    db_session.add_all([state, row])
    db_session.commit()

    payload = message_out(row)
    assert payload["subject"] == "Rate enquiry"
    assert payload["attachments"][0]["name"] == "rfq.pdf"
    assert state.history_id == "123"


def test_media_inventory_returns_stable_signature(db_session):
    first = media_inventory(db_session, kind="image", limit=5)
    second = media_inventory(db_session, kind="image", limit=5)

    assert first["kind"] == "image"
    assert first["signature"] == second["signature"]
    assert first["changed"] is False
    assert isinstance(first["items"], list)


def test_business_kpi_endpoints(client, auth_headers):
    overview = client.get("/api/business-kpi/executive", headers=auth_headers)
    assert overview.status_code == 200, overview.text
    assert "metrics" in overview.json()
    assert "drilldowns" in overview.json()

    companies = client.get("/api/business-kpi/executive/companies", headers=auth_headers)
    assert companies.status_code == 200, companies.text
    assert companies.json()["metric"] == "companies"

    unknown = client.get("/api/business-kpi/executive/unknown", headers=auth_headers)
    assert unknown.status_code == 404


def test_gmail_message_list_requires_existing_mailbox(client, auth_headers):
    response = client.get("/api/email/google/mailboxes/999/messages", headers=auth_headers)
    assert response.status_code == 404


def test_public_config_exposes_ui_assets_prompt_tag(client):
    body = client.get("/api/config").json()

    assert body["ui_assets_enabled"] is True
    assert body["ui_assets_prompt_tag"] == "ui-assets-from-gcs-v2"


def test_ui_assets_endpoint_respects_disabled_flag(client, auth_headers, monkeypatch):
    import sales_fastapi.routers.media as media_router

    monkeypatch.setattr(media_router.settings, "UI_ASSETS_ENABLED", False)
    response = client.get("/api/media/ui-assets", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["enabled"] is False
    assert body["prompt_tag"] == "ui-assets-from-gcs-v2"
    assert body["source"] == "gs://sales-crm/assets/UI/"
    assert body["kit"]["palette"]["brand"]["navy"] == "#1F3A8A"
    assert "daily_rate_video_template_v2.html" in body["kit"]["templates"]
