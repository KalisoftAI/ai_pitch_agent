"""Tests for the marketing companies router."""

import pathlib

import pytest

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
