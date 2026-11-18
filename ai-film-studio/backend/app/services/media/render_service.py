from __future__ import annotations

import shutil
import subprocess
import textwrap
import threading
import time
import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.models import Project, RenderJob, Scene, Storyboard
from app.services.film.common import record_activity
from app.services.media.motion_renderer import (
    MotionRenderCancelled,
    MotionRenderError,
    MotionRenderer,
)
from app.services.storage import GCSStorage, StorageError, StorageUnavailable


class RenderError(RuntimeError):
    pass


class RenderService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def create_job(self, db: Session, project: Project, options: dict) -> RenderJob:
        storyboard = db.execute(
            select(Storyboard).where(Storyboard.project_id == project.id)
        ).scalar_one_or_none()
        if storyboard is None or not storyboard.scenes:
            raise RenderError("Create and approve a storyboard before rendering.")
        if not storyboard.approved:
            raise RenderError("Approve the storyboard before rendering.")
        active = db.execute(
            select(RenderJob).where(
                RenderJob.project_id == project.id,
                RenderJob.status.in_(["queued", "running"]),
            )
        ).scalar_one_or_none()
        if active is not None:
            raise RenderError(f"Render job {active.id} is already in progress.")
        options = dict(options or {})
        options.setdefault(
            "engine", "motion" if self.settings.render_mode == "motion" else "cards"
        )
        job = RenderJob(project_id=project.id, options=options, stage="queued")
        db.add(job)
        db.commit()
        db.refresh(job)
        record_activity(db, project.id, "render", f"Queued render job {job.id[:8]}.")
        thread = threading.Thread(target=self._run, args=(job.id,), daemon=True)
        thread.start()
        return job

    def cancel(self, db: Session, job: RenderJob) -> RenderJob:
        if job.status in {"queued", "running"}:
            job.status = "cancelled"
            job.stage = "cancelled"
            job.finished_at = datetime.now(UTC)
            self._append_log(job, "Cancellation requested by user.")
            db.add(job)
            db.commit()
            db.refresh(job)
        return job

    def publish(self, db: Session, job: RenderJob) -> dict:
        project = db.get(Project, job.project_id)
        if project is None:
            raise StorageError("Project not found for this render.")
        if not job.preview_path and not job.export_path:
            raise StorageError("Render has no preview or export file to publish.")
        storage = GCSStorage(self.settings)
        result = storage.publish_render(
            job_id=job.id,
            project_id=job.project_id,
            preview=Path(job.preview_path) if job.preview_path else None,
            export=Path(job.export_path) if job.export_path else None,
            metadata={
                "title": project.title,
                "category": project.category,
                "topic": project.topic,
                "style": project.visual_style,
                "duration_seconds": project.duration_seconds,
                "aspect_ratio": project.aspect_ratio,
                "engine": job.options.get("engine", "motion"),
                "quality": job.options.get("quality", "both"),
            },
        )
        job.options = {**(job.options or {}), "storage": result}
        self._append_log(
            job,
            f"Published render to {result.get('folder', result.get('bucket', 'GCS'))}.",
        )
        db.add(job)
        db.commit()
        record_activity(db, project.id, "storage", f"Published render {job.id[:8]} to GCS.")
        return result

    def _run(self, job_id: str) -> None:
        db = SessionLocal()
        try:
            job = db.get(RenderJob, job_id)
            if job is None:
                return
            project = db.get(Project, job.project_id)
            storyboard = db.execute(
                select(Storyboard).where(Storyboard.project_id == job.project_id)
            ).scalar_one_or_none()
            if project is None or storyboard is None:
                self._fail(db, job, "Project or storyboard disappeared.")
                return
            scenes = sorted(storyboard.scenes, key=lambda scene: scene.order_index)
            if not scenes:
                self._fail(db, job, "Storyboard has no scenes.")
                return

            job.status = "running"
            job.stage = "preparing"
            job.progress = 5
            job.started_at = datetime.now(UTC)
            self._append_log(job, f"Render started for '{project.title}'.")
            db.add(job)
            db.commit()

            if job.status == "cancelled":
                return

            if self.settings.render_mode == "simulated":
                self._simulate(db, job)
                return

            ffmpeg = shutil.which(self.settings.ffmpeg_bin)
            if not ffmpeg:
                self._fail(
                    db,
                    job,
                    "FFmpeg was not found. Install FFmpeg or set FFMPEG_BIN, "
                    "or use RENDER_MODE=simulated.",
                )
                return

            quality = job.options.get("quality", "both")
            engine = job.options.get("engine") or (
                "motion" if self.settings.render_mode == "motion" else "cards"
            )
            if engine == "motion":
                motion = MotionRenderer(self.settings)
                ready, reason = motion.available()
                if not ready:
                    self._append_log(job, f"Motion renderer unavailable: {reason}")
                    if not self.settings.motion_fallback_to_cards:
                        self._fail(db, job, reason)
                        return
                    self._append_log(job, "Falling back to the fast card renderer.")
                    engine = "cards"
                else:
                    self._append_log(job, f"Motion engine: {reason}")
                    try:
                        self._render_motion(
                            db, job, project, scenes, ffmpeg, quality
                        )
                        return
                    except MotionRenderCancelled:
                        return
                    except MotionRenderError as exc:
                        self._append_log(job, f"Motion render failed: {exc}")
                        if not self.settings.motion_fallback_to_cards:
                            self._fail(db, job, str(exc))
                            return
                        self._append_log(job, "Falling back to the fast card renderer.")
                        db.refresh(job)
                        if job.status == "cancelled":
                            return
                        job.status = "running"
                        job.stage = "preparing scenes"
                        db.add(job)
                        db.commit()

            job.stage = "preparing scenes"
            job.progress = 15
            self._append_log(job, "Generating scene frames.")
            db.add(job)
            db.commit()

            temp_dir = self.settings.storage_path / "temp" / job.id
            temp_dir.mkdir(parents=True, exist_ok=True)
            frames = self._render_frames(db, project, scenes, temp_dir, job)
            if not frames:
                self._fail(db, job, "No frames were generated.")
                return

            job.stage = "encoding"
            job.progress = 55
            self._append_log(job, "Encoding video with FFmpeg.")
            db.add(job)
            db.commit()

            preview_path = None
            export_path = None
            if quality in {"preview", "both"}:
                preview_path = self._encode(
                    ffmpeg,
                    frames,
                    scenes,
                    self.settings.storage_path / "previews" / f"{job.id}.mp4",
                    self.settings.preview_width,
                    self.settings.preview_height,
                )
                job.preview_path = str(preview_path)
                job.progress = 75
                self._append_log(job, "Preview encoded.")
                db.add(job)
                db.commit()
            if quality in {"export", "both"}:
                export_path = self._encode(
                    ffmpeg,
                    frames,
                    scenes,
                    self.settings.storage_path / "exports" / f"{job.id}.mp4",
                    self.settings.export_width,
                    self.settings.export_height,
                )
                job.export_path = str(export_path)
                job.progress = 90
                self._append_log(job, "Export encoded.")
                db.add(job)
                db.commit()

            self._complete(db, job, project)
        except MotionRenderCancelled:
            return
        except Exception as exc:  # pragma: no cover - defensive worker boundary
            job = db.get(RenderJob, job_id)
            if job is not None:
                self._fail(db, job, str(exc))
        finally:
            db.close()

    def _render_motion(
        self,
        db: Session,
        job: RenderJob,
        project: Project,
        scenes: list[Scene],
        ffmpeg: str,
        quality: str,
    ) -> None:
        motion = MotionRenderer(self.settings)
        preview_size = self._motion_size(project, preview=True)
        export_size = self._motion_size(project, preview=False)
        preview_path = self.settings.storage_path / "previews" / f"{job.id}.mp4"
        export_path = self.settings.storage_path / "exports" / f"{job.id}.mp4"

        def update(progress: int, stage: str, message: str | None) -> None:
            db.refresh(job)
            if job.status == "cancelled":
                raise MotionRenderCancelled("Render cancelled.")
            job.status = "running"
            job.progress = max(job.progress or 0, min(98, progress))
            job.stage = stage
            if message:
                self._append_log(job, message)
            db.add(job)
            db.commit()

        def cancelled() -> bool:
            check = SessionLocal()
            try:
                current = check.get(RenderJob, job.id)
                return current is None or current.status == "cancelled"
            except Exception:  # pragma: no cover - database hiccup
                return False
            finally:
                check.close()

        if quality == "preview":
            motion.render(
                db,
                project,
                scenes,
                job_id=job.id,
                output=preview_path,
                width=preview_size[0],
                height=preview_size[1],
                fps=self.settings.motion_fps,
                workers=self.settings.motion_workers,
                include_captions=bool(job.options.get("include_captions", True)),
                options=job.options,
                progress=update,
                should_cancel=cancelled,
            )
            db.refresh(job)
            job.preview_path = str(preview_path)
            db.add(job)
            db.commit()
        else:
            motion.render(
                db,
                project,
                scenes,
                job_id=job.id,
                output=export_path,
                width=export_size[0],
                height=export_size[1],
                fps=self.settings.motion_fps,
                workers=self.settings.motion_workers,
                include_captions=bool(job.options.get("include_captions", True)),
                options=job.options,
                progress=update,
                should_cancel=cancelled,
            )
            db.refresh(job)
            job.export_path = str(export_path)
            db.add(job)
            db.commit()
            if quality == "both":
                update(94, "encoding preview", "Downscaling the motion export for preview.")
                self._downscale(ffmpeg, export_path, preview_path, preview_size)
                db.refresh(job)
                job.preview_path = str(preview_path)
                db.add(job)
                db.commit()

        self._complete(db, job, project)

    def _motion_size(self, project: Project, *, preview: bool) -> tuple[int, int]:
        ratio = (project.aspect_ratio or "16:9").replace(" ", "")
        if ratio == "16:9":
            if preview:
                return self.settings.preview_width, self.settings.preview_height
            return self.settings.export_width, self.settings.export_height
        long = self.settings.preview_width if preview else self.settings.export_width
        if ratio == "9:16":
            width, height = long * 9 / 16, long
        elif ratio == "1:1":
            width, height = long, long
        elif ratio == "4:5":
            width, height = long * 4 / 5, long
        else:
            width, height = long, long * 9 / 16
        return self._even(width), self._even(height)

    @staticmethod
    def _even(value: float) -> int:
        return max(16, int(round(value / 2)) * 2)

    def _downscale(
        self, ffmpeg: str, source: Path, output: Path, size: tuple[int, int]
    ) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.unlink(missing_ok=True)
        width, height = size
        command = [
            ffmpeg,
            "-y",
            "-i",
            str(source),
            "-vf",
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
            "-c:a",
            "copy",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "24",
            "-movflags",
            "+faststart",
            str(output),
        ]
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=600, check=False
        )
        if result.returncode != 0:
            raise RenderError(
                f"FFmpeg preview downscale failed with exit {result.returncode}: "
                f"{result.stderr[-800:]}"
            )

    def _complete(self, db: Session, job: RenderJob, project: Project) -> None:
        db.refresh(job)
        job.status = "completed"
        job.stage = "completed"
        job.progress = 100
        job.finished_at = datetime.now(UTC)
        self._validate_outputs(job)
        self._append_log(job, "Render completed successfully.")
        db.add(job)
        project.status = "rendered"
        project.current_step = "insights"
        db.add(project)
        db.commit()
        record_activity(db, project.id, "render", f"Render job {job.id[:8]} completed.")
        if self.settings.gcs_enabled and self.settings.gcs_auto_publish:
            try:
                self.publish(db, job)
            except (StorageError, StorageUnavailable) as exc:
                self._append_log(job, f"Cloud publish skipped: {exc}")
                db.add(job)
                db.commit()

    def _validate_outputs(self, job: RenderJob) -> None:
        probe = shutil.which("ffprobe")
        if not probe:
            return
        checks: dict[str, dict] = {}
        for kind, raw_path in (("preview", job.preview_path), ("export", job.export_path)):
            if not raw_path:
                continue
            path = Path(raw_path)
            if not path.exists() or path.stat().st_size == 0:
                checks[kind] = {"ok": False, "error": "missing or empty"}
                continue
            command = [
                probe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,r_frame_rate,duration",
                "-of",
                "json",
                str(path),
            ]
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=30, check=False
            )
            if result.returncode != 0:
                checks[kind] = {"ok": False, "error": result.stderr[-300:]}
                continue
            try:
                stream = json.loads(result.stdout).get("streams", [{}])[0]
            except (json.JSONDecodeError, IndexError):
                checks[kind] = {"ok": False, "error": "could not parse ffprobe output"}
                continue
            checks[kind] = {
                "ok": bool(stream.get("width") and stream.get("height")),
                "width": stream.get("width"),
                "height": stream.get("height"),
                "fps": stream.get("r_frame_rate"),
                "duration": stream.get("duration"),
                "bytes": path.stat().st_size,
            }
        if checks:
            job.options = {**(job.options or {}), "quality_check": checks}
            if any(not item.get("ok", False) for item in checks.values()):
                self._append_log(job, f"Output validation warning: {checks}")

    def _simulate(self, db: Session, job: RenderJob) -> None:
        stages = [
            (20, "preparing scenes"),
            (45, "rendering frames"),
            (70, "encoding"),
            (90, "finalizing"),
        ]
        for progress, stage in stages:
            time.sleep(0.35)
            job = db.get(RenderJob, job.id)
            if job is None or job.status == "cancelled":
                return
            job.progress = progress
            job.stage = stage
            self._append_log(job, f"Simulated stage: {stage}.")
            db.add(job)
            db.commit()
        job = db.get(RenderJob, job.id)
        if job is None or job.status == "cancelled":
            return
        job.status = "completed"
        job.stage = "completed"
        job.progress = 100
        job.finished_at = datetime.now(UTC)
        self._append_log(job, "Simulated render completed. Set RENDER_MODE=ffmpeg for MP4 output.")
        db.add(job)
        project = db.get(Project, job.project_id)
        if project is not None:
            project.status = "rendered"
            project.current_step = "insights"
            db.add(project)
        db.commit()
        record_activity(db, job.project_id, "render", f"Render job {job.id[:8]} completed.")

    def _render_frames(
        self,
        db: Session,
        project: Project,
        scenes: list[Scene],
        temp_dir: Path,
        job: RenderJob,
    ) -> list[Path]:
        frames: list[Path] = []
        width, height = self.settings.preview_width, self.settings.preview_height
        for index, scene in enumerate(scenes):
            db.refresh(job)
            if job.status == "cancelled":
                return frames
            frame_path = temp_dir / f"scene-{index:03d}.png"
            self._draw_frame(project, scene, index, width, height, frame_path)
            frames.append(frame_path)
            job.progress = 15 + int(((index + 1) / len(scenes)) * 35)
            job.stage = f"rendering frame {index + 1}/{len(scenes)}"
            self._append_log(job, f"Rendered frame {index + 1}/{len(scenes)}.")
            db.add(job)
            db.commit()
        return frames

    def _draw_frame(
        self,
        project: Project,
        scene: Scene,
        index: int,
        width: int,
        height: int,
        path: Path,
    ) -> None:
        palettes = [
            ((13, 17, 28), (45, 27, 105)),
            ((10, 24, 32), (20, 78, 86)),
            ((24, 14, 36), (88, 28, 135)),
            ((9, 20, 40), (30, 64, 175)),
            ((20, 20, 24), (80, 45, 120)),
            ((12, 30, 28), (16, 94, 74)),
        ]
        top, bottom = palettes[index % len(palettes)]
        image = Image.new("RGB", (width, height), top)
        draw = ImageDraw.Draw(image)
        for y in range(height):
            ratio = y / max(1, height - 1)
            color = tuple(int(top[channel] + (bottom[channel] - top[channel]) * ratio) for channel in range(3))
            draw.line([(0, y), (width, y)], fill=color)

        draw.rectangle([(32, 30), (width - 32, 38)], fill=(139, 92, 246))
        title_font = self._font(26)
        body_font = self._font(16)
        small_font = self._font(12)

        draw.text((40, 54), project.topic[:70], font=small_font, fill=(196, 181, 253))
        draw.text((40, 88), scene.title[:60], font=title_font, fill=(248, 250, 252))
        body = textwrap.fill(scene.narration, width=64)
        draw.multiline_text((40, 140), body[:420], font=body_font, fill=(226, 232, 240), spacing=6)
        draw.text(
            (40, height - 50),
            f"{index + 1:02d} / {scene.duration_seconds:.0f}s  ·  {project.category.replace('-', ' ').title()}",
            font=small_font,
            fill=(148, 163, 184),
        )
        draw.ellipse([(width - 120, height - 96), (width - 60, height - 36)], outline=(167, 139, 250), width=3)
        draw.text((width - 110, height - 78), f"{index + 1}", font=body_font, fill=(233, 213, 255))
        image.save(path)

    def _font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidates = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for candidate in candidates:
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
        try:
            return ImageFont.load_default(size=size)
        except TypeError:  # pragma: no cover - old Pillow
            return ImageFont.load_default()

    def _encode(
        self,
        ffmpeg: str,
        frames: list[Path],
        scenes: list[Scene],
        output: Path,
        width: int,
        height: int,
    ) -> Path:
        output.parent.mkdir(parents=True, exist_ok=True)
        concat_file = frames[0].parent / f"concat-{output.stem}.txt"
        lines: list[str] = []
        for frame, scene in zip(frames, scenes, strict=False):
            lines.append(f"file '{frame.as_posix()}'")
            lines.append(f"duration {max(1.0, scene.duration_seconds):.3f}")
        if frames:
            lines.append(f"file '{frames[-1].as_posix()}'")
        concat_file.write_text("\n".join(lines), encoding="utf-8")
        command = [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-vf",
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "24",
            "-movflags",
            "+faststart",
            str(output),
        ]
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=600, check=False
        )
        if result.returncode != 0:
            raise RenderError(
                f"FFmpeg failed with exit {result.returncode}: {result.stderr[-800:]}"
            )
        return output

    def _append_log(self, job: RenderJob, message: str) -> None:
        stamp = datetime.now(UTC).strftime("%H:%M:%S")
        existing = job.logs or ""
        job.logs = f"{existing}\n[{stamp}] {message}".strip()

    def _fail(self, db: Session, job: RenderJob, message: str) -> None:
        job.status = "failed"
        job.stage = "failed"
        job.error = message
        job.finished_at = datetime.now(UTC)
        self._append_log(job, f"ERROR: {message}")
        db.add(job)
        db.commit()


@lru_cache
def get_render_service() -> RenderService:
    return RenderService()
