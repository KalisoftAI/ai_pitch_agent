from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_project_or_404
from app.core.database import get_db
from app.models import Project, Scene, Storyboard
from app.schemas import (
    ApproveRequest,
    SceneRead,
    SceneRegenerateRequest,
    SceneReorderRequest,
    SceneUpdate,
    StoryboardGenerateRequest,
    StoryboardRead,
)
from app.services.ai.router import get_ai_service
from app.services.film.script_service import ScriptService
from app.services.film.storyboard_service import StoryboardService

router = APIRouter(prefix="/projects/{project_id}/storyboard", tags=["storyboards"])


def _service() -> StoryboardService:
    ai = get_ai_service()
    return StoryboardService(ai, ScriptService(ai))


def _require_storyboard(db: Session, project_id: str) -> Storyboard:
    storyboard = _service().get(db, project_id)
    if storyboard is None:
        raise HTTPException(status_code=404, detail="No storyboard exists for this project.")
    return storyboard


@router.get("", response_model=StoryboardRead)
def get_storyboard(
    project: Project = Depends(get_project_or_404),
    db: Session = Depends(get_db),
) -> Storyboard:
    return _require_storyboard(db, project.id)


@router.post("/generate", response_model=StoryboardRead)
async def generate_storyboard(
    payload: StoryboardGenerateRequest,
    project: Project = Depends(get_project_or_404),
    db: Session = Depends(get_db),
) -> Storyboard:
    try:
        return await _service().generate(db, project, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/scenes/{scene_id}", response_model=SceneRead)
def update_scene(
    scene_id: str,
    payload: SceneUpdate,
    project: Project = Depends(get_project_or_404),
    db: Session = Depends(get_db),
) -> Scene:
    storyboard = _require_storyboard(db, project.id)
    try:
        return _service().update_scene(db, storyboard, scene_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scenes/reorder", response_model=StoryboardRead)
def reorder_scenes(
    payload: SceneReorderRequest,
    project: Project = Depends(get_project_or_404),
    db: Session = Depends(get_db),
) -> Storyboard:
    storyboard = _require_storyboard(db, project.id)
    try:
        return _service().reorder(db, storyboard, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scenes/{scene_id}/regenerate", response_model=SceneRead)
async def regenerate_scene(
    scene_id: str,
    payload: SceneRegenerateRequest,
    project: Project = Depends(get_project_or_404),
    db: Session = Depends(get_db),
) -> Scene:
    storyboard = _require_storyboard(db, project.id)
    try:
        return await _service().regenerate_scene(db, storyboard, scene_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/approve", response_model=StoryboardRead)
def approve_storyboard(
    payload: ApproveRequest,
    project: Project = Depends(get_project_or_404),
    db: Session = Depends(get_db),
) -> Storyboard:
    storyboard = _require_storyboard(db, project.id)
    return _service().approve(db, project, storyboard, payload.approved)
