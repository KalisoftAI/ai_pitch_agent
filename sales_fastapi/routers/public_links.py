from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse, Response

from ..config import settings
from ..services import GCSStorage

router = APIRouter(prefix="/public", tags=["public-links"])
logger = logging.getLogger(__name__)

BUCKET = "kalika_enterprises"
MAX_INLINE_BYTES = 20 * 1024 * 1024
DOCUMENTS = {
    "catalog": ("ERP-V1/New_kalika_enterprises_catalog.pdf", "kalika-catalogue.pdf"),
    "profile": ("kalika backup/KALIKA.pdf", "kalika-profile.pdf"),
}


@router.get("/catalog/{kind}")
def public_catalog(kind: str):
    key = (kind or "").strip().lower()
    if key not in DOCUMENTS:
        raise HTTPException(status_code=404, detail="Unknown document")
    path, filename = DOCUMENTS[key]
    buckets = [settings.GCS_BUCKET_CONTACTS, BUCKET]
    data = None
    for bucket in [value for value in buckets if value]:
        storage = GCSStorage(bucket_name=bucket)
        if not storage.available or storage._client is None:
            continue
        try:
            blob = storage._client.bucket(bucket).blob(path)
            blob.reload()
            size = int(blob.size or 0)
            if size > MAX_INLINE_BYTES:
                signed_url = None
                try:
                    sign_args = {
                        "expiration": datetime.now(timezone.utc) + timedelta(hours=1),
                        "method": "GET",
                        "version": "v4",
                    }
                    sa_email = settings.GCS_SIGNING_SERVICE_ACCOUNT
                    if not sa_email and settings.GOOGLE_CLOUD_PROJECT:
                        sa_email = (
                            f"kalisoft-sales-run@{settings.GOOGLE_CLOUD_PROJECT}."
                            "iam.gserviceaccount.com"
                        )
                    try:
                        import google.auth
                        from google.auth.transport import requests as google_requests

                        creds, _ = google.auth.default(
                            scopes=["https://www.googleapis.com/auth/cloud-platform"]
                        )
                        request = google_requests.Request()
                        if not getattr(creds, "valid", False) or getattr(creds, "token", None) is None:
                            if hasattr(creds, "refresh"):
                                creds.refresh(request)
                        if not sa_email:
                            sa_email = getattr(creds, "service_account_email", None)
                        token = getattr(creds, "token", None)
                        if sa_email and token:
                            sign_args["service_account_email"] = sa_email
                            sign_args["access_token"] = token
                        elif sa_email:
                            sign_args["service_account_email"] = sa_email
                    except Exception:
                        if sa_email:
                            sign_args["service_account_email"] = sa_email
                    signed_url = blob.generate_signed_url(**sign_args)
                except Exception:  # noqa: BLE001 - fall back to inline proxy
                    logger.exception("Signed URL generation failed for %s/%s", bucket, path)
                if signed_url:
                    return RedirectResponse(signed_url, status_code=307)
            data = blob.download_as_bytes()
            break
        except Exception:  # noqa: BLE001 - try the next configured bucket
            logger.exception("Public catalogue fetch failed for %s/%s", bucket, path)
            continue
    if data is None:
        raise HTTPException(status_code=503, detail="Document temporarily unavailable")
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "public, max-age=3600",
        },
    )


@router.get("/catalog")
def public_catalog_index():
    return {
        "items": [
            {"key": key, "url": f"/api/public/catalog/{key}", "filename": filename}
            for key, (_, filename) in DOCUMENTS.items()
        ]
    }
