from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Asset, Project, RenderJob
from app.schemas import AssetRead


def get_project_or_404(project_id: str, db: Session = Depends(get_db)) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


def get_render_or_404(job_id: str, db: Session = Depends(get_db)) -> RenderJob:
    job = db.get(RenderJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Render job not found.")
    return job


def get_asset_or_404(asset_id: str, db: Session = Depends(get_db)) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    return asset


def asset_read(asset: Asset) -> AssetRead:
    return AssetRead(
        id=asset.id,
        filename=asset.filename,
        original_name=asset.original_name,
        media_type=asset.media_type,
        content_type=asset.content_type,
        size_bytes=asset.size_bytes,
        tags=asset.tags or [],
        favorite=asset.favorite,
        created_at=asset.created_at,
        url=f"/api/v1/assets/{asset.id}/file",
    )
