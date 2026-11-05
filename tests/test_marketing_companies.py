"""Tests for the marketing companies router."""

import pathlib
from datetime import date

import pytest

from sales_fastapi.routers.marketing_companies import _parse_customers_csv

WORKBOOK = pathlib.Path(__file__).resolve().parents[1] / "gcs_data" / "sales-contacts__marketing_list_kalika_(1).xlsx"


@pytest.mark.skipif(not WORKBOOK.exists(), reason="marketing workbook not present")
def test_import_and_list(client, auth_headers):
    with WORKBOOK.open("rb") as fh:
        resp = client.post(
            "/api/marketing-companies/import",
            files={"file": (WORKBOOK.name, fh.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=auth_headers,
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["imported"] + body["updated"] > 0
    assert body["skipped"] >= 0
    assert body["source"].startswith("upload:")
    assert "removed duplicates - mail list" in body["sheets"] or any("mail list" in sheet for sheet in body["sheets"])

    listing = client.get("/api/marketing-companies", headers=auth_headers).json()
    assert listing
    assert listing[0]["company"]
    assert any(row["requirements"] for row in listing)

    stats = client.get("/api/marketing-companies/stats", headers=auth_headers).json()
    assert stats["total"] == body["imported"]


@pytest.mark.skipif(not WORKBOOK.exists(), reason="marketing workbook not present")
def test_update_requirements(client, auth_headers):
    with WORKBOOK.open("rb") as fh:
        client.post(
            "/api/marketing-companies/import",
            files={"file": (WORKBOOK.name, fh.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=auth_headers,
        )

    listing = client.get("/api/marketing-companies", headers=auth_headers).json()
    first = listing[0]
    resp = client.patch(
        f"/api/marketing-companies/{first['id']}",
        json={"requirements": "custom requirement"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["requirements"] == "custom requirement"

    updated = client.get("/api/marketing-companies", headers=auth_headers).json()
    match = next(row for row in updated if row["id"] == first["id"])
    assert match["requirements"] == "custom requirement"


def test_customers_csv_maps_contact_and_requirement_columns():
    rows = _parse_customers_csv(
        b"Customer Name,Contact Person,Mobile,Email Address,Product\n"
        b"Acme Films,Ravi Shah,9876543210,ravi@acme.example,Stretch film\n"
    )

    assert rows == [
        {
            "company": "Acme Films",
            "contact_name": "Ravi Shah",
            "phone": "9876543210",
            "email": "ravi@acme.example",
            "category": "",
            "call_status": "",
            "requirements": "Stretch film",
            "source_sheet": "customers.csv",
            "source_row": 2,
        }
    ]


def test_marketing_company_workflow_and_due_followup(client, auth_headers):
    from sales_fastapi.database import SessionLocal
    from sales_fastapi.models import MarketingCompany, User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "tester@kalisoftai.com").one()
        company = MarketingCompany(
            user_id=user.id,
            company="Acme Films",
            company_key="acme-films",
            email="ravi@acme.example",
        )
        db.add(company)
        db.commit()
        company_id = company.id
    finally:
        db.close()

    response = client.patch(
        f"/api/marketing-companies/{company_id}",
        headers=auth_headers,
        json={
            "funnel_stage": "decision",
            "sales_progress": "quote_sent",
            "next_action": "Call about the quote",
            "follow_up_date": date.today().isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["funnel_stage"] == "decision"
    assert response.json()["sales_progress"] == "quote_sent"

    due = client.get("/api/marketing-companies?due_follow_up=true", headers=auth_headers)
    assert [row["id"] for row in due.json()] == [company_id]

    stats = client.get("/api/marketing-companies/stats", headers=auth_headers).json()
    assert stats["by_funnel_stage"]["decision"] == 1
    assert stats["by_sales_progress"]["quote_sent"] == 1
    assert stats["follow_up_due"] == 1
