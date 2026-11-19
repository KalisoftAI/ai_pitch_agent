from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import asset_read, get_asset_or_404
from app.core.database import get_db
from app.models import Asset
from app.schemas import AssetRead, AssetUpdate
from app.services.media.asset_service import AssetService

router = APIRouter(prefix="/assets", tags=["assets"])
service = AssetService()

MAX_UPLOAD_BYTES = 100 * 1024 * 1024


@router.post("", response_model=AssetRead, status_code=201)
async def upload_asset(
    file: UploadFile = File(...),
    tags: str = Form(default=""),
    db: Session = Depends(get_db),
) -> AssetRead:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than 100 MB.")
    tag_list = [item.strip() for item in tags.split(",") if item.strip()]
    asset = service.save(
        db,
        filename=file.filename or "upload.bin",
        content_type=file.content_type or "",
        data=data,
        tags=tag_list,
    )
    return asset_read(asset)


@router.get("", response_model=list[AssetRead])
def list_assets(
    search: str | None = None,
    media_type: str | None = None,
    tag: str | None = None,
    favorite: bool | None = None,
    db: Session = Depends(get_db),
) -> list[AssetRead]:
    assets = service.list(
        db, search=search, media_type=media_type, tag=tag, favorite=favorite
    )
    return [asset_read(asset) for asset in assets]


@router.get("/{asset_id}", response_model=AssetRead)
def get_asset(asset: Asset = Depends(get_asset_or_404)) -> AssetRead:
    return asset_read(asset)


@router.patch("/{asset_id}", response_model=AssetRead)
def update_asset(
    payload: AssetUpdate,
    asset: Asset = Depends(get_asset_or_404),
    db: Session = Depends(get_db),
) -> AssetRead:
    updated = service.update(
        db, asset, tags=payload.tags, favorite=payload.favorite
    )
    return asset_read(updated)


@router.delete("/{asset_id}", status_code=204)
def delete_asset(
    asset: Asset = Depends(get_asset_or_404),
    db: Session = Depends(get_db),
) -> None:
    service.delete(db, asset)


@router.get("/{asset_id}/file")
def get_asset_file(asset: Asset = Depends(get_asset_or_404)) -> FileResponse:
    path = Path(asset.path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Asset file is missing from disk.")
    return FileResponse(
        path,
        media_type=asset.content_type or "application/octet-stream",
        filename=asset.original_name,
    )
