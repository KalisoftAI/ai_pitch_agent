from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_project_or_404
from app.core.database import get_db
from app.models import Project, Script
from app.schemas import (
    ApproveRequest,
    ParagraphRegenerateRequest,
    ScriptGenerateRequest,
    ScriptRead,
    ScriptUpdate,
)
from app.services.ai.router import get_ai_service
from app.services.film.script_service import ScriptService

router = APIRouter(prefix="/projects/{project_id}/script", tags=["scripts"])


def _service() -> ScriptService:
    return ScriptService(get_ai_service())


@router.get("", response_model=ScriptRead)
def get_script(
    project: Project = Depends(get_project_or_404),
    db: Session = Depends(get_db),
) -> Script:
    script = _service().get(db, project.id)
    if script is None:
        raise HTTPException(status_code=404, detail="No script has been generated yet.")
    return script


@router.post("/generate", response_model=ScriptRead)
async def generate_script(
    payload: ScriptGenerateRequest,
    project: Project = Depends(get_project_or_404),
    db: Session = Depends(get_db),
) -> Script:
    try:
        return await _service().generate(db, project, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("", response_model=ScriptRead)
def update_script(
    payload: ScriptUpdate,
    project: Project = Depends(get_project_or_404),
    db: Session = Depends(get_db),
) -> Script:
    return _service().update(db, project, payload.content)


@router.post("/regenerate-paragraph", response_model=ScriptRead)
async def regenerate_paragraph(
    payload: ParagraphRegenerateRequest,
    project: Project = Depends(get_project_or_404),
    db: Session = Depends(get_db),
) -> Script:
    try:
        return await _service().regenerate_paragraph(db, project, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/approve", response_model=ScriptRead)
def approve_script(
    payload: ApproveRequest,
    project: Project = Depends(get_project_or_404),
    db: Session = Depends(get_db),
) -> Script:
    try:
        return _service().approve(db, project, payload.approved)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
