from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_render_or_404
from app.core.config import get_settings
from app.core.database import get_db
from app.models import RenderJob
from app.schemas import StorageObjectRead, StoragePublishRead, StorageStatusRead
from app.services.media.render_service import get_render_service
from app.services.storage import GCSStorage, StorageError, StorageUnavailable

router = APIRouter(tags=["storage"])


@router.get("/storage/status", response_model=StorageStatusRead)
def storage_status(refresh: bool = Query(default=False)) -> StorageStatusRead:
    status = GCSStorage(get_settings()).status(refresh=refresh)
    return StorageStatusRead(**status.__dict__)


@router.get("/storage/objects", response_model=list[StorageObjectRead])
def storage_objects(
    prefix: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[StorageObjectRead]:
    try:
        objects = GCSStorage(get_settings()).list_objects(prefix, limit=limit)
    except StorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [StorageObjectRead(**item) for item in objects]


@router.get("/storage/gallery", response_model=list[StorageObjectRead])
def storage_gallery(limit: int = Query(default=50, ge=1, le=200)) -> list[StorageObjectRead]:
    try:
        objects = GCSStorage(get_settings()).gallery(limit=limit)
    except StorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [StorageObjectRead(**item) for item in objects]


@router.post("/storage/upload", response_model=StorageObjectRead, status_code=201)
def storage_upload(
    file: UploadFile = File(...),
    folder: str = Form(default="assets/uploads"),
    tags: str = Form(default=""),
) -> StorageObjectRead:
    settings = get_settings()
    target_dir = settings.storage_path / "temp" / "uploads"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / (Path(file.filename or "upload.bin").name)
    try:
        with target.open("wb") as handle:
            shutil.copyfileobj(file.file, handle)
        result = GCSStorage(settings).upload_file(
            target,
            folder,
            metadata={"tags": tags, "original_name": file.filename or target.name},
            content_type=file.content_type,
        )
    except StorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        target.unlink(missing_ok=True)
    return StorageObjectRead(**result)


@router.post("/renders/{job_id}/publish", response_model=StoragePublishRead)
def publish_render(
    job: RenderJob = Depends(get_render_or_404),
    db: Session = Depends(get_db),
) -> StoragePublishRead:
    service = get_render_service()
    try:
        result = service.publish(db, job)
    except StorageUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StoragePublishRead(**result)


@router.delete("/storage/object")
def delete_storage_object(name: str = Query(min_length=1)) -> dict[str, str]:
    try:
        GCSStorage(get_settings()).delete_object(name)
    except StorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "deleted", "name": name}
