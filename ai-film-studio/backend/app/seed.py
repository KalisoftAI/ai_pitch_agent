from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import Activity, Asset, Project, Scene, Script, Storyboard, Topic

TOPICS: dict[str, list[tuple[str, str]]] = {
    "business-tips": [
        ("The 3 numbers every small business should review weekly", "Cash, margin, and pipeline in one simple ritual."),
        ("Stop discounting before you fix this one process", "A practical look at pricing discipline."),
        ("How to turn customer complaints into a growth system", "Capture, categorise, and close the loop."),
        ("A 15-minute weekly planning routine that actually works", "A lightweight operating rhythm for busy teams."),
        ("Why your best salesperson should document their process", "Turn tribal knowledge into repeatable playbooks."),
    ],
    "erp-walkthrough": [
        ("From purchase order to stock receipt in five clicks", "A guided walkthrough of the inbound flow."),
        ("How to spot a production bottleneck in your dashboard", "Read the signals before the delay compounds."),
        ("Setting up role-based access without slowing the team", "Practical permissions for growing operations."),
        ("Month-end inventory reconciliation, simplified", "A repeatable checklist for clean stock numbers."),
        ("Turning a sales order into a production plan", "Connect demand to the shop floor."),
    ],
    "financial-education": [
        ("Cash flow vs profit: the difference that sinks businesses", "Why a profitable month can still run out of cash."),
        ("How to read a balance sheet in under five minutes", "A plain-language tour for non-finance founders."),
        ("The working capital trap hiding in your growth plan", "Growth consumes cash; plan for it."),
        ("Three ratios that reveal business health early", "A compact dashboard for owners."),
        ("Why forecasting is a habit, not a spreadsheet", "Build a monthly rhythm that reduces surprises."),
    ],
}


def seed_topics(db: Session) -> None:
    existing = db.execute(select(Topic)).first()
    if existing:
        return
    for category, items in TOPICS.items():
        for title, description in items:
            db.add(
                Topic(
                    category=category,
                    title=title,
                    description=description,
                    is_custom=False,
                )
            )
    db.commit()


def seed_sample_data(db: Session) -> None:
    if not get_settings().seed_sample_data:
        return
    existing = db.execute(select(Project)).first()
    if existing:
        return

    samples = [
        {
            "title": "Weekly numbers that keep cash healthy",
            "category": "business-tips",
            "topic": "The 3 numbers every small business should review weekly",
            "description": "A short, practical video for owners who want a simple weekly rhythm.",
            "status": "storyboard-approved",
            "step": "render",
        },
        {
            "title": "Purchase order to stock receipt",
            "category": "erp-walkthrough",
            "topic": "From purchase order to stock receipt in five clicks",
            "description": "A guided product walkthrough for the operations team.",
            "status": "script-ready",
            "step": "storyboard",
        },
        {
            "title": "Cash flow vs profit",
            "category": "financial-education",
            "topic": "Cash flow vs profit: the difference that sinks businesses",
            "description": "An explainer that helps founders avoid a common trap.",
            "status": "draft",
            "step": "category",
        },
    ]

    asset = _create_sample_asset(db)
    for index, sample in enumerate(samples):
        project = Project(
            title=sample["title"],
            category=sample["category"],
            topic=sample["topic"],
            description=sample["description"],
            status=sample["status"],
            current_step=sample["step"],
            progress={"seeded": True},
        )
        db.add(project)
        db.flush()
        paragraphs = _sample_paragraphs(sample["category"], sample["topic"])
        if index < 2:
            db.add(
                Script(
                    project_id=project.id,
                    content="\n\n".join(paragraphs),
                    approved=index == 0,
                    version=1,
                )
            )
        if index == 0:
            storyboard = Storyboard(project_id=project.id, approved=True)
            db.add(storyboard)
            db.flush()
            for scene_index, paragraph in enumerate(paragraphs):
                db.add(
                    Scene(
                        storyboard_id=storyboard.id,
                        order_index=scene_index,
                        title=f"Scene {scene_index + 1}",
                        narration=paragraph,
                        visual_prompt="Cinematic business b-roll with clean typography.",
                        duration_seconds=6,
                        transition="fade",
                        asset_id=asset.id if scene_index == 0 else None,
                    )
                )
        db.add(
            Activity(
                project_id=project.id,
                kind="seed",
                message=f"Sample project created for {sample['category'].replace('-', ' ')}.",
            )
        )
    db.commit()


def _sample_paragraphs(category: str, topic: str) -> list[str]:
    return [
        f"What if {topic.lower()} could be handled in one calm weekly routine?",
        f"Most teams overcomplicate {category.replace('-', ' ')}. They collect more data, "
        "but they do not decide what the data should change.",
        "Start with one number, one owner, and one action. Write the number down, review it "
        "at the same time every week, and name the next action before the meeting ends.",
        "When the routine is small enough to repeat, the improvement compounds. That is how "
        "a simple habit becomes an operating system.",
        "Open your dashboard today and pick the single number you will review this week.",
    ]


def _create_sample_asset(db: Session) -> Asset:
    settings = get_settings()
    target_dir = settings.storage_path / "assets"
    target_dir.mkdir(parents=True, exist_ok=True)
    name = f"sample-{uuid4().hex[:8]}.png"
    path = target_dir / name
    image = Image.new("RGB", (640, 360), (17, 24, 39))
    draw = ImageDraw.Draw(image)
    for y in range(360):
        ratio = y / 359
        color = (
            int(17 + (76 - 17) * ratio),
            int(24 + (29 - 24) * ratio),
            int(39 + (149 - 39) * ratio),
        )
        draw.line([(0, y), (640, y)], fill=color)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 30)
    except OSError:
        font = ImageFont.load_default()
    draw.text((36, 150), "Sample b-roll", font=font, fill=(248, 250, 252))
    draw.text((36, 200), "AI Film Studio", font=font, fill=(196, 181, 253))
    image.save(path)
    asset = Asset(
        filename=name,
        original_name="sample-b-roll.png",
        media_type="image",
        content_type="image/png",
        path=str(path),
        size_bytes=path.stat().st_size,
        tags=["sample", "b-roll"],
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def seed_all() -> None:
    db = SessionLocal()
    try:
        seed_topics(db)
        seed_sample_data(db)
    finally:
        db.close()
