"""Cheap GCS media inventory.

Metadata-only listing with a persisted signature so repeat calls can detect
changes without downloading video/image bytes. Signed URLs are generated only
when explicitly requested by the caller.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from .config import settings
from .models import IntegrationSetting
from .services import GCSStorage

_VIDEO_SUFFIXES = (".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v")
_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff")
_PREFIXES: dict[str, list[tuple[str, str]]] = {
    "image": [
        ("kalika_enterprises", "images/"),
        ("kalika_enterprises", "sales-metadata/sales-image-templates/"),
        ("sales-crm", "assets/"),
    ],
    "video": [
        ("kalika_enterprises", "videos/"),
        ("sales-crm", "Manufacturing-Data/kalika-videos/"),
        ("sales-crm", "marketing-videos/"),
    ],
}


def _setting(db: Session, key: str, default: str = "") -> str:
    row = db.query(IntegrationSetting).filter(IntegrationSetting.key == key).first()
    return row.value if row and row.value else default


def _put_setting(db: Session, key: str, value: str) -> None:
    row = db.query(IntegrationSetting).filter(IntegrationSetting.key == key).first()
    if row is None:
        db.add(IntegrationSetting(key=key, value=value))
    else:
        row.value = value
        row.updated_at = datetime.now(timezone.utc)
    db.commit()


def media_inventory(
    db: Session,
    *,
    kind: str = "image",
    limit: int | None = None,
    prefix: str = "",
    signed: bool = False,
    signed_hours: int = 1,
) -> dict[str, Any]:
    kind = (kind or "image").strip().lower()
    if kind not in _PREFIXES:
        raise ValueError("kind must be image or video")
    suffixes = _IMAGE_SUFFIXES if kind == "image" else _VIDEO_SUFFIXES
    cap = max(1, min(int(limit or settings.GCS_MEDIA_INVENTORY_LIMIT), 2000))
    selected = _PREFIXES[kind]
    if prefix.strip():
        clean = prefix.strip().strip("/") + "/"
        selected = [(bucket, clean) for bucket, _ in selected]

    clients: dict[str, GCSStorage] = {}
    items: list[dict[str, Any]] = []
    for bucket_name, blob_prefix in selected:
        gcs = clients.setdefault(bucket_name, GCSStorage(bucket_name=bucket_name))
        if not gcs.available:
            continue
        for blob in gcs.list_blobs(prefix=blob_prefix, suffixes=suffixes, max_results=cap):
            items.append(
                {
                    "name": blob["name"].split("/")[-1],
                    "path": blob["name"],
                    "gcs_uri": f"gs://{bucket_name}/{blob['name']}",
                    "bucket": bucket_name,
                    "size": blob.get("size"),
                    "updated": blob.get("updated"),
                    "content_type": blob.get("content_type"),
                    "kind": kind,
                }
            )

    items.sort(key=lambda item: str(item.get("updated") or ""), reverse=True)
    items = items[:cap]
    signature_payload = [
        {"path": item["path"], "updated": item["updated"], "size": item["size"]} for item in items
    ]
    signature = hashlib.sha256(
        json.dumps(signature_payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    key = f"media.inventory.{kind}.{prefix.strip() or 'all'}"
    previous = _setting(db, key)

    if signed:
        from datetime import timedelta

        for item in items:
            gcs = clients[item["bucket"]]
            if not gcs.available or gcs._client is None:
                item["url"] = ""
                continue
            try:
                blob = gcs._client.bucket(gcs.bucket_name).blob(item["path"])
                item["url"] = blob.generate_signed_url(
                    expires=datetime.utcnow() + timedelta(hours=max(1, min(signed_hours, 24))),
                    method="GET",
                )
            except Exception:  # noqa: BLE001 - keep metadata when signing is unavailable
                item["url"] = ""

    _put_setting(db, key, signature)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "prefixes": [{"bucket": bucket, "prefix": p} for bucket, p in selected],
        "signature": signature,
        "changed": bool(previous and previous != signature),
        "count": len(items),
        "items": items,
    }
