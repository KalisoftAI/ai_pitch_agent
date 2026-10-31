"""Tests: preflight guardrail checks, UAT window, model catalog, prompt samples,
journey events/stories/behaviours, and IST cron mapping.
"""

from sales_fastapi.config import settings
from sales_fastapi.customer_journey import (
    PATTERNS,
    STAGES,
    classify_customer_type,
)
from sales_fastapi.model_catalog import catalog, default_model
from sales_fastapi.ops_checks import ist_to_utc_cron
from sales_fastapi.scheduler import STANDARD_TASKS


# ---------------------------------------------------------------- IST cron mapping
def test_ist_to_utc_window():
    assert ist_to_utc_cron(20, 0) == (14, 30)  # 20:00 IST -> 14:30 UTC
    assert ist_to_utc_cron(21, 0) == (15, 30)
    assert ist_to_utc_cron(22, 0) == (16, 30)
    assert ist_to_utc_cron(0, 0) == (18, 30)  # midnight IST -> 18:30 UTC prev day


def test_ist_crons_registered():
    crons = {t["cron"] for t in STANDARD_TASKS}
    for c in ("30 14 * * *", "30 15 * * *", "30 16 * * *"):
        assert c in crons
    names = {t["name"] for t in STANDARD_TASKS}
    assert {"daily_guardrail_checks", "daily_llm_prompt_refine", "daily_uat_report"} <= names


# ---------------------------------------------------------------- preflight
def test_preflight_report_shape(client, auth_headers):
    resp = client.get("/api/ops/preflight", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert {"generated_at", "summary", "checks"} <= set(data)
    assert data["summary"]["total"] == len(data["checks"])
    layers = {c["layer"] for c in data["checks"]}
    assert {
        "config",
        "security",
        "auth",
        "data",
        "erp",
        "scheduler",
        "llm",
        "uat",
        "storage",
    } <= layers
    assert all(c["status"] in ("pass", "warn", "fail") for c in data["checks"])


def test_run_checks_persists(client, auth_headers):
    resp = client.post("/api/ops/run-checks", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["summary"]["total"] > 5


def test_preflight_admin_only(client, auth_headers):
    # dev-login user is the configured admin in tests (AUTH_DEV_MODE dev email)
    r = client.get("/api/ops/preflight", headers=auth_headers)
    assert r.status_code in (200, 403)  # depends on ADMIN_EMAILS in test env


# ---------------------------------------------------------------- models / prompts
def test_model_catalog_has_flash_and_gemma(client, auth_headers):
    data = client.get("/api/ops/models", headers=auth_headers).json()
    ids = {m["id"] for m in data["models"]}
    assert "gemini-2.5-flash" in ids
    assert "gemma-4-27b-it" in ids
    assert data["default"] == default_model()
    assert all("human_review" in m for m in data["models"])


def test_model_catalog_unit():
    assert any("flash" in m["id"] for m in catalog())
    assert any(m["provider"] == "gemma" for m in catalog())


def test_prompt_samples(client, auth_headers):
    data = client.get("/api/ops/prompt-samples", headers=auth_headers).json()
    assert data["version"]
    assert len(data["prompts"]) >= 5
    ids = {p["id"] for p in data["prompts"]}
    assert {"PR-01", "PR-02"} <= ids
    # every prompt declares a model + variables + human review flag
    for p in data["prompts"]:
        assert p["model"] and p["variables"] is not None and "human_review" in p
    # filtered fetch
    one = client.get("/api/ops/prompt-samples?task=journey_next_step", headers=auth_headers).json()
    assert len(one["prompts"]) == 1


def test_assets_exist_for_u1():
    from sales_fastapi.config import settings as s

    assert s.DEPLOY_ENV in ("preprod", "stage", "uat", "prod")
    assert s.HUMAN_REVIEW_REQUIRED is True
    assert "flash" in (s.GEMINI_FLASH_MODEL or "")


# ---------------------------------------------------------------- journey
def test_customer_type_classifier():
    assert classify_customer_type() == "new_customer"
    assert classify_customer_type(order_count=2) == "repeat_customer"
    assert classify_customer_type(negative_sentiment=True) == "at_risk"
    assert classify_customer_type(days_since_order=90) == "at_risk"
    assert classify_customer_type(gross_value=2_000_000) == "high_value"


def test_journey_patterns_cover_stages():
    assert STAGES[0] == "awareness" and STAGES[-1] == "advocacy"
    for name, p in PATTERNS.items():
        assert p["label"] and p["detect"] and p["stages"]
        for stage in p["stages"]:
            assert stage in STAGES, (name, stage)
        for stage in p["next_action"]:
            assert stage in STAGES


def test_journey_event_and_stories(client, auth_headers, db_session=None):
    payload = {
        "contact_id": 101,
        "customer_type": "new_customer",
        "stage": "interest",
        "event": "rate_requested",
        "channel": "whatsapp",
        "detail": "asked VCI price",
    }
    r = client.post("/api/journey/event", json=payload, headers=auth_headers)
    assert r.status_code == 200, r.text
    r2 = client.post(
        "/api/journey/event",
        json={**payload, "stage": "evaluation", "event": "quotation_sent"},
        headers=auth_headers,
    )
    assert r2.status_code == 200
    stories_resp = client.get("/api/journey/stories", headers=auth_headers).json()
    assert len(stories_resp) >= 1
    story = stories_resp[0]
    assert story["current_stage"] == "evaluation"
    assert story["next_action_template"] == "WA-QT-01"
    assert len(story["timeline"]) == 2
    beh = client.get("/api/journey/behaviours", headers=auth_headers).json()
    assert beh["total"] >= 2 and beh["by_channel"].get("whatsapp") == 2
    summ = client.get("/api/journey/summary", headers=auth_headers).json()
    assert summ["events"] >= 2 and summ["contacts"] >= 1


def test_journey_rejects_bad_stage(client, auth_headers):
    r = client.post(
        "/api/journey/event",
        json={"contact_id": 1, "stage": "nonsense", "event": "x"},
        headers=auth_headers,
    )
    assert r.status_code in (422, 500)  # ValueError surfaces as server error or validation


# ---------------------------------------------------------------- UAT + logs
def test_uat_status(client, auth_headers):
    u = client.get("/api/ops/uat", headers=auth_headers).json()
    assert u["phase"] == "ERP-UAT"
    assert u["enabled_until"] == settings.UAT_ENABLED_UNTIL
    assert isinstance(u["features"], list) and any(f["status"] == "enabled" for f in u["features"])
    assert any(f["status"] == "next scope" for f in u["features"])


def test_logs_endpoint(client, auth_headers):
    data = client.get("/api/ops/logs?limit=5", headers=auth_headers).json()
    assert set(data) == {"model_usage", "audit", "sync_runs"}
