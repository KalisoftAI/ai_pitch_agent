from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Project, Script
from app.schemas import AIGenerateRequest, ParagraphRegenerateRequest, ScriptGenerateRequest
from app.services.ai.router import AIService
from app.services.film.common import category_label, mark_step, record_activity


class ScriptService:
    def __init__(self, ai: AIService) -> None:
        self.ai = ai

    def get(self, db: Session, project_id: str) -> Script | None:
        return db.execute(
            select(Script).where(Script.project_id == project_id)
        ).scalar_one_or_none()

    async def generate(
        self, db: Session, project: Project, request: ScriptGenerateRequest
    ) -> Script:
        prompt = (
            "Write a short-form video script for a business audience.\n"
            f"Category: {category_label(project.category)}\n"
            f"Topic: {project.topic}\n"
            f"Target duration: {project.duration_seconds} seconds\n"
            f"Tone: {request.tone}\n"
            f"Audience: {request.audience}\n"
            f"Extra instructions: {request.instructions or 'none'}\n\n"
            "Return 4 to 6 short paragraphs. Each paragraph is one beat of the video. "
            "Open with a hook, explain the idea with one concrete example, and close with "
            "a clear call to action. Do not include scene headings or markdown fences."
        )
        result = await self.ai.generate(
            db,
            AIGenerateRequest(
                prompt=prompt,
                task="script",
                system="You are a senior short-form video scriptwriter for business education.",
                project_id=project.id,
            ),
        )
        script = self.get(db, project.id)
        if script is None:
            script = Script(project_id=project.id, content=result.text, version=1)
            db.add(script)
        else:
            script.content = result.text
            script.version += 1
            script.approved = False
            db.add(script)
        db.commit()
        db.refresh(script)
        mark_step(
            db,
            project,
            status="script-ready",
            step="script",
            progress={"script": True, "script_version": script.version},
        )
        record_activity(db, project.id, "script", f"Generated script v{script.version}.")
        return script

    def update(self, db: Session, project: Project, content: str) -> Script:
        script = self.get(db, project.id)
        if script is None:
            script = Script(project_id=project.id, content=content, version=1)
            db.add(script)
        else:
            script.content = content
            script.version += 1
            script.approved = False
            db.add(script)
        db.commit()
        db.refresh(script)
        record_activity(db, project.id, "script", f"Edited script to v{script.version}.")
        return script

    async def regenerate_paragraph(
        self,
        db: Session,
        project: Project,
        request: ParagraphRegenerateRequest,
    ) -> Script:
        script = self.get(db, project.id)
        if script is None or not script.content.strip():
            raise ValueError("Generate or write a script before regenerating a paragraph.")
        paragraphs = split_paragraphs(script.content)
        if request.paragraph_index >= len(paragraphs):
            raise ValueError(
                f"Paragraph {request.paragraph_index} does not exist; script has "
                f"{len(paragraphs)} paragraphs."
            )
        target = paragraphs[request.paragraph_index]
        prompt = (
            "Rewrite only the paragraph below. Keep the meaning and approximate length. "
            "Return only the rewritten paragraph, with no preamble or quotes.\n\n"
            f"Category: {category_label(project.category)}\n"
            f"Topic: {project.topic}\n"
            f"Instruction: {request.instruction or 'Make it sharper and more concrete.'}\n\n"
            f"Paragraph:\n{target}"
        )
        result = await self.ai.generate(
            db,
            AIGenerateRequest(
                prompt=prompt,
                task="cleanup",
                system="You are a precise editor. Return only the rewritten paragraph.",
                project_id=project.id,
            ),
        )
        paragraphs[request.paragraph_index] = result.text.strip()
        script.content = "\n\n".join(paragraphs)
        script.version += 1
        script.approved = False
        db.add(script)
        db.commit()
        db.refresh(script)
        record_activity(
            db,
            project.id,
            "script",
            f"Regenerated paragraph {request.paragraph_index + 1} (v{script.version}).",
        )
        return script

    def approve(self, db: Session, project: Project, approved: bool) -> Script:
        script = self.get(db, project.id)
        if script is None:
            raise ValueError("No script exists for this project.")
        script.approved = approved
        db.add(script)
        db.commit()
        db.refresh(script)
        if approved:
            mark_step(
                db,
                project,
                status="script-approved",
                step="storyboard",
                progress={"script_approved": True},
            )
        record_activity(
            db,
            project.id,
            "script",
            "Script approved." if approved else "Script approval removed.",
        )
        return script


def split_paragraphs(content: str) -> list[str]:
    parts = [part.strip() for part in content.replace("\r\n", "\n").split("\n\n")]
    return [part for part in parts if part]
