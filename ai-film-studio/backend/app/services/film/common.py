from sqlalchemy.orm import Session

from app.models import Activity, Project
from app.schemas import CATEGORY_LABELS


def record_activity(db: Session, project_id: str | None, kind: str, message: str) -> None:
    db.add(Activity(project_id=project_id, kind=kind, message=message))
    db.commit()


def mark_step(
    db: Session,
    project: Project,
    *,
    status: str,
    step: str,
    progress: dict | None = None,
) -> None:
    project.status = status
    project.current_step = step
    if progress:
        merged = dict(project.progress or {})
        merged.update(progress)
        project.progress = merged
    db.add(project)
    db.commit()
    db.refresh(project)


def category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, category.replace("-", " ").title())
