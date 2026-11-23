"""Read-only JSON API for the sales prompt catalog.

Only GET routes are exposed. Templates, models and review flags are served
exactly as published in the reviewed GCS snapshot; no execution or sending is
triggered from this router.
"""

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.sales_prompt_catalog import (
    Prompt,
    catalog,
    catalog_meta,
    get_prompt,
    list_prompts,
)

router = APIRouter(tags=["sales-prompts"])


class PromptResponse(BaseModel):
    id: str
    task: str
    model: str
    tier: str
    json_mode: bool
    human_review: bool
    template: str
    variables: list[str]
    sample_input: dict[str, Any]
    expected_output: Any


class CatalogResponse(BaseModel):
    meta: dict[str, Any]
    prompts: list[PromptResponse]


def _as_response(prompt: Prompt) -> PromptResponse:
    return PromptResponse(**prompt.to_dict())


@router.get("/sales-prompts", response_model=CatalogResponse)
def list_sales_prompts(
    task: str | None = Query(default=None, description="Filter by exact task name"),
    model: str | None = Query(default=None, description="Filter by exact model id"),
    human_review: bool | None = Query(
        default=None, description="Filter by human-review requirement"
    ),
) -> CatalogResponse:
    prompts = list_prompts(task=task, model=model, human_review=human_review)
    meta = catalog_meta()
    meta["total"] = len(prompts)
    meta["catalog_size"] = len(catalog())
    return CatalogResponse(meta=meta, prompts=[_as_response(prompt) for prompt in prompts])


@router.get("/sales-prompts/{prompt_id}", response_model=PromptResponse)
def get_sales_prompt(prompt_id: str) -> PromptResponse:
    return _as_response(get_prompt(prompt_id))
