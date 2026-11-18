from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models import Activity, Asset, Project, RenderJob
from app.schemas import (
    CATEGORY_LABELS,
    ActivityRead,
    DashboardSummary,
    ProjectRead,
    UsageSummary,
)
from app.services.ai.router import AIService, get_ai_service

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardSummary)
def dashboard(
    db: Session = Depends(get_db),
    ai: AIService = Depends(get_ai_service),
) -> DashboardSummary:
    projects_total = db.scalar(select(func.count(Project.id))) or 0
    projects_in_progress = (
        db.scalar(
            select(func.count(Project.id)).where(
                Project.status.notin_(["rendered", "draft"])
            )
        )
        or 0
    )
    renders_active = (
        db.scalar(
            select(func.count(RenderJob.id)).where(
                RenderJob.status.in_(["queued", "running"])
            )
        )
        or 0
    )
    renders_completed = (
        db.scalar(select(func.count(RenderJob.id)).where(RenderJob.status == "completed"))
        or 0
    )
    assets_total = db.scalar(select(func.count(Asset.id))) or 0

    recent_projects = list(
        db.execute(
            select(Project)
            .options(selectinload(Project.script), selectinload(Project.storyboard))
            .order_by(Project.updated_at.desc())
            .limit(6)
        )
        .scalars()
        .all()
    )
    recent_activity = list(
        db.execute(select(Activity).order_by(Activity.created_at.desc()).limit(12))
        .scalars()
        .all()
    )
    counts = dict(
        db.execute(
            select(Project.category, func.count(Project.id)).group_by(Project.category)
        ).all()
    )
    categories = [
        {
            "id": category,
            "label": label,
            "project_count": counts.get(category, 0),
        }
        for category, label in CATEGORY_LABELS.items()
    ]
    usage: UsageSummary = ai.usage_summary(db)
    return DashboardSummary(
        projects_total=projects_total,
        projects_in_progress=projects_in_progress,
        renders_active=renders_active,
        renders_completed=renders_completed,
        assets_total=assets_total,
        usage=usage,
        recent_projects=[ProjectRead.model_validate(project) for project in recent_projects],
        recent_activity=[ActivityRead.model_validate(item) for item in recent_activity],
        categories=categories,
    )


@router.get("/activity", response_model=list[ActivityRead])
def list_activity(db: Session = Depends(get_db), limit: int = 50) -> list[Activity]:
    return list(
        db.execute(select(Activity).order_by(Activity.created_at.desc()).limit(limit))
        .scalars()
        .all()
    )
