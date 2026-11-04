"""Tests: ERP analytics handles an empty database without raising KeyError."""

from sales_fastapi.erp_sync import dispatch_stats, orders_stats


def test_empty_stats_shapes(client):
    from sales_fastapi.database import SessionLocal

    db = SessionLocal()
    try:
        dispatch = dispatch_stats(db)
        orders = orders_stats(db)
    finally:
        db.close()

    assert dispatch == {
        "report_date": "",
        "records": 0,
        "scheduled_qty": 0.0,
        "dispatched_qty": 0.0,
        "completion_pct": 0,
        "by_status": {},
        "customers": 0,
    }
    assert orders == {"report_date": "", "records": 0, "total_value": 0.0, "by_status": {}}


def test_analytics_empty_erp(client, auth_headers):
    resp = client.get("/api/erp/analytics", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["report_date"] == ""
    assert data["funnel"] == {
        "orders": 0,
        "orders_value": 0,
        "scheduled_qty": 0,
        "dispatched_qty": 0,
        "completion_pct": 0,
    }
    assert data["top_customers"] == []
    assert data["plants"] == []
    assert data["status_breakdown"] == {}
    assert data["pending_followup"] == 0
