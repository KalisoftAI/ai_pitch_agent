"""Pre-deploy / daily guardrail checks for the sales app.

Layers checked (each returns pass / warn / fail + remediation):

1. config        deployment env, secret strength, dev-mode flags
2. security      allowed hosts, CORS, request limits, PII redaction, audit
3. auth          admin emails, Google sign-in / dev login posture
4. data          core tables present and populated (contacts, ERP mirror, journey)
5. erp           latest report synced
6. scheduler     cron registry incl. the 20:00-22:00 IST window jobs
7. llm           provider/model catalog, flash + gemma availability, human review
8. uat           UAT window active for the one-week rollout
9. storage       GCS reachability (or local mirror fallback)

Output is deterministic and safe to show to admins (no secrets).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from .config import settings

# IST is UTC+05:30. Cron entries are UTC, so the 20:00-22:00 IST window maps to
# 14:30-16:30 UTC.
IST_OFFSET_HOURS = 5.5


def ist_to_utc_cron(hour_ist: int, minute_ist: int = 0) -> tuple[int, int]:
    total = hour_ist * 60 + minute_ist - int(IST_OFFSET_HOURS * 60)
    total %= 24 * 60
    return total // 60, total % 60


def _c(level: str, layer: str, id_: str, ok: bool, detail: str, remediation: str = "",
       warn_only: bool = False) -> dict:
    status = "pass" if ok else ("warn" if warn_only else "fail")
    return {"id": id_, "layer": layer, "status": status, "detail": detail, "remediation": remediation}


def run_checks(db: Session) -> dict:
    checks: list[dict] = []
    env = (settings.ENV or "development").lower()

    # ---------------------------------------------------------------- config
    checks.append(_c("config", "config", "deploy_env",
                     settings.DEPLOY_ENV in ("preprod", "stage", "uat", "prod"),
                     f"DEPLOY_ENV={settings.DEPLOY_ENV}", "set DEPLOY_ENV to preprod/stage/uat/prod"))
    secret = settings.SECRET_KEY or ""
    checks.append(_c("config", "config", "secret_key",
                     len(secret) >= 32 and "change" not in secret.lower(),
                     f"SECRET_KEY length={len(secret)}", "use a 32+ char random SECRET_KEY", warn_only=env != "production"))
    checks.append(_c("config", "config", "dev_login",
                     not settings.AUTH_DEV_MODE or env != "production",
                     f"AUTH_DEV_MODE={settings.AUTH_DEV_MODE} ENV={settings.ENV}",
                     "disable AUTH_DEV_MODE in production"))

    # ---------------------------------------------------------------- security
    checks.append(_c("security", "security", "allowed_hosts",
                     bool(settings.ALLOWED_HOSTS) and (env != "production" or "*" not in settings.ALLOWED_HOSTS),
                     f"ALLOWED_HOSTS={settings.ALLOWED_HOSTS}", "restrict hosts in production"))
    checks.append(_c("security", "security", "cors",
                     env != "production" or "*" not in (settings.CORS_ORIGINS or ""),
                     f"CORS_ORIGINS={settings.CORS_ORIGINS}", "list explicit origins in production"))
    checks.append(_c("security", "security", "body_limit",
                     settings.MAX_REQUEST_BYTES <= 50_000_000,
                     f"MAX_REQUEST_BYTES={settings.MAX_REQUEST_BYTES}", "keep under 50 MB"))
    checks.append(_c("security", "security", "pii_redaction",
                     settings.PII_REDACTION_ENABLED, f"PII_REDACTION_ENABLED={settings.PII_REDACTION_ENABLED}",
                     "enable PII redaction"))
    checks.append(_c("security", "security", "audit_log",
                     settings.AUDIT_LOG_ENABLED, f"AUDIT_LOG_ENABLED={settings.AUDIT_LOG_ENABLED}",
                     "enable audit logging"))

    # ---------------------------------------------------------------- auth
    checks.append(_c("auth", "auth", "admin_configured", bool(settings.admin_emails),
                     f"admins={sorted(settings.admin_emails)}", "set ADMIN_EMAILS"))
    checks.append(_c("auth", "auth", "google_signin",
                     bool(settings.GOOGLE_CLIENT_ID) or env != "production",
                     f"GOOGLE_CLIENT_ID set={bool(settings.GOOGLE_CLIENT_ID)}",
                     "configure Google OAuth client for production", warn_only=env != "production"))

    # ---------------------------------------------------------------- data
    try:
        tables = set(inspect(db.get_bind()).get_table_names())
    except Exception:
        tables = set()
    required = {"users", "contacts", "whatsapp_messages", "erp_dispatch", "erp_orders", "journey_events"}
    missing = sorted(required - tables)
    checks.append(_c("data", "data", "tables", not missing,
                     f"missing={missing}" if missing else f"{len(required)} core tables present",
                     "run init_db / migrations"))
    try:
        contacts = int(db.execute(text("SELECT COUNT(*) FROM contacts")).scalar() or 0)
    except Exception:
        contacts = 0
    checks.append(_c("data", "data", "contacts_loaded", contacts > 0, f"contacts={contacts}",
                     "sync GCS contacts", warn_only=True))

    # ---------------------------------------------------------------- erp
    try:
        erp_rows = int(db.execute(text("SELECT COUNT(*) FROM erp_dispatch")).scalar() or 0)
        erp_date = db.execute(text("SELECT MAX(report_date) FROM erp_dispatch")).scalar()
    except Exception:
        erp_rows, erp_date = 0, None
    checks.append(_c("erp", "erp", "dispatch_synced", erp_rows > 0,
                     f"dispatch_rows={erp_rows} report_date={erp_date}",
                     "POST /api/erp/sync (cron 0 6 * * *)"))
    if erp_rows:
        age = None
        try:
            age = (date.today() - date.fromisoformat(str(erp_date))).days
        except Exception:
            pass
        checks.append(_c("erp", "erp", "dispatch_fresh", age is not None and age <= 2,
                         f"report_age_days={age}", "run the daily ERP sync", warn_only=True))

    # ---------------------------------------------------------------- scheduler
    from .scheduler import STANDARD_TASKS
    names = {t["name"] for t in STANDARD_TASKS}
    need = {"erp_dispatch_sync", "daily_guardrail_checks", "daily_llm_prompt_refine", "daily_uat_report"}
    lacking = sorted(need - names)
    checks.append(_c("scheduler", "scheduler", "cron_registry", not lacking,
                     f"tasks={len(names)} missing={lacking}", "register the missing cron jobs"))
    h, m = ist_to_utc_cron(20, 0)
    checks.append(_c("scheduler", "scheduler", "ist_window",
                     f"{m} {h} * * *" in {t["cron"] for t in STANDARD_TASKS},
                     f"20:00 IST == {m:02d} {h:02d} UTC",
                     "schedule the 20:00-22:00 IST window jobs", warn_only=True))

    # ---------------------------------------------------------------- llm
    checks.append(_c("llm", "llm", "llm_enabled", settings.LLM_ENABLED,
                     f"LLM_ENABLED={settings.LLM_ENABLED}", "set LLM_ENABLED=true for AI features", warn_only=True))
    flash = settings.GEMINI_FLASH_MODEL or ""
    checks.append(_c("llm", "llm", "flash_model", flash.startswith("gemini") and "flash" in flash,
                     f"GEMINI_FLASH_MODEL={flash}", "select a Gemini flash model"))
    checks.append(_c("llm", "llm", "gemma_model", bool(settings.LLM_GEMMA_MODEL),
                     f"LLM_GEMMA_MODEL={settings.LLM_GEMMA_MODEL}", "select a Gemma model"))
    checks.append(_c("llm", "llm", "human_review", settings.HUMAN_REVIEW_REQUIRED,
                     f"HUMAN_REVIEW_REQUIRED={settings.HUMAN_REVIEW_REQUIRED}",
                     "keep human review on for customer-facing sends"))

    # ---------------------------------------------------------------- uat
    try:
        until = date.fromisoformat(settings.UAT_ENABLED_UNTIL)
    except Exception:
        until = None
    days_left = (until - date.today()).days if until else None
    checks.append(_c("uat", "uat", "uat_window",
                     settings.UAT_ENABLED and days_left is not None and days_left >= 0,
                     f"UAT_ENABLED={settings.UAT_ENABLED} until={settings.UAT_ENABLED_UNTIL} days_left={days_left}",
                     "extend UAT_ENABLED_UNTIL or disable UAT", warn_only=True))

    # ---------------------------------------------------------------- storage
    try:
        from .services import GCSStorage
        gcs = GCSStorage().available
    except Exception:
        gcs = False
    checks.append(_c("storage", "storage", "gcs", gcs, f"gcs_available={gcs}",
                     "check ADC credentials (gcloud auth application-default login)", warn_only=True))

    fails = [c for c in checks if c["status"] == "fail"]
    warns = [c for c in checks if c["status"] == "warn"]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "env": settings.ENV,
        "deploy_env": settings.DEPLOY_ENV,
        "summary": {"total": len(checks), "pass": len(checks) - len(fails) - len(warns),
                    "warn": len(warns), "fail": len(fails),
                    "ready": len(fails) == 0},
        "checks": checks,
    }
