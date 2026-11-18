from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_project_or_404
from app.core.database import get_db
from app.models import Project
from app.schemas import ProjectCreate, ProjectProgressUpdate, ProjectRead, ProjectUpdate
from app.services.film.common import record_activity

router = APIRouter(prefix="/projects", tags=["projects"])

PROJECT_LOADS = (
    selectinload(Project.script),
    selectinload(Project.storyboard),
)


@router.get("", response_model=list[ProjectRead])
def list_projects(
    db: Session = Depends(get_db),
    category: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = None,
    sort: str = Query(default="updated", pattern="^(updated|created|title)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[Project]:
    statement = select(Project).options(*PROJECT_LOADS)
    if category:
        statement = statement.where(Project.category == category)
    if status_filter:
        statement = statement.where(Project.status == status_filter)
    if search:
        needle = f"%{search.lower()}%"
        statement = statement.where(
            Project.title.ilike(needle) | Project.topic.ilike(needle)
        )
    if sort == "created":
        statement = statement.order_by(Project.created_at.desc())
    elif sort == "title":
        statement = statement.order_by(Project.title.asc())
    else:
        statement = statement.order_by(Project.updated_at.desc())
    statement = statement.limit(limit).offset(offset)
    return list(db.execute(statement).scalars().all())


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    project = Project(
        title=payload.title,
        category=payload.category,
        topic=payload.topic,
        description=payload.description,
        visual_style=payload.visual_style,
        template=payload.template,
        duration_seconds=payload.duration_seconds,
        aspect_ratio=payload.aspect_ratio,
        status="draft",
        current_step="category",
        progress={},
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    record_activity(db, project.id, "project", f"Created project '{project.title}'.")
    return project


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project: Project = Depends(get_project_or_404)) -> Project:
    return project


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    payload: ProjectUpdate,
    project: Project = Depends(get_project_or_404),
    db: Session = Depends(get_db),
) -> Project:
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(project, key, value)
    db.add(project)
    db.commit()
    db.refresh(project)
    record_activity(db, project.id, "project", f"Updated project '{project.title}'.")
    return project


@router.post("/{project_id}/progress", response_model=ProjectRead)
def save_progress(
    payload: ProjectProgressUpdate,
    project: Project = Depends(get_project_or_404),
    db: Session = Depends(get_db),
) -> Project:
    if payload.current_step:
        project.current_step = payload.current_step
    if payload.status:
        project.status = payload.status
    if payload.progress:
        merged = dict(project.progress or {})
        merged.update(payload.progress)
        project.progress = merged
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project: Project = Depends(get_project_or_404),
    db: Session = Depends(get_db),
) -> None:
    title = project.title
    db.delete(project)
    db.commit()
    record_activity(db, None, "project", f"Deleted project '{title}'.")
