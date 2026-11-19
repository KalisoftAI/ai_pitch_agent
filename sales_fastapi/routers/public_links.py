from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..services import GCSStorage

router = APIRouter(prefix="/public", tags=["public-links"])

BUCKET = "kalika_enterprises"
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
    storage = GCSStorage(bucket_name=BUCKET)
    if not storage.available or storage._client is None:
        raise HTTPException(status_code=503, detail="Document storage unavailable")
    try:
        blob = storage._client.bucket(BUCKET).blob(path)
        data = blob.download_as_bytes()
    except Exception as exc:  # noqa: BLE001 - storage errors must not leak details
        raise HTTPException(status_code=503, detail="Document temporarily unavailable") from exc
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
