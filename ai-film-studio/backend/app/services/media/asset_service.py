from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Asset

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".mkv", ".avi"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}


class AssetService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def save(
        self,
        db: Session,
        *,
        filename: str,
        content_type: str,
        data: bytes,
        tags: list[str] | None = None,
    ) -> Asset:
        original = Path(filename or "upload.bin").name
        suffix = Path(original).suffix.lower()
        stored_name = f"{uuid4().hex}{suffix}"
        target_dir = self.settings.storage_path / "assets"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / stored_name
        target.write_bytes(data)
        media_type = self._media_type(content_type, suffix)
        asset = Asset(
            filename=stored_name,
            original_name=original,
            media_type=media_type,
            content_type=content_type or "",
            path=str(target),
            size_bytes=len(data),
            tags=tags or [],
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        if self.settings.gcs_enabled and self.settings.gcs_auto_publish:
            try:
                from app.services.storage import GCSStorage

                GCSStorage(self.settings).publish_asset(
                    asset_id=asset.id,
                    path=target,
                    metadata={
                        "original_name": asset.original_name,
                        "media_type": asset.media_type,
                        "content_type": asset.content_type,
                        "tags": ",".join(asset.tags or []),
                    },
                )
            except Exception:  # noqa: BLE001 - local asset remains usable if GCS is down
                pass
        return asset

    def _media_type(self, content_type: str, suffix: str) -> str:
        if content_type.startswith("image/"):
            return "image"
        if content_type.startswith("video/"):
            return "video"
        if content_type.startswith("audio/"):
            return "audio"
        if suffix in IMAGE_EXTENSIONS:
            return "image"
        if suffix in VIDEO_EXTENSIONS:
            return "video"
        if suffix in AUDIO_EXTENSIONS:
            return "audio"
        return "file"

    def list(
        self,
        db: Session,
        *,
        search: str | None = None,
        media_type: str | None = None,
        tag: str | None = None,
        favorite: bool | None = None,
    ) -> list[Asset]:
        statement = select(Asset).order_by(Asset.created_at.desc())
        if media_type:
            statement = statement.where(Asset.media_type == media_type)
        if favorite is not None:
            statement = statement.where(Asset.favorite == favorite)
        assets = list(db.execute(statement).scalars().all())
        if search:
            needle = search.lower()
            assets = [
                asset
                for asset in assets
                if needle in asset.original_name.lower()
                or any(needle in value.lower() for value in (asset.tags or []))
            ]
        if tag:
            assets = [asset for asset in assets if tag in (asset.tags or [])]
        return assets

    def update(self, db: Session, asset: Asset, *, tags: list[str] | None, favorite: bool | None) -> Asset:
        if tags is not None:
            asset.tags = tags
        if favorite is not None:
            asset.favorite = favorite
        db.add(asset)
        db.commit()
        db.refresh(asset)
        return asset

    def delete(self, db: Session, asset: Asset) -> None:
        path = Path(asset.path)
        if path.exists() and path.is_file():
            path.unlink()
        db.delete(asset)
        db.commit()

    def clear_all(self) -> None:
        """Test helper: remove stored asset files."""
        target_dir = self.settings.storage_path / "assets"
        if target_dir.exists():
            for item in target_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
