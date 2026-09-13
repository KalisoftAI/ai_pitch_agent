"""LLM layer: task registry, guardrails, providers, cost-optimised router."""

from .guardrails import GuardrailReport, scan_prompt, validate_output
from .providers import EchoProvider, GeminiProvider, LLMResult, OllamaProvider, estimate_tokens
from .router import (
    AllProvidersFailed,
    BudgetExceeded,
    LLMError,
    ModelRouter,
    PromptRejected,
    RouteResult,
    estimate_cost_micros,
)
from .tasks import TASKS, TaskSpec, Tier, get_task, list_tasks

__all__ = [
    "AllProvidersFailed",
    "BudgetExceeded",
    "EchoProvider",
    "GeminiProvider",
    "GuardrailReport",
    "LLMError",
    "LLMResult",
    "ModelRouter",
    "OllamaProvider",
    "PromptRejected",
    "RouteResult",
    "TASKS",
    "TaskSpec",
    "Tier",
    "estimate_cost_micros",
    "estimate_tokens",
    "get_task",
    "list_tasks",
    "scan_prompt",
    "validate_output",
]
