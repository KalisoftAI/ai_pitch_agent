"""Read-only catalog of human-reviewed sales prompts.

The catalog is a local snapshot of
``gs://kalika_enterprises/sales-metadata/weekly_prompts.json`` (version
2026-10-30.1). Nothing in this module writes to GCS, the database, or the
snapshot on disk.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import HTTPException

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "weekly_prompts.json"


@dataclass(frozen=True)
class Prompt:
    id: str
    task: str
    model: str
    tier: str
    json_mode: bool
    human_review: bool
    template: str
    variables: tuple[str, ...]
    sample_input: dict[str, Any]
    expected_output: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task": self.task,
            "model": self.model,
            "tier": self.tier,
            "json_mode": self.json_mode,
            "human_review": self.human_review,
            "template": self.template,
            "variables": list(self.variables),
            "sample_input": dict(self.sample_input),
            "expected_output": self.expected_output,
        }


def _to_prompt(item: dict[str, Any]) -> Prompt:
    return Prompt(
        id=str(item["id"]),
        task=str(item["task"]),
        model=str(item["model"]),
        tier=str(item["tier"]),
        json_mode=bool(item.get("json_mode", False)),
        human_review=bool(item.get("human_review", False)),
        template=str(item["template"]),
        variables=tuple(str(value) for value in item.get("variables", [])),
        sample_input=dict(item.get("sample_input") or {}),
        expected_output=item.get("expected_output"),
    )


def load_catalog(path: Path = CATALOG_PATH) -> tuple[Prompt, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return tuple(_to_prompt(item) for item in payload.get("prompts", []))


@lru_cache(maxsize=1)
def catalog() -> tuple[Prompt, ...]:
    return load_catalog()


@lru_cache(maxsize=1)
def catalog_meta() -> dict[str, Any]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return {
        "version": payload.get("version"),
        "source": "gs://kalika_enterprises/sales-metadata/weekly_prompts.json",
        "default_model": payload.get("models", {}).get("default"),
        "fallback_chain": list(payload.get("models", {}).get("fallback_chain", [])),
        "human_review_required": bool(payload.get("human_review_required", False)),
        "timezone": payload.get("schedule", {}).get("timezone"),
    }


def list_prompts(
    *,
    task: str | None = None,
    model: str | None = None,
    human_review: bool | None = None,
) -> list[Prompt]:
    prompts = list(catalog())
    if task:
        prompts = [prompt for prompt in prompts if prompt.task == task]
    if model:
        prompts = [prompt for prompt in prompts if prompt.model == model]
    if human_review is not None:
        prompts = [prompt for prompt in prompts if prompt.human_review is human_review]
    return prompts


def get_prompt(prompt_id: str) -> Prompt:
    wanted = prompt_id.strip().casefold()
    for prompt in catalog():
        if prompt.id.casefold() == wanted:
            return prompt
    raise HTTPException(status_code=404, detail=f"Prompt '{prompt_id}' not found")
