"""Tally Sales Register parsing, sync and dashboard/API integration."""

from __future__ import annotations

import pandas as pd

from sales_fastapi.config import settings
from sales_fastapi.models import TallySale
from sales_fastapi.tally_sync import (
    list_tally_sales,
    parse_tally_workbook,
    sync_tally_sales,
    tally_stats,
)

HEADER = [
    "Date",
    "Particulars",
    "Buyer",
    "Buyer Address",
    "Consignee",
    "Voucher Type",
    "Voucher No.",
    "GSTIN/UIN",
    "Quantity",
    "Rate",
    "Value",
    "Gross Total",
    "SALES GST",
]


def _workbook(path):
    rows = [
        ["Tally Sales Register"],
        [],
        HEADER,
        [
            "2026-04-01",
            "ACME",
            "ACME",
            "Pune",
            "ACME",
            "SALES GST",
            "INV-1",
            "27AAAAA0000A1Z5",
            0,
            0,
            1000,
            1180,
            1000,
        ],
        [None, "VCI Bags", None, None, None, None, None, None, 100, 10, 1000, None, None],
        [
            "2026-04-02",
            "(cancelled )",
            "ACME",
            "Pune",
            "ACME",
            "SALES GST",
            "INV-2",
            "27AAAAA0000A1Z5",
            0,
            0,
            500,
            590,
            500,
        ],
        [None, "Cancelled item", None, None, None, None, None, None, 50, 10, 500, None, None],
        [
            "2026-04-03",
            "Beta",
            "Beta",
            "Mumbai",
            "Beta",
            "SALES GST",
            "INV-3",
            "27BBBBB0000B1Z5",
            2,
            100,
            200,
            236,
            200,
        ],
    ]
    pd.DataFrame(rows).to_excel(path, index=False, header=False)


def test_parse_tally_workbook_handles_header_and_continuation(tmp_path):
    path = tmp_path / "SALE_R_APRIL-26.xlsx"
    _workbook(path)
    rows = parse_tally_workbook(path, path.name)
    assert len(rows) == 2
    assert rows[0]["buyer"] == "ACME"
    assert rows[0]["item_name"] == "VCI Bags"
    assert rows[0]["quantity"] == 100
    assert rows[0]["value"] == 1000
    assert rows[0]["invoice_total"] == 1180
    assert rows[0]["tax"] == 180
    assert rows[1]["item_name"] == "Beta"
    assert rows[1]["value"] == 200
    assert rows[1]["tax"] == 36


def test_sync_tally_sales_upserts_and_skips_cancelled(client, monkeypatch, tmp_path):
    from sales_fastapi.database import SessionLocal

    cache = tmp_path / "cache"
    uploads = tmp_path / "uploads"
    cache.mkdir()
    monkeypatch.setattr(settings, "TALLY_CACHE_PATH", str(cache))
    monkeypatch.setattr(settings, "TALLY_UPLOAD_DIR", str(uploads))
    _workbook(cache / "kalika_sales2026__SALE_R_APRIL-26.xlsx")

    db = SessionLocal()
    try:
        first = sync_tally_sales(db)
        assert first["ok"] is True
        assert first["created"] == 2
        assert first["periods"] == ["2026-04"]
        stats = tally_stats(db)
        assert stats["data_available"] is True
        assert stats["period"] == "2026-04"
        assert stats["records"] == 2
        assert stats["invoices"] == 2
        assert stats["customers"] == 2
        assert stats["total_value"] == 1200
        assert stats["total_quantity"] == 102
        assert stats["top_buyers"][0]["buyer"] in {"ACME", "Beta"}
        sales = list_tally_sales(db)
        assert len(sales) == 2
        assert {row["voucher_no"] for row in sales} == {"INV-1", "INV-3"}

        second = sync_tally_sales(db)
        assert second["created"] == 0
        assert second["updated"] == 2
        assert db.query(TallySale).count() == 2
    finally:
        db.close()


def test_tally_status_and_dashboard_empty(client, auth_headers):
    status = client.get("/api/tally/status", headers=auth_headers)
    assert status.status_code == 200, status.text
    body = status.json()
    assert body["data_available"] is False
    assert body["is_admin"] is True
    assert body["bucket"] == "kalika_enterprises"
    assert body["prefix"] == "kalika_sales2026/"

    overview = client.get("/api/tally/overview", headers=auth_headers)
    assert overview.status_code == 200, overview.text
    assert overview.json()["records"] == 0
    assert client.get("/api/tally/sales", headers=auth_headers).json() == []

    dashboard = client.get("/api/dashboard/summary", headers=auth_headers)
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["tally"]["data_available"] is False


def test_prompt_review_flow(client, auth_headers):
    submitted = client.post(
        "/api/ops/prompt-reviews",
        headers=auth_headers,
        json={
            "prompt_id": "PR-01",
            "comment": "Add a delivery-date field to the summary.",
            "proposed_change": "Return delivery_date when the customer mentions a deadline.",
        },
    )
    assert submitted.status_code == 201, submitted.text
    review = submitted.json()
    assert review["status"] == "pending"
    assert review["prompt_id"] == "PR-01"
    assert review["task"] == "customer_feedback_summary"

    pending = client.get("/api/ops/prompt-reviews?status=pending", headers=auth_headers)
    assert pending.status_code == 200, pending.text
    assert pending.json()["pending"] == 1
    assert pending.json()["items"][0]["comment"].startswith("Add a delivery")

    decided = client.post(
        f"/api/ops/prompt-reviews/{review['id']}/review",
        headers=auth_headers,
        json={"status": "approved", "review_note": "Approved for next weekly run."},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "approved"
    assert decided.json()["reviewed_by"] == "tester@kalisoftai.com"
    assert decided.json()["review_note"].startswith("Approved")

    approved = client.get("/api/ops/prompt-reviews?status=approved", headers=auth_headers)
    assert approved.json()["pending"] == 0
    assert len(approved.json()["items"]) == 1

    unknown = client.post(
        "/api/ops/prompt-reviews",
        headers=auth_headers,
        json={"prompt_id": "PR-99", "comment": "No such prompt."},
    )
    assert unknown.status_code == 404
