import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_project_or_404, get_render_or_404
from app.core.database import SessionLocal, get_db
from app.models import Project, RenderJob
from app.schemas import RenderCreate, RenderLogs, RenderRead
from app.services.media.render_service import RenderError, RenderService, get_render_service

router = APIRouter(tags=["rendering"])


@router.post("/projects/{project_id}/renders", response_model=RenderRead, status_code=201)
def create_render(
    payload: RenderCreate,
    project: Project = Depends(get_project_or_404),
    db: Session = Depends(get_db),
    service: RenderService = Depends(get_render_service),
) -> RenderJob:
    try:
        return service.create_job(db, project, payload.model_dump())
    except RenderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects/{project_id}/renders", response_model=list[RenderRead])
def list_renders(
    project: Project = Depends(get_project_or_404),
    db: Session = Depends(get_db),
) -> list[RenderJob]:
    statement = (
        select(RenderJob)
        .where(RenderJob.project_id == project.id)
        .order_by(RenderJob.created_at.desc())
    )
    return list(db.execute(statement).scalars().all())


@router.get("/renders/{job_id}", response_model=RenderRead)
def get_render(job: RenderJob = Depends(get_render_or_404)) -> RenderJob:
    return job


@router.get("/renders/{job_id}/logs", response_model=RenderLogs)
def get_logs(job: RenderJob = Depends(get_render_or_404)) -> RenderLogs:
    lines = [line for line in (job.logs or "").splitlines() if line.strip()]
    return RenderLogs(job_id=job.id, status=job.status, logs=lines)


@router.post("/renders/{job_id}/cancel", response_model=RenderRead)
def cancel_render(
    job: RenderJob = Depends(get_render_or_404),
    db: Session = Depends(get_db),
    service: RenderService = Depends(get_render_service),
) -> RenderJob:
    return service.cancel(db, job)


@router.get("/renders/{job_id}/events")
async def render_events(
    request: Request,
    job: RenderJob = Depends(get_render_or_404),
) -> EventSourceResponse:
    job_id = job.id

    async def stream():
        previous: str | None = None
        while True:
            if await request.is_disconnected():
                break
            db = SessionLocal()
            try:
                current = db.get(RenderJob, job_id)
                if current is None:
                    break
                payload = {
                    "id": current.id,
                    "status": current.status,
                    "stage": current.stage,
                    "progress": current.progress,
                    "error": current.error,
                }
                encoded = json.dumps(payload)
                if encoded != previous:
                    previous = encoded
                    yield {"event": "progress", "data": encoded}
                if current.status in {"completed", "failed", "cancelled"}:
                    break
            finally:
                db.close()
            await asyncio.sleep(1)

    return EventSourceResponse(stream())


@router.get("/renders/{job_id}/preview")
def download_preview(job: RenderJob = Depends(get_render_or_404)) -> FileResponse:
    return _file_response(job.preview_path, f"preview-{job.id[:8]}.mp4", "Preview is not ready.")


@router.get("/renders/{job_id}/export")
def download_export(job: RenderJob = Depends(get_render_or_404)) -> FileResponse:
    return _file_response(job.export_path, f"export-{job.id[:8]}.mp4", "Export is not ready.")


def _file_response(raw_path: str | None, filename: str, missing_message: str) -> FileResponse:
    if not raw_path:
        raise HTTPException(status_code=404, detail=missing_message)
    path = Path(raw_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail=missing_message)
    return FileResponse(path, media_type="video/mp4", filename=filename)
