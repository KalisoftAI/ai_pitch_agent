from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import AIUsage, Setting
from app.schemas import AIResult, AIGenerateRequest, ModelInfo, ProviderStatus, UsageBucket, UsageSummary
from app.services.ai.providers import (
    AIProvider,
    ClaudeProvider,
    ConnectionResult,
    GemmaProvider,
    GeminiProvider,
    MockProvider,
    ProviderError,
    ProviderUnavailable,
    ProviderResponse,
)


@dataclass(frozen=True)
class ModelSpec:
    id: str
    provider: str
    label: str
    task: str
    local: bool
    description: str

    def resolve_name(self, settings: Settings) -> str:
        mapping = {
            "local-gemma-4-12b": settings.gemma_model_id,
            "gemini-flash-lite": settings.gemini_flash_lite_model,
            "gemini-flash": settings.gemini_flash_model,
            "gemini-pro": settings.gemini_pro_model,
            "claude-opus": settings.claude_opus_model,
            "mock-ai": "mock-ai",
        }
        return mapping[self.id]


MODEL_SPECS: list[ModelSpec] = [
    ModelSpec(
        "local-gemma-4-12b",
        "gemma",
        "Gemma 4 12B (local QAT)",
        "classification & cleanup",
        True,
        "Runs on your machine through llama.cpp. Zero inference cost.",
    ),
    ModelSpec(
        "gemini-flash-lite",
        "gemini",
        "Gemini Flash-Lite",
        "short drafts",
        False,
        "Fast, low-cost drafts and short copy.",
    ),
    ModelSpec(
        "gemini-flash",
        "gemini",
        "Gemini Flash",
        "scripts & storyboards",
        False,
        "Balanced quality for full scripts and scene planning.",
    ),
    ModelSpec(
        "gemini-pro",
        "gemini",
        "Gemini Pro",
        "complex technical",
        False,
        "Deeper reasoning for ERP and technical walkthroughs.",
    ),
    ModelSpec(
        "claude-opus",
        "claude",
        "Claude Opus",
        "advanced escalation",
        False,
        "Premium escalation path for the hardest briefs.",
    ),
    ModelSpec(
        "mock-ai",
        "mock",
        "Mock AI",
        "development",
        True,
        "Deterministic local responses. No network calls, no cost.",
    ),
]

TASK_ROUTING = {
    "classification": "local-gemma-4-12b",
    "cleanup": "local-gemma-4-12b",
    "tagging": "local-gemma-4-12b",
    "short-draft": "gemini-flash-lite",
    "metadata": "gemini-flash-lite",
    "script": "gemini-flash",
    "storyboard": "gemini-flash",
    "motion": "gemini-flash",
    "complex": "gemini-pro",
    "technical": "gemini-pro",
    "quality": "gemini-pro",
    "escalation": "claude-opus",
}

SELECTED_MODEL_KEY = "ai.selected_model"


@dataclass
class CacheEntry:
    expires_at: float
    response: ProviderResponse


