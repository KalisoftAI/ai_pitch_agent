"""Media uploads for WhatsApp outreach: images + manufacturing videos.

Files are stored in the ``kalika_enterprises`` bucket:
- ``images/`` for product/catalog photos attached to WhatsApp messages
- ``videos/`` for manufacturing/process videos attached to WhatsApp messages

Default Instagram reel links are exposed so the UI can offer them when a
user has not uploaded a video yet.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..governance.audit import log_event
from ..models import User
from ..security import get_current_user
from ..services import GCSStorage

router = APIRouter(prefix="/media", tags=["media"])

GCS_BUCKET = "kalika_enterprises"
IMAGE_TEMPLATE_PREFIX = "sales-metadata/sales-image-templates"
ALLOWED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff")
ALLOWED_VIDEO_EXTENSIONS = (".mp4", ".mov", ".webm", ".mkv", ".avi")

DEFAULT_VIDEOS = [
    {
        "id": "reel-1",
        "name": "Instagram prod reel 1",
        "url": "https://www.instagram.com/reel/DejmP7AMb5j/?utm_source=ig_web_copy_link&vrfl=MzRlODBiNWFlZA==&srtk=MzRlODBiNWFlZA==",
    },
    {
        "id": "reel-2",
        "name": "Instagram prod reel 2",
        "url": "https://www.instagram.com/reel/DcrV7w8SaTy/?utm_source=ig_web_copy_link&dlrf=MzRlODBiNWFlZA==&srtk=MzRlODBiNWFlZA==",
    },
    {
        "id": "reel-3",
        "name": "Instagram prod reel 3",
        "url": "https://www.instagram.com/reel/DehxLXWgLcM/?utm_source=ig_web_copy_link&rpxt=MzRlODBiNWFlZA==&srtk=MzRlODBiNWFlZA==",
    },
]


def _signed_url(path: str, hours: int = 24) -> str:
    """Return a signed download URL when GCS is available; otherwise the public URL."""
    gcs = GCSStorage(bucket_name=GCS_BUCKET)
    if gcs.available and gcs._client is not None:
        try:
            blob = gcs._client.bucket(gcs.bucket_name).blob(path)
            return blob.generate_signed_url(expires=datetime.utcnow() + timedelta(hours=hours), method="GET")
        except Exception:  # noqa: BLE001 - fall back to plain URL
            pass
    return f"https://storage.googleapis.com/{GCS_BUCKET}/{path}"


@router.get("/default-videos")
def default_videos():
    return DEFAULT_VIDEOS


@router.get("/image-templates")
def image_templates(user: User = Depends(get_current_user)):
    """Poster/image templates stored under ``sales-metadata/sales-image-templates``.

    Returns selectable tiles (signed URLs) so campaigns can attach a Diwali or
    product poster to WhatsApp and email without re-uploading each time.
    """
    gcs = GCSStorage(bucket_name=GCS_BUCKET)
    if not gcs.available:
        return {"items": [], "prefix": f"gs://{GCS_BUCKET}/{IMAGE_TEMPLATE_PREFIX}"}
    blobs = gcs.list_blobs(prefix=f"{IMAGE_TEMPLATE_PREFIX}/", suffixes=ALLOWED_IMAGE_EXTENSIONS)
    items = []
    for blob in blobs:
        name = blob["name"]
        base = name.split("/")[-1]
        if not base or base.endswith("/"):
            continue
        items.append(
            {
                "name": base,
                "path": name,
                "url": _signed_url(name),
                "size": blob.get("size"),
                "updated": blob.get("updated"),
            }
        )
    items.sort(key=lambda x: str(x.get("updated") or ""), reverse=True)
    return {"items": items, "prefix": f"gs://{GCS_BUCKET}/{IMAGE_TEMPLATE_PREFIX}"}


@router.post("/upload")
async def upload_media(
    kind: str = Query(default="image"),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kind = (kind or "image").strip().lower()
    if kind not in {"image", "video", "image_template"}:
        raise HTTPException(status_code=400, detail="kind must be image, video or image_template")
    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="File name is required")
    allowed = ALLOWED_VIDEO_EXTENSIONS if kind == "video" else ALLOWED_IMAGE_EXTENSIONS
    if not filename.lower().endswith(allowed):
        raise HTTPException(
            status_code=400,
            detail=f"{kind} must be one of {', '.join(allowed)}",
        )
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    if kind == "image_template":
        prefix = IMAGE_TEMPLATE_PREFIX
    elif kind == "image":
        prefix = "images"
    else:
        prefix = "videos"
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename.replace(" ", "_"))[-120:]
    path = f"{prefix}/{timestamp}_{safe_name}"

    gcs = GCSStorage(bucket_name=GCS_BUCKET)
    if not gcs.available:
        raise HTTPException(status_code=503, detail="GCS is not available")
    ok = gcs.upload_bytes(path, raw, content_type=file.content_type or "application/octet-stream")
    if not ok:
        raise HTTPException(status_code=502, detail="GCS upload failed")

    url = _signed_url(path)
    log_event(
        db,
        action="media.upload",
        actor_user_id=user.id,
        resource_type="media",
        resource_id="",
        tenant_id=user.domain,
        detail={"kind": kind, "gcs_path": path},
        commit=True,
    )
    return {"kind": kind, "gcs_path": path, "url": url, "filename": filename}


@router.get("/list")
def list_media(
    kind: str = Query(default="image"),
    prefix: str = Query(default=""),
    user: User = Depends(get_current_user),
):
    kind = (kind or "image").strip().lower()
    base_prefix = "images" if kind == "image" else "videos"
    gcs_prefix = (prefix or f"{base_prefix}/").strip()
    gcs = GCSStorage(bucket_name=GCS_BUCKET)
    if not gcs.available:
        raise HTTPException(status_code=503, detail="GCS is not available")
    blobs = gcs.list_blobs(prefix=gcs_prefix)
    return [
        {**blob, "url": _signed_url(blob["name"])}
        for blob in blobs
        if not blob["name"].endswith(("/", ""))  # skip folders, keep files
    ]


@router.post("/video-link")
def store_video_link(payload: dict[str, Any], user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Store a video URL (e.g. Instagram reel) reference under videos/ as a .txt pointer."""
    url = str(payload.get("url") or "").strip()
    name = str(payload.get("name") or "video link").strip() or "video link"
    if not url:
        raise HTTPException(status_code=400, detail="Video url is required")
    if not url.startswith(("https://", "http://")):
        raise HTTPException(status_code=400, detail="Video url must start with https://")

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in name.replace(" ", "_"))[:80] or "video"
    path = f"videos/{timestamp}_link_{safe_name}.txt"

    gcs = GCSStorage(bucket_name=GCS_BUCKET)
    if not gcs.available:
        raise HTTPException(status_code=503, detail="GCS is not available")
    ok = gcs.upload_bytes(path, url.encode("utf-8"), content_type="text/plain")
    if not ok:
        raise HTTPException(status_code=502, detail="GCS upload failed")

    log_event(
        db,
        action="media.video_link",
        actor_user_id=user.id,
        resource_type="media",
        resource_id="",
        tenant_id=user.domain,
        detail={"gcs_path": path, "url": url[:120]},
        commit=True,
    )
    return {"gcs_path": path, "url": url, "name": name}
