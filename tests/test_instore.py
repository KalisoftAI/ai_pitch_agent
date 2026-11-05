from sales_fastapi.config import Settings
from sales_fastapi.instore_mail import build_insights
from sales_fastapi.routers.instore import _filter_mails, _snapshot_context


def test_gmail_credentials_fill_smtp_and_imap_defaults():
    config = Settings(
        _env_file=None,
        SECRET_KEY="test-secret-key-that-is-long-enough-for-hs256",
        GMAIL_ADDRESS="sales@example.com",
        GMAIL_APP_PASSWORD="app-password",
        SMTP_HOST="sales@example.com",
    )

    assert config.SMTP_HOST == "smtp.gmail.com"
    assert config.SMTP_USER == "sales@example.com"
    assert config.SMTP_PASSWORD == "app-password"
    assert config.IMAP_HOST == "imap.gmail.com"
    assert config.IMAP_USER == "sales@example.com"


def test_snapshot_context_uses_selected_intent_only():
    payload = {
        "insights": {"total": 2},
        "mails": [
            {"intent": "quote_request", "subject": "Rate enquiry", "contact_id": 1},
            {"intent": "order", "subject": "Purchase order", "contact_id": 0},
        ],
    }

    context = _snapshot_context(payload, intent="quote_request")

    assert "Total mails: 1; linked contacts: 1; unlinked: 0" in context
    assert "Rate enquiry" in context
    assert "Purchase order" not in context


def test_mail_filters_match_keyword_subject_company_and_date_newest_first():
    mails = [
        {
            "intent": "quote_request",
            "subject": "Rate enquiry for LD film",
            "company": "Acme Packaging",
            "snippet": "Please send the best rate.",
            "date": "Tue, 03 Nov 2026 10:00:00 +0530",
        },
        {
            "intent": "quote_request",
            "subject": "Older rate enquiry",
            "company": "Acme Packaging",
            "snippet": "LD film quotation",
            "date": "2026-11-02T10:00:00+00:00",
        },
        {
            "intent": "order",
            "subject": "Purchase order",
            "company": "Other Company",
            "date": "2026-11-04",
        },
    ]

    result = _filter_mails(
        mails,
        intent="quote_request",
        query="best rate",
        subject="LD film",
        company="Acme",
        since="2026-11-03",
    )

    assert len(result) == 1
    assert result[0]["subject"] == "Rate enquiry for LD film"


def test_build_insights_links_senders_and_attachments():
    contacts = [
        {
            "id": 7,
            "name": "Ravi",
            "email": "ravi@acme.com",
            "phone": "9820011122",
            "domain": "acme.com",
            "company": "Acme Packaging",
        },
    ]
    mails = [
        {
            "uid": "1",
            "from": "Ravi Patil <ravi@acme.com>",
            "subject": "Quotation for 50 micron LD film",
            "date": "Tue, 03 Nov 2026 10:00:00 +0530",
            "snippet": "Please find the attached rate sheet and drawing.",
            "attachments": [{"name": "rate-sheet.xlsx", "size": 1200}],
        },
        {
            "uid": "2",
            "from": "unknown@newbuyer.in",
            "subject": "Purchase order PO-778",
            "date": "2026-11-02",
            "snippet": "Order for 2,000 kg HDPE rolls. Invoice to follow.",
        },
    ]
    payload = build_insights(mails, contacts, source={"kind": "test"})
    insights = payload["insights"]
    assert insights["total"] == 2
    assert insights["linked"] == 1
    assert insights["unlinked"] == 1
    assert insights["attachments"] == 1
    assert insights["attachment_purposes"]["quote_or_rate_sheet"] == 1
    assert payload["missing_links"]["count"] == 1
    assert payload["missing_links"]["samples"][0]["from_email"] == "unknown@newbuyer.in"
    assert payload["graph"]["stats"]["nodes"] > 0
    assert payload["graph"]["stats"]["edges"] > 0
    assert insights["accuracy_pct"] < 100


def _empty_snapshot():
    return {
        "data_available": False,
        "generated_at": "",
        "source": {"kind": "none"},
        "insights": {},
        "missing_links": {"count": 0, "samples": []},
        "mails": [],
        "graph": {"stats": {}},
    }


def test_instore_summary_and_prompts(client, auth_headers, monkeypatch):
    monkeypatch.setattr("sales_fastapi.routers.instore.load_insights", _empty_snapshot)
    summary = client.get("/api/instore/summary", headers=auth_headers)
    assert summary.status_code == 200, summary.text
    assert summary.json()["data_available"] is False

    prompts = client.get("/api/instore/prompts", headers=auth_headers)
    assert prompts.status_code == 200, prompts.text
    body = prompts.json()
    assert body["expertise"]
    assert body["models"]["gemma"]
    assert "INSTORE MAIL SNAPSHOT" in body["prompt_preview"]


