from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Topic
from app.schemas import CATEGORY_LABELS, CustomTopicCreate, TopicRead, TopicSuggestion

router = APIRouter(prefix="/topics", tags=["topics"])

EXTRA_SUGGESTIONS: dict[str, list[tuple[str, str]]] = {
    "business-tips": [
        ("The one metric hiding in your invoices", "A simple way to spot leakage."),
        ("How to delegate without losing quality", "Build a review loop, not a bottleneck."),
        ("A pricing test you can run this month", "Small experiment, clear signal."),
    ],
    "erp-walkthrough": [
        ("Reconciling stock after a busy week", "A clean, repeatable close-out flow."),
        ("Building a dashboard your team will actually use", "Fewer metrics, better decisions."),
        ("Approving a purchase request end to end", "Roles, limits, and audit trail."),
    ],
    "financial-education": [
        ("The break-even point, explained simply", "One formula every owner should know."),
        ("How to build a 13-week cash forecast", "A practical weekly routine."),
        ("Fixed vs variable costs in plain language", "Why it changes your pricing."),
    ],
}


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)) -> list[dict]:
    counts = dict(
        db.execute(
            select(Topic.category, func.count(Topic.id)).group_by(Topic.category)
        ).all()
    )
    return [
        {
            "id": category,
            "label": label,
            "description": _category_description(category),
            "topic_count": counts.get(category, 0),
        }
        for category, label in CATEGORY_LABELS.items()
    ]


def _category_description(category: str) -> str:
    return {
        "business-tips": "Practical operating advice for owners and small teams.",
        "erp-walkthrough": "Clear product tours for ERP and production workflows.",
        "financial-education": "Plain-language finance lessons for business decisions.",
    }.get(category, "")


@router.get("", response_model=list[TopicRead])
def list_topics(
    category: str | None = None,
    db: Session = Depends(get_db),
) -> list[Topic]:
    statement = select(Topic).order_by(Topic.created_at.asc())
    if category:
        statement = statement.where(Topic.category == category)
    return list(db.execute(statement).scalars().all())


@router.get("/suggest", response_model=list[TopicSuggestion])
def suggest_topics(
    category: str = Query(pattern="^(business-tips|erp-walkthrough|financial-education)$"),
    limit: int = Query(default=6, ge=1, le=20),
    db: Session = Depends(get_db),
) -> list[TopicSuggestion]:
    topics = list(
        db.execute(
            select(Topic)
            .where(Topic.category == category)
            .order_by(Topic.created_at.asc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    suggestions = [
        TopicSuggestion(title=topic.title, description=topic.description, category=topic.category)
        for topic in topics
    ]
    if len(suggestions) < limit:
        existing = {item.title for item in suggestions}
        for title, description in EXTRA_SUGGESTIONS.get(category, []):
            if title in existing:
                continue
            suggestions.append(
                TopicSuggestion(title=title, description=description, category=category)
            )
            if len(suggestions) >= limit:
                break
    return suggestions


@router.post("/custom", response_model=TopicRead, status_code=201)
def add_custom_topic(payload: CustomTopicCreate, db: Session = Depends(get_db)) -> Topic:
    topic = Topic(
        category=payload.category,
        title=payload.title,
        description=payload.description,
        is_custom=True,
    )
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return topic