class AIService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.providers: dict[str, AIProvider] = {
            "mock": MockProvider(self.settings),
            "gemma": GemmaProvider(self.settings),
            "gemini": GeminiProvider(self.settings),
            "claude": ClaudeProvider(self.settings),
        }
        self._cache: dict[str, CacheEntry] = {}

    def _spec(self, model_id: str) -> ModelSpec:
        for spec in MODEL_SPECS:
            if spec.id == model_id:
                return spec
        raise ProviderError(f"Unknown model '{model_id}'.")

    def _configured(self, spec: ModelSpec) -> bool:
        if spec.provider == "mock":
            return True
        if spec.provider == "gemma":
            return bool(self.settings.gemma_base_url)
        if spec.provider == "gemini":
            return bool(self.settings.gemini_api_key)
        if spec.provider == "claude":
            return bool(self.settings.anthropic_api_key)
        return False

    def _selected_model_id(self, db: Session) -> str | None:
        row = db.get(Setting, SELECTED_MODEL_KEY)
        if row and isinstance(row.value, dict):
            value = row.value.get("model_id")
            if isinstance(value, str) and value:
                return value
        return None

    def select_model(self, db: Session, model_id: str) -> None:
        self._spec(model_id)
        row = db.get(Setting, SELECTED_MODEL_KEY)
        if row is None:
            row = Setting(key=SELECTED_MODEL_KEY, value={"model_id": model_id})
            db.add(row)
        else:
            row.value = {"model_id": model_id}
        db.commit()

    def list_models(self, db: Session) -> list[ModelInfo]:
        selected = self._selected_model_id(db)
        default = "mock-ai" if self.settings.mock_ai else "local-gemma-4-12b"
        chosen = selected or default
        models = []
        for spec in MODEL_SPECS:
            if spec.provider == "mock" and not self.settings.mock_ai:
                continue
            models.append(
                ModelInfo(
                    id=spec.id,
                    provider=spec.provider,
                    label=spec.label,
                    task=spec.task,
                    local=spec.local,
                    configured=self._configured(spec),
                    selected=spec.id == chosen,
                    description=spec.description,
                )
            )
        return models

    def resolve(self, db: Session, task: str) -> ModelSpec:
        if self.settings.mock_ai:
            return self._spec("mock-ai")
        selected = self._selected_model_id(db)
        if selected:
            return self._spec(selected)
        model_id = TASK_ROUTING.get(task, "gemini-flash")
        return self._spec(model_id)

    async def test_model(self, db: Session, model_id: str) -> ProviderStatus:
        spec = self._spec(model_id)
        if self.settings.mock_ai and spec.provider != "mock":
            return ProviderStatus(
                provider=spec.provider,
                model=spec.resolve_name(self.settings),
                configured=False,
                reachable=False,
                message="Mock AI mode is enabled. Set MOCK_AI=false to test live providers.",
            )
        configured = self._configured(spec)
        if not configured:
            return ProviderStatus(
                provider=spec.provider,
                model=spec.resolve_name(self.settings),
                configured=False,
                reachable=False,
                message=self._configuration_hint(spec),
            )
        provider = self.providers[spec.provider]
        try:
            result: ConnectionResult = await provider.test_connection(
                spec.resolve_name(self.settings)
            )
            return ProviderStatus(
                provider=spec.provider,
                model=spec.resolve_name(self.settings),
                configured=True,
                reachable=result.reachable,
                message=result.message,
                latency_ms=result.latency_ms,
            )
        except ProviderUnavailable as exc:
            return ProviderStatus(
                provider=spec.provider,
                model=spec.resolve_name(self.settings),
                configured=True,
                reachable=False,
                message=str(exc),
            )

    def _configuration_hint(self, spec: ModelSpec) -> str:
        if spec.provider == "gemini":
            return "Set GEMINI_API_KEY in .env to enable Gemini models."
        if spec.provider == "claude":
            return "Set ANTHROPIC_API_KEY in .env to enable Claude."
        if spec.provider == "gemma":
            return "Start the local llama.cpp server (scripts/start_gemma.ps1)."
        return "Model is not configured."

    def _cache_key(self, model: str, system: str, prompt: str, max_tokens: int) -> str:
        raw = f"{model}|{system}|{prompt}|{max_tokens}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def generate(self, db: Session, request: AIGenerateRequest) -> AIResult:
        spec = self.resolve(db, request.task)
        if not self.settings.mock_ai and not self._configured(spec):
            raise ProviderUnavailable(self._configuration_hint(spec))
        provider = self.providers[spec.provider]
        model_name = spec.resolve_name(self.settings)
        max_tokens = request.max_tokens or self.settings.ai_max_output_tokens
        key = self._cache_key(model_name, request.system, request.prompt, max_tokens)

        cached = self._cache.get(key)
        if cached and cached.expires_at > time.monotonic():
            response = cached.response
            self._record(db, response, request, cached=True)
            return self._to_result(response, cached=True)

        response = await self._generate_with_retries(
            provider, model_name, request, max_tokens
        )
        self._cache[key] = CacheEntry(
            expires_at=time.monotonic() + self.settings.ai_cache_ttl_seconds,
            response=response,
        )
        self._record(db, response, request, cached=False)
        return self._to_result(response, cached=False)

    async def _generate_with_retries(
        self,
        provider: AIProvider,
        model_name: str,
        request: AIGenerateRequest,
        max_tokens: int,
    ) -> ProviderResponse:
        last_error: Exception | None = None
        for attempt in range(self.settings.ai_max_retries + 1):
            try:
                return await provider.generate(
                    model=model_name,
                    prompt=request.prompt,
                    system=request.system,
                    max_tokens=max_tokens,
                )
            except ProviderUnavailable:
                raise
            except ProviderError as exc:
                last_error = exc
            except Exception as exc:  # pragma: no cover - defensive
                last_error = exc
            if attempt < self.settings.ai_max_retries:
                time.sleep(0.25 * (attempt + 1))
        raise ProviderError(f"AI generation failed: {last_error}")

    def _record(
        self,
        db: Session,
        response: ProviderResponse,
        request: AIGenerateRequest,
        *,
        cached: bool,
    ) -> None:
        db.add(
            AIUsage(
                provider=response.provider,
                model=response.model,
                task=request.task,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_tokens=response.prompt_tokens + response.completion_tokens,
                estimated_cost=0.0 if cached else response.estimated_cost,
                cached=cached,
                project_id=request.project_id,
            )
        )
        db.commit()

    def _to_result(self, response: ProviderResponse, *, cached: bool) -> AIResult:
        return AIResult(
            text=response.text,
            provider=response.provider,
            model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            total_tokens=response.prompt_tokens + response.completion_tokens,
            estimated_cost=0.0 if cached else response.estimated_cost,
            cached=cached,
        )

    def usage_summary(self, db: Session) -> UsageSummary:
        rows = db.execute(select(AIUsage)).scalars().all()
        total_requests = len(rows)
        total_tokens = sum(row.total_tokens for row in rows)
        estimated_cost = round(sum(row.estimated_cost for row in rows), 6)
        buckets: dict[tuple[str, str], UsageBucket] = {}
        for row in rows:
            key = (row.provider, row.model)
            bucket = buckets.get(key)
            if bucket is None:
                bucket = UsageBucket(
                    provider=row.provider,
                    model=row.model,
                    requests=0,
                    total_tokens=0,
                    estimated_cost=0.0,
                )
                buckets[key] = bucket
            bucket.requests += 1
            bucket.total_tokens += row.total_tokens
            bucket.estimated_cost = round(bucket.estimated_cost + row.estimated_cost, 6)
        selected = self._selected_model_id(db) or (
            "mock-ai" if self.settings.mock_ai else "local-gemma-4-12b"
        )
        budget = self.settings.ai_monthly_budget_usd
        used_pct = round((estimated_cost / budget) * 100, 2) if budget else 0.0
        return UsageSummary(
            total_requests=total_requests,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
            budget_usd=budget,
            budget_used_pct=used_pct,
            selected_model=selected,
            by_model=sorted(buckets.values(), key=lambda item: item.total_tokens, reverse=True),
        )


@lru_cache
def get_ai_service() -> AIService:
    return AIService()
