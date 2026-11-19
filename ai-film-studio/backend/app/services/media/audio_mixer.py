from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

from app.services.media import audio_sfx as sfx


class AudioMixError(RuntimeError):
    pass


class AudioMixer:
    """Build a deterministic sound bed and mux it into the silent motion video."""

    def __init__(self, sample_rate: int = 48000) -> None:
        self.sample_rate = sample_rate

    def build(self, data: dict, output: Path) -> Path:
        duration = max(1.0, float(data.get("duration") or 1.0))
        frames = int(round(duration * self.sample_rate))
        mix = np.zeros((frames, 2), dtype=np.float32)
        scenes = data.get("scenes") or []
        if not scenes:
            return output

        ambient = sfx.rumble(min(duration, 8.0), 0.08)
        self._add(mix, ambient, 0.0, 0.55)

        for index, scene in enumerate(scenes):
            start = float(scene.get("start") or 0.0)
            pattern = str(scene.get("pattern") or scene.get("layout") or "split")
            accent = str(scene.get("accent") or "#ff4d2e")
            pitch = 0.92 + (index % 5) * 0.035
            if pattern in {"data", "infographic"}:
                cue = sfx.pop(0.9) * 0.7
            elif pattern in {"typographic", "quote"}:
                cue = sfx.click(pitch, 0.8)
            elif pattern == "isometric":
                cue = sfx.thump(0.7, 62)
            elif pattern in {"documentary", "story"}:
                cue = sfx.creak(0.6)
            else:
                cue = sfx.whoosh(0.32, 0.7)
            self._add(mix, cue, start, 0.7)
            if scene.get("stat") and start + 0.7 < duration:
                self._add(mix, sfx.ding(0.55), start + 0.7, 0.65)
            if scene.get("transition") in {"zoom", "glitch", "whip"} and start > 0:
                self._add(mix, sfx.whoosh(0.18, 0.55), max(0.0, start - 0.12), 0.45)

        self._add(mix, sfx.thump(0.8, 54), max(0.0, duration - 1.05), 0.8)
        self._add(mix, sfx.ding(0.35), max(0.0, duration - 0.95), 0.35)
        self._finish(mix)
        output.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output), mix, self.sample_rate, subtype="PCM_16")
        return output

    def _add(self, mix: np.ndarray, cue: np.ndarray, at: float, gain: float) -> None:
        if cue is None or not len(cue):
            return
        sfx.add(mix, np.asarray(cue, dtype=np.float32), at, gain)

    def _finish(self, mix: np.ndarray) -> None:
        if not len(mix):
            return
        peak = float(np.abs(mix).max())
        if peak > 0:
            mix *= min(0.82 / peak, 8.0)
        fade = min(int(0.12 * self.sample_rate), len(mix) // 2)
        if fade > 0:
            mix[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)[:, None]
            mix[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)[:, None]
        mix[:] = np.tanh(mix * 1.1) / math.tanh(1.1)

    def mux(self, ffmpeg: str, video: Path, audio: Path, output: Path) -> Path:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.unlink(missing_ok=True)
        command = [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-i",
            str(audio),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-af",
            "loudnorm=I=-14:TP=-1.5:LRA=11",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output),
        ]
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=1800, check=False
        )
        if result.returncode != 0 or not output.exists() or output.stat().st_size == 0:
            raise AudioMixError(
                f"Audio mux failed with exit {result.returncode}: {result.stderr[-800:]}"
            )
        return output
