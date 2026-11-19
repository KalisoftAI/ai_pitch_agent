from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..governance.audit import log_event
from ..models import StudioRefinement
from ..security import get_current_user, require_admin
from ..services import GCSStorage

router = APIRouter(prefix="/v1/studio", tags=["studio"])

VERIFIED_FACTS = (
    "Kalika Enterprises (Est. 1990, Plot No M-59 MIDC Ahmednagar). "
    "Stretch Film 7-10 Tons/Day, 23-51 microns, up to 300% stretch, in-house recycling. "
    "ERP proof: 118 Quotations (Rs 2.17 Cr), 91 Sales Orders (Rs 98.69 L), 68,174 kg dispatched. "
    "Mobile barcode scan with 25.000 kg weight lock is approved for follow-up."
)
MODEL_COSTS = {
    "local_gemma_4b": 0.0,
    "gcp_gemma_27b": 0.0008,
    "gcp_flash_lite": 0.0004,
    "zero_llm_fast": 0.0,
}
ALLOWED_UPLOAD_EXTENSIONS = {
    ".json",
    ".txt",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".mp4",
    ".mov",
    ".webm",
}
DEFAULT_TEMPLATES = [
    {
        "name": "PAT-04 3D Factory",
        "path": "sales-crm/marketing-videos/Templates/pat-04-3d-factory.json",
    },
    {
        "name": "Stretch Film Hook",
        "path": "sales-crm/marketing-videos/Templates/stretch-film-hook.json",
    },
    {
        "name": "Barcode Traceability",
        "path": "sales-crm/marketing-videos/Templates/barcode-traceability.json",
    },
]


class StudioRefineRequest(BaseModel):
    prompt_text: str = Field(min_length=10, max_length=8000)
    model_choice: Literal["local_gemma_4b", "gcp_gemma_27b", "gcp_flash_lite", "zero_llm_fast"] = (
        "local_gemma_4b"
    )
    template_path: str = Field(default="sales-crm/marketing-videos/Templates/", max_length=512)
    aspect_ratio: Literal["16:9", "9:16"] = "16:9"


def _actor(user) -> str:
    return str(getattr(user, "email", "") or "")


def _crm_storage() -> GCSStorage:
    return GCSStorage(bucket_name=settings.GCS_BUCKET_CRM or "sales-crm")


def _append_jsonl(storage: GCSStorage, blob_name: str, payload: dict) -> str:
    if not storage.available or storage._client is None:
        return ""
    try:
        blob = storage._client.bucket(storage.bucket_name).blob(blob_name)
        existing = (
            blob.download_as_bytes().decode("utf-8", errors="replace") if blob.exists() else ""
        )
        line = json.dumps(payload, ensure_ascii=False, default=str)
        blob.upload_from_string(f"{existing}{line}\n", content_type="application/x-ndjson")
        return f"gs://{storage.bucket_name}/{blob_name}"
    except Exception:  # noqa: BLE001 - studio output must not break the main app
        return ""


def _fallback_refine(prompt_text: str) -> str:
    return (
        f"{prompt_text.strip()}\n\n"
        f"Verified KPI guardrails: {VERIFIED_FACTS}\n"
        "Production-safe direction: 25s high-contrast industrial motion-graphics, 0-2.5s hook on "
        "transit damage, show XHD extrusion, mobile barcode scan + 25.000 kg weight lock, "
        "then CTA Call/WhatsApp +91 96659 34999."
    )


def _refine(prompt_text: str, model_choice: str) -> tuple[str, str, float]:
    instruction = (
        "Refine this manufacturing video/sales prompt using ONLY these verified facts. "
        "Do not invent numbers or claims.\n"
        f"Verified facts: {VERIFIED_FACTS}\n"
        f"Input: {prompt_text}\n"
        "Refined Output:"
    )
    if model_choice == "local_gemma_4b":
        try:
            response = httpx.post(
                f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate",
                json={"model": "gemma3:4b", "prompt": instruction, "stream": False},
                timeout=5.0,
            )
            if response.status_code == 200:
                refined = str(response.json().get("response", "")).strip()
                if refined:
                    return refined, "local_ollama", 0.0
        except Exception:  # noqa: BLE001 - local Ollama is optional; deterministic output is safe
            pass
    return _fallback_refine(prompt_text), "deterministic_fallback", MODEL_COSTS[model_choice]