def test_instore_ask_falls_back_to_echo(client, auth_headers, monkeypatch):
    monkeypatch.setattr("sales_fastapi.routers.instore.load_insights", _empty_snapshot)
    monkeypatch.setattr(
        "sales_fastapi.routers.instore._model_available", lambda provider: provider == "echo"
    )
    response = client.post(
        "/api/instore/ask",
        headers=auth_headers,
        json={"question": "Which accounts need a follow-up?", "expertise": "field_executive"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["provider"] == "echo"


def test_instore_sync_uses_dump_and_records_run(client, auth_headers, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "sales_fastapi.routers.instore.load_dump_mails",
        lambda: [
            {
                "uid": "dump-1",
                "from": "Buyer <buyer@example.com>",
                "subject": "Rate enquiry",
                "date": "2026-11-01",
                "snippet": "Please share your best rate.",
            }
        ],
    )
    monkeypatch.setattr(
        "sales_fastapi.routers.instore.save_insights",
        lambda payload: {"path": str(tmp_path / "snap.json"), "gcs_uploaded": False},
    )
    response = client.post(
        "/api/instore/sync",
        headers=auth_headers,
        json={"source": "dump", "include_dump": True},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["insights"]["total"] == 1
    assert body["stored"]["gcs_uploaded"] is False


def test_company_visit_extended_field_fields(client, auth_headers):
    created = client.post(
        "/api/visits",
        headers=auth_headers,
        json={
            "company": "Acme Packaging",
            "contact_name": "Ravi",
            "visit_date": "2026-11-03",
            "meet_person": "Ravi Patil",
            "meet_home_location": "Supa MIDC, Ahmednagar",
            "previous_discussion": "Asked for 50 micron LD film quote.",
            "mail_chat_details": "Mail 2026-11-01: rate enquiry; chat: follow up Friday.",
            "map_location": "https://maps.google.com/?q=Supa+MIDC",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["meet_person"] == "Ravi Patil"
    assert body["meet_home_location"] == "Supa MIDC, Ahmednagar"
    assert body["previous_discussion"].startswith("Asked for 50 micron")
    assert body["mail_chat_details"].startswith("Mail 2026-11-01")
    assert body["map_location"].startswith("https://maps.google.com")

    listed = client.get("/api/visits", headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()[0]["meet_home_location"] == "Supa MIDC, Ahmednagar"


def test_dashboard_has_instore_and_field_blocks(client, auth_headers):
    response = client.get("/api/dashboard/summary", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "instore" in body
    assert "field" in body
    assert "missing_links" in body["instore"]
    assert "latest" in body["field"]


def test_whatsapp_dump_mail_gets_working_title_and_outcome():
    payload = build_insights(
        [
            {
                "type": "whatsapp_outbound",
                "id": 27,
                "to": "919260760760",
                "date": "2026-10-30 13:34:36",
                "body_preview": "Namaste Chavan Saheb Mahalaxmi ji, your Kalika Enterprises order LOC-001 (Rs. 0) status: Completed. Reply here for changes. - Ai.Solutions",
            }
        ],
        [],
        source={"kind": "interaction_dump"},
    )
    mail = payload["mails"][0]
    assert mail["working_title"].startswith("Order LOC-001 (Completed)")
    assert "Chavan Saheb Mahalaxmi" in mail["client_name"]
    assert mail["outcome"] == "Completed"
    assert payload["insights"]["by_outcome"]["Completed"] == 1


def test_client_directory_adds_owner_and_context():
    payload = build_insights(
        [
            {
                "uid": "c1",
                "from": "Dhiraj Zatale <dhiraj.zatale@jsw.in>",
                "subject": "Request for Price List_ Cummins DG",
                "date": "2026-10-29",
                "snippet": "Please share the updated Cummins DG price list.",
            }
        ],
        [],
        source={"kind": "test"},
    )
    mail = payload["mails"][0]
    assert mail["client_name"] == "JSW (Dhiraj Zatale)"
    assert mail["owner_email"] == "neoinsights@neosapien.ai"
    assert mail["working_title"] == "Request for Price List_ Cummins DG"
    assert "cummins" in mail["entities"]


def test_visit_samples_sync_is_idempotent(client, auth_headers):
    first = client.post("/api/visits/samples", headers=auth_headers)
    assert first.status_code == 200, first.text
    assert first.json()["created"] == 3
    second = client.post("/api/visits/samples", headers=auth_headers)
    assert second.json()["created"] == 0
    assert second.json()["existing"] == 3

    visits = client.get("/api/visits", headers=auth_headers).json()
    companies = {visit["company"] for visit in visits}
    assert {"Kflex", "Jabil", "Ranjangaon MIDC"} <= companies
    jabil = next(visit for visit in visits if visit["company"] == "Jabil")
    assert jabil["sales_person"] == "Chandrakant G"
    assert jabil["follow_up_date"] == "2026-11-04"
    assert "IndoSpace" in jabil["meet_home_location"]


def test_instore_mails_and_graph_endpoints(client, auth_headers, monkeypatch):
    snapshot = build_insights(
        [
            {
                "uid": "m1",
                "from": "Dhiraj Zatale <dhiraj.zatale@jsw.in>",
                "subject": "Request for Price List_ Cummins DG",
                "date": "2026-10-29",
                "snippet": "Please share the updated Cummins DG price list.",
            },
            {
                "uid": "m2",
                "from": "unknown@buyer.in",
                "subject": "Rate enquiry",
                "date": "2026-10-30",
                "snippet": "Please quote.",
            },
        ],
        [],
        source={"kind": "test"},
    )
    monkeypatch.setattr("sales_fastapi.routers.instore.load_insights", lambda: snapshot)

    mails = client.get("/api/instore/mails?limit=5", headers=auth_headers)
    assert mails.status_code == 200, mails.text
    rows = mails.json()["mails"]
    jsw = next(row for row in rows if row["from_email"] == "dhiraj.zatale@jsw.in")
    assert jsw["client_name"] == "JSW (Dhiraj Zatale)"
    assert jsw["owner_email"] == "neoinsights@neosapien.ai"

    missing = client.get("/api/instore/mails?only_missing=true", headers=auth_headers)
    assert all(row["contact_id"] == 0 for row in missing.json()["mails"])

    graph = client.get("/api/instore/graph", headers=auth_headers)
    assert graph.status_code == 200
    assert graph.json()["stats"]["nodes"] > 0


def test_instore_sync_gmail_without_mailbox_returns_400(client, auth_headers):
    response = client.post("/api/instore/sync", headers=auth_headers, json={"source": "gmail"})
    assert response.status_code == 400


def test_visits_stats_activity_update_delete(client, auth_headers):
    created = client.post(
        "/api/visits",
        headers=auth_headers,
        json={
            "company": "Kflex",
            "visit_date": "2026-11-03",
            "sales_person": "Vishal K",
            "outcome": "Lead generated",
            "follow_up_date": "2026-11-06",
        },
    )
    assert created.status_code == 201, created.text
    visit_id = created.json()["id"]

    stats = client.get("/api/visits/stats", headers=auth_headers)
    assert stats.status_code == 200
    assert stats.json()["visits"] == 1

    activity = client.get("/api/visits/activity", headers=auth_headers)
    assert activity.status_code == 200
    assert activity.json()["visits"] == 1

    updated = client.patch(
        f"/api/visits/{visit_id}",
        headers=auth_headers,
        json={"outcome": "Rate finalized", "status": "closed"},
    )
    assert updated.status_code == 200
    assert updated.json()["outcome"] == "Rate finalized"

    single = client.get(f"/api/visits/{visit_id}", headers=auth_headers)
    assert single.status_code == 200

    deleted = client.delete(f"/api/visits/{visit_id}", headers=auth_headers)
    assert deleted.status_code == 204
    gone = client.get(f"/api/visits/{visit_id}", headers=auth_headers)
    assert gone.status_code == 404


def test_llm_error_is_tagged_logged_and_falls_back(client, auth_headers, monkeypatch, tmp_path):
    import httpx

    from sales_fastapi.llm import providers

    log_file = tmp_path / "llm_errors.log"
    monkeypatch.setattr(providers, "LLM_ERROR_LOG", log_file)

    def boom(**kwargs):
        request = httpx.Request("POST", "https://generativelanguage.googleapis.com/x")
        response = httpx.Response(404, request=request)
        raise httpx.HTTPStatusError("model not found", request=request, response=response)

    class FailingProvider:
        name = "gemma"
        available = True

        def generate(self, **kwargs):
            boom()

    monkeypatch.setattr("sales_fastapi.routers.instore.load_insights", _empty_snapshot)
    monkeypatch.setattr("sales_fastapi.routers.instore._model_available", lambda provider: True)
    from sales_fastapi.llm.providers import EchoProvider

    monkeypatch.setattr(
        "sales_fastapi.routers.instore._provider_for",
        lambda model_id: (
            FailingProvider()
            if "gemma" in model_id
            else (EchoProvider() if model_id == "echo" else None)
        ),
    )
    response = client.post(
        "/api/instore/ask",
        headers=auth_headers,
        json={
            "question": "Next field actions?",
            "expertise": "sales_strategist",
            "model": "gemma-4-27b-it",
        },
    )
    # Chain: failing gemma -> ... -> echo keeps the app running.
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["fallback_used"] is True
    assert body["provider"] == "echo"
    assert "llm:http_404_model" in body["error_tags"]
    assert "llm:http_404_model" in log_file.read_text(encoding="utf-8")
