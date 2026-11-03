from sales_fastapi.instore_mail import build_insights


def test_build_insights_links_senders_and_attachments():
    contacts = [
        {"id": 7, "name": "Ravi", "email": "ravi@acme.com", "phone": "9820011122",
         "domain": "acme.com", "company": "Acme Packaging"},
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
    monkeypatch.setattr("sales_fastapi.routers.instore._model_available", lambda provider: provider == "echo")
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
