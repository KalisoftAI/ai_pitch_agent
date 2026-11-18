from __future__ import annotations

import hashlib
import json
import mimetypes
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings


class StorageError(RuntimeError):
    pass


class StorageUnavailable(StorageError):
    pass


@dataclass
class StorageStatus:
    enabled: bool
    available: bool
    bucket: str
    prefix: str
    project: str
    message: str


class GCSStorage:
    """ADC-backed Google Cloud Storage helper for reusable studio assets."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = None
        self._bucket = None
        self._status: tuple[float, StorageStatus] | None = None

    @property
    def bucket_name(self) -> str:
        return self.settings.gcs_bucket

    @property
    def root(self) -> str:
        return self.settings.gcs_root

    def _get_client(self):
        if not self.settings.gcs_enabled:
            raise StorageUnavailable("GCS publishing is disabled.")
        if self._client is not None:
            return self._client
        try:
            from google.cloud import storage
        except ImportError as exc:
            raise StorageUnavailable(
                "google-cloud-storage is not installed. Run pip install -r requirements.txt."
            ) from exc
        try:
            self._client = storage.Client(project=self.settings.gcs_project or None)
        except Exception as exc:  # noqa: BLE001 - ADC and network errors are user-facing
            raise StorageUnavailable(f"Could not create a GCS client: {exc}") from exc
        return self._client

    def _get_bucket(self):
        if self._bucket is not None:
            return self._bucket
        client = self._get_client()
        try:
            self._bucket = client.bucket(self.bucket_name)
        except Exception as exc:  # noqa: BLE001
            raise StorageUnavailable(f"Could not open bucket {self.bucket_name}: {exc}") from exc
        return self._bucket

    def status(self, *, refresh: bool = False) -> StorageStatus:
        if not self.settings.gcs_enabled:
            return StorageStatus(
                enabled=False,
                available=False,
                bucket=self.bucket_name,
                prefix=self.root,
                project=self.settings.gcs_project,
                message="GCS publishing is disabled.",
            )
        now = time.monotonic()
        if not refresh and self._status and now - self._status[0] < 30:
            return self._status[1]
        try:
            bucket = self._get_bucket()
            bucket.reload(timeout=self.settings.gcs_timeout_seconds)
            status = StorageStatus(
                enabled=True,
                available=True,
                bucket=bucket.name,
                prefix=self.root,
                project=self.settings.gcs_project,
                message=f"Connected to gs://{bucket.name}/{self.root}.",
            )
        except Exception as exc:  # noqa: BLE001
            status = StorageStatus(
                enabled=True,
                available=False,
                bucket=self.bucket_name,
                prefix=self.root,
                project=self.settings.gcs_project,
                message=str(exc)[:300],
            )
        self._status = (now, status)
        return status

    def available(self) -> tuple[bool, str]:
        status = self.status()
        return status.available, status.message

    def _full_name(self, name: str) -> str:
        clean = name.replace("\\", "/").strip("/")
        if clean.startswith(f"{self.root}/") or clean == self.root:
            return clean
        return f"{self.root}/{clean}" if self.root else clean

    def _blob(self, name: str):
        return self._get_bucket().blob(self._full_name(name))

    def _safe_name(self, value: str) -> str:
        allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_./"
        cleaned = "".join(char if char in allowed else "-" for char in value).strip("./")
        return cleaned or "object"

    def _metadata(self, path: Path, extra: dict[str, Any] | None = None) -> dict[str, str]:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        data = {
            "sha256": digest.hexdigest(),
            "source": path.name,
            "uploaded_at": datetime.now(UTC).isoformat(),
            "studio": "ai-film-studio",
        }
        for key, value in (extra or {}).items():
            if value is not None:
                data[str(key)] = str(value)
        return data

    def upload_file(
        self,
        path: Path,
        folder: str,
        *,
        remote_name: str | None = None,
        metadata: dict[str, Any] | None = None,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        if not path.exists() or not path.is_file():
            raise StorageError(f"Local file does not exist: {path}")
        name = self._safe_name(remote_name or path.name)
        full = self._full_name(f"{folder.strip('/')}/{name}")
        blob = self._get_bucket().blob(full)
        blob.metadata = self._metadata(path, metadata)
        blob.content_type = content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        blob.upload_from_filename(
            str(path),
            content_type=blob.content_type,
            timeout=self.settings.gcs_timeout_seconds,
        )
        blob.reload(timeout=self.settings.gcs_timeout_seconds)
        self._status = None
        return {
            "name": blob.name,
            "uri": f"gs://{self.bucket_name}/{blob.name}",
            "size": int(blob.size or path.stat().st_size),
            "content_type": blob.content_type,
            "updated": blob.updated.isoformat() if blob.updated else None,
            "sha256": (blob.metadata or {}).get("sha256"),
            "metadata": blob.metadata or {},
        }

    def upload_bytes(
        self,
        data: bytes,
        folder: str,
        remote_name: str,
        *,
        content_type: str = "application/octet-stream",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        full = self._full_name(f"{folder.strip('/')}/{self._safe_name(remote_name)}")
        blob = self._get_bucket().blob(full)
        payload = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "uploaded_at": datetime.now(UTC).isoformat(),
            "studio": "ai-film-studio",
        }
        payload.update({str(key): str(value) for key, value in (metadata or {}).items()})
        blob.metadata = payload
        blob.upload_from_string(
            data,
            content_type=content_type,
            timeout=self.settings.gcs_timeout_seconds,
        )
        blob.reload(timeout=self.settings.gcs_timeout_seconds)
        self._status = None
        return {
            "name": blob.name,
            "uri": f"gs://{self.bucket_name}/{blob.name}",
            "size": int(blob.size or len(data)),
            "content_type": blob.content_type,
            "updated": blob.updated.isoformat() if blob.updated else None,
            "sha256": payload["sha256"],
            "metadata": blob.metadata or {},
        }

    def upload_json(self, payload: dict[str, Any], folder: str, remote_name: str) -> dict[str, Any]:
        return self.upload_bytes(
            json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
            folder,
            remote_name,
            content_type="application/json",
            metadata={"kind": "manifest"},
        )

    def list_objects(self, prefix: str = "", limit: int = 100) -> list[dict[str, Any]]:
        full = self._full_name(prefix.strip("/")) if prefix else self.root
        if full and not full.endswith("/"):
            full += "/"
        blobs = self._get_client().list_blobs(
            self.bucket_name,
            prefix=full,
            max_results=max(1, min(limit, 1000)),
            timeout=self.settings.gcs_timeout_seconds,
        )
        result = []
        for blob in blobs:
            result.append(
                {
                    "name": blob.name,
                    "uri": f"gs://{self.bucket_name}/{blob.name}",
                    "size": int(blob.size or 0),
                    "content_type": blob.content_type,
                    "updated": blob.updated.isoformat() if blob.updated else None,
                    "metadata": blob.metadata or {},
                }
            )
        return result

    def download_file(self, name: str, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._blob(name).download_to_filename(
            str(path), timeout=self.settings.gcs_timeout_seconds
        )
        return path

    def delete_object(self, name: str) -> None:
        self._blob(name).delete(timeout=self.settings.gcs_timeout_seconds)
        self._status = None

    def publish_render(
        self,
        *,
        job_id: str,
        project_id: str,
        preview: Path | None,
        export: Path | None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        folder = f"renders/{project_id}/{job_id}"
        objects: list[dict[str, Any]] = []
        if preview and preview.exists():
            objects.append(
                self.upload_file(
                    preview,
                    folder,
                    remote_name="preview.mp4",
                    content_type="video/mp4",
                    metadata={**(metadata or {}), "kind": "preview", "job_id": job_id},
                )
            )
        if export and export.exists():
            objects.append(
                self.upload_file(
                    export,
                    folder,
                    remote_name="export.mp4",
                    content_type="video/mp4",
                    metadata={**(metadata or {}), "kind": "export", "job_id": job_id},
                )
            )
        manifest = {
            "job_id": job_id,
            "project_id": project_id,
            "published_at": datetime.now(UTC).isoformat(),
            "bucket": self.bucket_name,
            "prefix": self.root,
            "objects": objects,
            "metadata": metadata or {},
        }
        manifest_object = self.upload_json(
            manifest, f"metadata/renders/{project_id}", f"{job_id}.json"
        )
        return {
            "bucket": self.bucket_name,
            "prefix": self.root,
            "folder": f"{self.root}/{folder}",
            "objects": objects,
            "manifest": manifest_object,
            "published_at": manifest["published_at"],
        }

    def publish_asset(self, *, asset_id: str, path: Path, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.upload_file(
            path,
            f"assets/{asset_id}",
            metadata={**(metadata or {}), "asset_id": asset_id},
        )

    def gallery(self, limit: int = 50) -> list[dict[str, Any]]:
        objects = self.list_objects("renders", limit=limit)
        videos = [item for item in objects if str(item.get("content_type", "")).startswith("video/")]
        return sorted(videos, key=lambda item: item.get("updated") or "", reverse=True)


def get_storage(settings: Settings | None = None) -> GCSStorage:
    return GCSStorage(settings)
