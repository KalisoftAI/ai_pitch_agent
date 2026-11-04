"""GCP environment verification.

Produces a status-only report (never secret values) so ``/api/governance/gcp``
and CI can confirm the runtime is bound to the expected project, database, and
storage. ``deep`` performs real client initialisation; keep it shallow on
health-check hot paths.
"""

from __future__ import annotations

from typing import Any

from ..config import settings


def _check_project() -> dict[str, Any]:
    configured = bool(settings.GOOGLE_CLOUD_PROJECT.strip())
    return {
        "ok": configured,
        "detail": "GOOGLE_CLOUD_PROJECT is set" if configured else "GOOGLE_CLOUD_PROJECT is empty",
        "value": settings.GOOGLE_CLOUD_PROJECT or None,
    }


def _check_adc() -> dict[str, Any]:
    try:
        import google.auth  # type: ignore
        from google.auth.exceptions import DefaultCredentialsError  # type: ignore

        try:
            credentials, project = google.auth.default()
            return {
                "ok": True,
                "detail": "Application Default Credentials resolved",
                "project": project or None,
                "principal": type(credentials).__name__,
            }
        except DefaultCredentialsError:
            return {"ok": False, "detail": "No Application Default Credentials found"}
    except ImportError:  # pragma: no cover - google-auth is a hard dep in prod
        return {"ok": False, "detail": "google-auth is not installed"}


def _check_database() -> dict[str, Any]:
    if settings.DATABASE_URL:
        scheme = settings.DATABASE_URL.split(":", 1)[0]
        return {"ok": True, "detail": "DATABASE_URL configured", "scheme": scheme}
    if settings.CLOUD_SQL_CONNECTION_NAME:
        return {
            "ok": True,
            "detail": "Cloud SQL unix socket configured",
            "instance": settings.CLOUD_SQL_CONNECTION_NAME,
        }
    if settings.POSTGRES_HOST:
        return {"ok": True, "detail": "Postgres TCP configured", "host": settings.POSTGRES_HOST}
    return {"ok": True, "detail": "Local SQLite fallback (not for production)", "scheme": "sqlite"}


def _check_gcs(*, deep: bool) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": bool(settings.GCS_BUCKET_CONTACTS),
        "detail": "bucket configured",
        "bucket": settings.GCS_BUCKET_CONTACTS or None,
        "deep": deep,
    }
    if not deep:
        return result
    try:
        from google.cloud import storage  # type: ignore

        client = storage.Client(project=settings.GOOGLE_CLOUD_PROJECT or None)
        bucket = client.bucket(settings.GCS_BUCKET_CONTACTS)
        result["ok"] = bool(bucket.exists())
        result["detail"] = "bucket reachable" if result["ok"] else "bucket not found / no access"
    except Exception as exc:  # pragma: no cover - network / credentials
        result["ok"] = False
        result["detail"] = f"GCS check failed: {type(exc).__name__}"
    return result


def _check_secret_manager(*, deep: bool) -> dict[str, Any]:
    names = [
        name
        for name in (
            "SALES_SECRET_KEY",
            "SALES_DATABASE_URL",
            "GOOGLE_CLIENT_ID",
            "GOOGLE_CLIENT_SECRET",
            "GEMINI_API_KEY",
        )
    ]
    result: dict[str, Any] = {
        "ok": True,
        "detail": "secret references expected at deploy time",
        "expected": names,
        "deep": deep,
    }
    if not deep:
        return result
    try:
        from google.cloud import secretmanager  # type: ignore

        client = secretmanager.SecretManagerServiceClient()
        project = settings.GOOGLE_CLOUD_PROJECT
        reachable = []
        for name in names:
            path = f"projects/{project}/secrets/{name}"
            try:
                client.get_secret(request={"name": path})
                reachable.append(name)
            except Exception:
                continue
        result["reachable"] = reachable
        result["ok"] = len(reachable) > 0
        result["detail"] = f"{len(reachable)}/{len(names)} secrets reachable"
    except Exception as exc:  # pragma: no cover - network / credentials
        result["ok"] = False
        result["detail"] = f"Secret Manager check failed: {type(exc).__name__}"
    return result


def verify_environment(*, deep: bool = False) -> dict[str, Any]:
    checks = {
        "project": _check_project(),
        "adc": _check_adc(),
        "database": _check_database(),
        "gcs": _check_gcs(deep=deep),
        "secret_manager": _check_secret_manager(deep=deep),
    }
    return {
        "env": settings.ENV,
        "deep": deep,
        "ok": all(check.get("ok") for check in checks.values()),
        "checks": checks,
    }