@router.get("/templates")
def list_studio_templates(user=Depends(get_current_user)):
    storage = _crm_storage()
    remote = storage.list_blobs(
        prefix="marketing-videos/Templates/",
        suffixes=(".json", ".mp4", ".mov", ".txt"),
    )
    items = [
        {"name": Path(item["name"]).name, "path": item["name"], "size": item.get("size", 0)}
        for item in remote
    ]
    return {"items": items or DEFAULT_TEMPLATES, "source": "gcs" if items else "defaults"}


@router.post("/refine-and-generate")
@router.post("/refine-prompt")
def refine_and_generate(
    payload: StudioRefineRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    refined_prompt, source_mode, cost_usd = _refine(payload.prompt_text, payload.model_choice)
    blob_name = (
        f"{settings.GCS_PATH_SALES_APP_DATA.strip('/')}/studio_refinements/{date.today()}.jsonl"
    )
    record = {
        "refined_at": datetime.now(timezone.utc).isoformat(),
        "prompt_text": payload.prompt_text,
        "refined_prompt": refined_prompt,
        "model_choice": payload.model_choice,
        "template_path": payload.template_path,
        "aspect_ratio": payload.aspect_ratio,
        "source_mode": source_mode,
        "cost_usd": cost_usd,
        "created_by": _actor(user),
    }
    gcs_uri = _append_jsonl(_crm_storage(), blob_name, record)
    row = StudioRefinement(
        user_id=int(getattr(user, "id", 0) or 0),
        prompt_text=payload.prompt_text,
        refined_prompt=refined_prompt,
        model_choice=payload.model_choice,
        template_path=payload.template_path,
        aspect_ratio=payload.aspect_ratio,
        cost_usd=cost_usd,
        source_mode=source_mode,
        gcs_uri=gcs_uri,
        created_by=_actor(user),
    )
    db.add(row)
    log_event(
        db,
        action="studio_prompt_refined",
        actor_user_id=row.user_id,
        resource_type="studio_refinement",
        resource_id=str(row.id or "pending"),
        detail={"model_choice": payload.model_choice, "source_mode": source_mode},
    )
    db.commit()
    db.refresh(row)
    return {
        "status": "refined",
        "id": row.id,
        "model": payload.model_choice,
        "cost_usd": cost_usd,
        "source_mode": source_mode,
        "refined_prompt": refined_prompt,
        "template_path": payload.template_path,
        "aspect_ratio": payload.aspect_ratio,
        "gcs_uri": gcs_uri or None,
    }


@router.get("/refinements")
def list_refinements(
    limit: int = 30,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = db.query(StudioRefinement)
    if getattr(user, "role", "") != "admin":
        query = query.filter(StudioRefinement.user_id == int(getattr(user, "id", 0) or 0))
    rows = query.order_by(StudioRefinement.created_at.desc()).limit(max(1, min(limit, 100))).all()
    return {
        "items": [
            {
                "id": row.id,
                "model_choice": row.model_choice,
                "source_mode": row.source_mode,
                "cost_usd": row.cost_usd,
                "aspect_ratio": row.aspect_ratio,
                "refined_prompt": row.refined_prompt,
                "gcs_uri": row.gcs_uri,
                "created_at": str(row.created_at),
            }
            for row in rows
        ]
    }


@router.post("/upload")
def upload_studio_asset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    original = Path(file.filename or "").name
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", original).strip("._")
    extension = Path(safe_name).suffix.lower()
    if not safe_name or extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported studio asset type")
    max_bytes = 20 * 1024 * 1024
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail="Studio asset exceeds 20 MB limit")
    blob_name = f"assets/uploads/{date.today()}/{uuid.uuid4().hex}_{safe_name}"
    storage = _crm_storage()
    if not storage.upload_bytes(blob_name, data, file.content_type or "application/octet-stream"):
        raise HTTPException(status_code=503, detail="Studio asset storage unavailable")
    log_event(
        db,
        action="studio_asset_uploaded",
        actor_user_id=int(getattr(user, "id", 0) or 0),
        resource_type="studio_asset",
        resource_id=blob_name,
        detail={"size": len(data), "extension": extension},
    )
    db.commit()
    return {
        "status": "uploaded",
        "path": blob_name,
        "gcs_uri": f"gs://{storage.bucket_name}/{blob_name}",
        "size": len(data),
    }
