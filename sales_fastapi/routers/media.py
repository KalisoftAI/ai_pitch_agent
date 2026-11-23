"""Media uploads for WhatsApp outreach: images + manufacturing videos.

Files are stored in the ``kalika_enterprises`` bucket:
- ``images/`` for product/catalog photos attached to WhatsApp messages
- ``videos/`` for manufacturing/process videos attached to WhatsApp messages

Default Instagram reel links are exposed so the UI can offer them when a
user has not uploaded a video yet.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..governance.audit import log_event
from ..media_inventory import media_inventory
from ..models import User
from ..security import get_current_user
from ..services import GCSStorage

router = APIRouter(prefix="/media", tags=["media"])

GCS_BUCKET = "kalika_enterprises"
IMAGE_TEMPLATE_PREFIX = "sales-metadata/sales-image-templates"
ALLOWED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff")
ALLOWED_VIDEO_EXTENSIONS = (".mp4", ".mov", ".webm", ".mkv", ".avi")
ALLOWED_DOC_EXTENSIONS = (".pdf",)

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


def _signed_url_for(path: str, bucket: str, hours: int = 24) -> str:
    """Return a signed download URL when GCS is available; otherwise the public URL."""
    gcs = GCSStorage(bucket_name=bucket)
    if gcs.available and gcs._client is not None:
        try:
            blob = gcs._client.bucket(gcs.bucket_name).blob(path)
            return blob.generate_signed_url(
                expires=datetime.utcnow() + timedelta(hours=hours), method="GET"
            )
        except Exception:  # noqa: BLE001 - fall back to plain URL
            pass
    return f"https://storage.googleapis.com/{bucket}/{path}"


def _signed_url(path: str, hours: int = 24) -> str:
    return _signed_url_for(path, GCS_BUCKET, hours)


def _load_ui_kit() -> dict[str, Any] | None:
    root = Path(__file__).resolve().parents[2] / settings.UI_ASSETS_KIT_PATH
    if not root.is_dir():
        return None

    def read_json(relative: str) -> Any:
        path = root / relative
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None

    def read_text(relative: str) -> str:
        path = root / relative
        if not path.is_file():
            return ""
        try:
            return path.read_text(encoding="utf-8")[:8000]
        except (OSError, UnicodeDecodeError):
            return ""

    template_dir = root / "html-templates"
    templates = (
        sorted(path.name for path in template_dir.glob("*.html")) if template_dir.is_dir() else []
    )
    return {
        "source": settings.UI_ASSETS_KIT_PATH.replace("\\", "/"),
        "palette": read_json("data/kaliflow_palette.json"),
        "dashboard_sample": read_json("data/dashboard_overview_sample.json"),
        "daily_rate_sample": read_json("data/daily_rates_video_sample.json"),
        "templates": templates,
        "stats_doc": read_text("docs/KALIFLOW_STATS_AND_PATTERNS.md"),
        "base_prompt": read_text("prompts/BASE_PROMPT_KALIFLOW_DASHBOARD_UI_UPDATES.md"),
    }


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


@router.get("/ui-assets")
def ui_assets(user: User = Depends(get_current_user)):
    """UI-only assets from ``gs://sales-crm/assets/UI`` for the overview panel."""
    bucket = settings.UI_ASSETS_GCS_BUCKET
    prefix = settings.UI_ASSETS_GCS_PREFIX.strip("/")
    source = f"gs://{bucket}/{prefix}/"
    payload: dict[str, Any] = {
        "enabled": settings.UI_ASSETS_ENABLED,
        "prompt_tag": settings.UI_ASSETS_PROMPT_TAG,
        "prompt_text": settings.UI_ASSETS_PROMPT_TEXT,
        "source": source,
        "kit": _load_ui_kit(),
        "items": [],
        "daily_rate_template": None,
        "business_kpis": None,
        "dashboards": [],
    }
    if not settings.UI_ASSETS_ENABLED:
        return payload

    gcs = GCSStorage(bucket_name=bucket)
    if not gcs.available:
        payload["error"] = "GCS is not available"
        return payload

    for blob in gcs.list_blobs(prefix=f"{prefix}/"):
        name = str(blob.get("name") or "")
        filename = name.rsplit("/", 1)[-1]
        if not filename:
            continue
        item = {
            "name": filename,
            "path": name,
            "url": _signed_url_for(name, bucket),
            "size": blob.get("size"),
            "updated": blob.get("updated"),
            "kind": "json"
            if filename.endswith(".json")
            else "html"
            if filename.endswith(".html")
            else "other",
        }
        payload["items"].append(item)
        if filename.endswith(".html") and "dashboard" in filename.lower():
            payload["dashboards"].append(item)

        size = int(blob.get("size") or 0)
        if filename.endswith(".json") and 0 < size <= settings.UI_ASSETS_JSON_MAX_BYTES:
            raw = gcs.download_blob(name)
            if not raw:
                continue
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if data.get("template_id") and payload["daily_rate_template"] is None:
                payload["daily_rate_template"] = data
            if "business_kpis" in data and payload["business_kpis"] is None:
                payload["business_kpis"] = data

    payload["items"].sort(key=lambda x: str(x.get("updated") or ""), reverse=True)
    preferred = "kaliflow_kalika_enterprises_3d_manufacturing_dashboard.html"
    payload["dashboards"].sort(key=lambda x: (x["name"] != preferred, x["name"]))
    return payload


@router.post("/upload")
async def upload_media(
    kind: str = Query(default="image"),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kind = (kind or "image").strip().lower()
    if kind not in {"image", "video", "image_template", "catalogue"}:
        raise HTTPException(status_code=400, detail="kind must be image, video or image_template")
    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="File name is required")
    allowed = (
        ALLOWED_VIDEO_EXTENSIONS
        if kind == "video"
        else (ALLOWED_DOC_EXTENSIONS if kind == "catalogue" else ALLOWED_IMAGE_EXTENSIONS)
    )
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
    elif kind == "catalogue":
        prefix = "catalogues"
    else:
        prefix = "videos"
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_name = "".join(
        c if c.isalnum() or c in "._-" else "_" for c in filename.replace(" ", "_")
    )[-120:]
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


@router.get("/inventory")
def get_media_inventory(
    kind: str = Query(default="image", pattern="^(image|video)$"),
    prefix: str = Query(default=""),
    limit: int = Query(default=500, ge=1, le=2000),
    signed: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Metadata-only GCS inventory for videos/images; bytes are never fetched."""
    try:
        return media_inventory(db, kind=kind, prefix=prefix, limit=limit, signed=signed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/video-link")
def store_video_link(
    payload: dict[str, Any], user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Store a video URL (e.g. Instagram reel) reference under videos/ as a .txt pointer."""
    url = str(payload.get("url") or "").strip()
    name = str(payload.get("name") or "video link").strip() or "video link"
    if not url:
        raise HTTPException(status_code=400, detail="Video url is required")
    if not url.startswith(("https://", "http://")):
        raise HTTPException(status_code=400, detail="Video url must start with https://")

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_name = (
        "".join(c if c.isalnum() or c in "._-" else "_" for c in name.replace(" ", "_"))[:80]
        or "video"
    )
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
