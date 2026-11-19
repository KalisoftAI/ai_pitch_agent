from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse, Response

from ..config import settings
from ..services import GCSStorage

router = APIRouter(prefix="/public", tags=["public-links"])

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
                sign_args = {
                    "expiration": datetime.now(timezone.utc) + timedelta(hours=1),
                    "method": "GET",
                }
                signer = settings.GCS_SIGNING_SERVICE_ACCOUNT
                if not signer and settings.GOOGLE_CLOUD_PROJECT:
                    signer = (
                        f"kalisoft-sales-run@{settings.GOOGLE_CLOUD_PROJECT}."
                        "iam.gserviceaccount.com"
                    )
                if signer:
                    sign_args["service_account_email"] = signer
                signed_url = blob.generate_signed_url(**sign_args)
                return RedirectResponse(signed_url, status_code=307)
            data = blob.download_as_bytes()
            break
        except Exception:  # noqa: BLE001 - try the next configured bucket
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
