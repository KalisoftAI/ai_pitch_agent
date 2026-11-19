from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import (
    AIGenerateRequest,
    AIResult,
    ModelInfo,
    ModelSelectRequest,
    ProviderStatus,
    UsageSummary,
)
from app.services.ai.providers import ProviderError, ProviderUnavailable
from app.services.ai.router import AIService, get_ai_service

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/models", response_model=list[ModelInfo])
def list_models(
    db: Session = Depends(get_db),
    ai: AIService = Depends(get_ai_service),
) -> list[ModelInfo]:
    return ai.list_models(db)


@router.post("/models/select", response_model=list[ModelInfo])
def select_model(
    payload: ModelSelectRequest,
    db: Session = Depends(get_db),
    ai: AIService = Depends(get_ai_service),
) -> list[ModelInfo]:
    try:
        ai.select_model(db, payload.model_id)
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ai.list_models(db)


@router.post("/models/{model_id}/test", response_model=ProviderStatus)
async def test_model(
    model_id: str,
    db: Session = Depends(get_db),
    ai: AIService = Depends(get_ai_service),
) -> ProviderStatus:
    try:
        return await ai.test_model(db, model_id)
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/generate", response_model=AIResult)
async def generate(
    payload: AIGenerateRequest,
    db: Session = Depends(get_db),
    ai: AIService = Depends(get_ai_service),
) -> AIResult:
    try:
        return await ai.generate(db, payload)
    except ProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/usage", response_model=UsageSummary)
def usage(
    db: Session = Depends(get_db),
    ai: AIService = Depends(get_ai_service),
) -> UsageSummary:
    return ai.usage_summary(db)
