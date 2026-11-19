import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Project, Scene, Storyboard
from app.schemas import (
    AIGenerateRequest,
    SceneRegenerateRequest,
    SceneReorderRequest,
    SceneUpdate,
    StoryboardGenerateRequest,
)
from app.services.ai.router import AIService
from app.services.film.common import category_label, mark_step, record_activity
from app.services.film.script_service import ScriptService, split_paragraphs

SCENE_LINE = re.compile(
    r"^\s*SCENE\s*(?P<number>\d+)\s*\|\s*(?P<title>[^|]*)\|\s*(?P<narration>[^|]*)\|"
    r"\s*(?P<visual>[^|]*)\|\s*(?P<duration>[\d.]+)\s*$",
    re.IGNORECASE,
)


class StoryboardService:
    def __init__(self, ai: AIService, scripts: ScriptService) -> None:
        self.ai = ai
        self.scripts = scripts

    def get(self, db: Session, project_id: str) -> Storyboard | None:
        return db.execute(
            select(Storyboard).where(Storyboard.project_id == project_id)
        ).scalar_one_or_none()

    async def generate(
        self, db: Session, project: Project, request: StoryboardGenerateRequest
    ) -> Storyboard:
        script = self.scripts.get(db, project.id)
        if script is None or not script.content.strip():
            raise ValueError("Generate a script before creating a storyboard.")
        prompt = (
            "Create a storyboard for a short business video.\n"
            f"Category: {category_label(project.category)}\n"
            f"Topic: {project.topic}\n"
            f"Visual style: {request.style or project.visual_style}\n"
            f"Target scene count: {request.scene_count}\n\n"
            "Script:\n"
            f"{script.content}\n\n"
            "Return exactly one line per scene in this format, with no extra text:\n"
            "SCENE <number> | <short title> | <narration sentence> | "
            "<specific visual description> | <duration in seconds>"
        )
        result = await self.ai.generate(
            db,
            AIGenerateRequest(
                prompt=prompt,
                task="storyboard",
                system="You are a video director. Return only storyboard scene lines.",
                project_id=project.id,
            ),
        )
        scenes = parse_scenes(result.text, request.scene_count, script.content)
        storyboard = self.get(db, project.id)
        if storyboard is None:
            storyboard = Storyboard(project_id=project.id)
            db.add(storyboard)
            db.flush()
        else:
            for scene in list(storyboard.scenes):
                db.delete(scene)
            db.flush()
            storyboard.approved = False
            db.add(storyboard)
        for index, item in enumerate(scenes):
            db.add(
                Scene(
                    storyboard_id=storyboard.id,
                    order_index=index,
                    title=item["title"],
                    narration=item["narration"],
                    visual_prompt=item["visual_prompt"],
                    duration_seconds=item["duration_seconds"],
                    transition=item.get("transition", "fade"),
                )
            )
        db.commit()
        db.refresh(storyboard)
        mark_step(
            db,
            project,
            status="storyboard-ready",
            step="storyboard",
            progress={"storyboard": True, "scenes": len(scenes)},
        )
        record_activity(
            db, project.id, "storyboard", f"Generated storyboard with {len(scenes)} scenes."
        )
        return storyboard

    def update_scene(
        self, db: Session, storyboard: Storyboard, scene_id: str, payload: SceneUpdate
    ) -> Scene:
        scene = db.get(Scene, scene_id)
        if scene is None or scene.storyboard_id != storyboard.id:
            raise ValueError("Scene not found on this storyboard.")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(scene, key, value)
        db.add(scene)
        db.commit()
        db.refresh(scene)
        record_activity(
            db, storyboard.project_id, "storyboard", f"Updated scene '{scene.title}'."
        )
        return scene

    def reorder(
        self, db: Session, storyboard: Storyboard, request: SceneReorderRequest
    ) -> Storyboard:
        owned = {scene.id: scene for scene in storyboard.scenes}
        for item in request.scenes:
            scene = owned.get(item.id)
            if scene is None:
                raise ValueError(f"Scene {item.id} does not belong to this storyboard.")
            scene.order_index = item.order_index
            db.add(scene)
        db.commit()
        db.refresh(storyboard)
        record_activity(db, storyboard.project_id, "storyboard", "Reordered scenes.")
        return storyboard

    async def regenerate_scene(
        self,
        db: Session,
        storyboard: Storyboard,
        scene_id: str,
        request: SceneRegenerateRequest,
    ) -> Scene:
        scene = db.get(Scene, scene_id)
        if scene is None or scene.storyboard_id != storyboard.id:
            raise ValueError("Scene not found on this storyboard.")
        project = db.get(Project, storyboard.project_id)
        prompt = (
            "Rewrite one storyboard scene. Return exactly one line in this format:\n"
            "SCENE <number> | <short title> | <narration sentence> | "
            "<specific visual description> | <duration in seconds>\n\n"
            f"Category: {category_label(project.category) if project else ''}\n"
            f"Current title: {scene.title}\n"
            f"Current narration: {scene.narration}\n"
            f"Current visual: {scene.visual_prompt}\n"
            f"Instruction: {request.instruction or 'Make it more concrete and visual.'}"
        )
        result = await self.ai.generate(
            db,
            AIGenerateRequest(
                prompt=prompt,
                task="storyboard",
                system="You are a video director. Return only one storyboard scene line.",
                project_id=storyboard.project_id,
            ),
        )
        parsed = parse_scenes(result.text, 1, scene.narration)
        updated = parsed[0]
        scene.title = updated["title"]
        scene.narration = updated["narration"]
        scene.visual_prompt = updated["visual_prompt"]
        scene.duration_seconds = updated["duration_seconds"]
        scene.status = "draft"
        db.add(scene)
        db.commit()
        db.refresh(scene)
        record_activity(
            db, storyboard.project_id, "storyboard", f"Regenerated scene '{scene.title}'."
        )
        return scene

    def approve(self, db: Session, project: Project, storyboard: Storyboard, approved: bool) -> Storyboard:
        storyboard.approved = approved
        db.add(storyboard)
        db.commit()
        db.refresh(storyboard)
        if approved:
            mark_step(
                db,
                project,
                status="storyboard-approved",
                step="render",
                progress={"storyboard_approved": True},
            )
        record_activity(
            db,
            project.id,
            "storyboard",
            "Storyboard approved." if approved else "Storyboard approval removed.",
        )
        return storyboard


def parse_scenes(text: str, expected: int, fallback_script: str) -> list[dict]:
    scenes: list[dict] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        match = SCENE_LINE.match(line.strip())
        if not match:
            continue
        scenes.append(
            {
                "title": match.group("title").strip()[:200],
                "narration": match.group("narration").strip(),
                "visual_prompt": match.group("visual").strip(),
                "duration_seconds": max(1.0, min(30.0, float(match.group("duration")))),
                "transition": "fade",
            }
        )
    if scenes:
        return scenes[: max(1, expected)] if len(scenes) > expected else scenes

    paragraphs = split_paragraphs(fallback_script) or [fallback_script.strip()]
    count = max(1, min(expected, len(paragraphs)))
    result = []
    for index in range(count):
        paragraph = paragraphs[index]
        result.append(
            {
                "title": f"Scene {index + 1}",
                "narration": paragraph[:400],
                "visual_prompt": "Cinematic business b-roll with clean typography.",
                "duration_seconds": 6.0,
                "transition": "fade",
            }
        )
    return result
