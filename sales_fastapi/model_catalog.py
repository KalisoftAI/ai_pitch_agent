"""Model catalog for user-facing model selection (with human-review policy).

Costs are indicative INR/1K tokens (input, output) used by the LLM router's
budget accounting; they mirror the router's table so the UI stays truthful.
"""
from __future__ import annotations

from .config import settings


def catalog() -> list[dict]:
    return [
        {
            "id": "gemma-4-27b-it", "provider": "gemma", "label": "Gemma 4 27B (IT)",
            "tier": "medium", "context": "128k", "cost_inr_per_1k": [0.10, 0.40],
            "best_for": ["outreach personalisation", "customer feedback summaries", "journey next-step"],
            "pii_allowed": True, "human_review": settings.HUMAN_REVIEW_REQUIRED,
        },
        {
            "id": "gemini-2.5-flash", "provider": "gemini", "label": "Gemini 2.5 Flash",
            "tier": "medium", "context": "1M", "cost_inr_per_1k": [0.10, 0.40],
            "best_for": ["fast classification", "reply drafting", "daily prompt refinement"],
            "pii_allowed": True, "human_review": settings.HUMAN_REVIEW_REQUIRED,
        },
        {
            "id": "gemini-2.0-flash", "provider": "gemini", "label": "Gemini 2.0 Flash",
            "tier": "medium", "context": "1M", "cost_inr_per_1k": [0.10, 0.40],
            "best_for": ["fallback flash", "batch summaries"],
            "pii_allowed": True, "human_review": settings.HUMAN_REVIEW_REQUIRED,
        },
        {
            "id": "gemini-2.0-flash-lite", "provider": "gemini", "label": "Gemini 2.0 Flash-Lite",
            "tier": "small", "context": "1M", "cost_inr_per_1k": [0.05, 0.20],
            "best_for": ["intent labels", "JSON extraction"],
            "pii_allowed": False, "human_review": settings.HUMAN_REVIEW_REQUIRED,
        },
        {
            "id": "gemini-2.5-pro", "provider": "gemini", "label": "Gemini 2.5 Pro",
            "tier": "large", "context": "2M", "cost_inr_per_1k": [1.25, 5.00],
            "best_for": ["deep research synthesis", "multi-section pitches"],
            "pii_allowed": True, "human_review": settings.HUMAN_REVIEW_REQUIRED,
        },
        {
            "id": settings.LLM_LOCAL_MODEL, "provider": "ollama", "label": f"Local SLM ({settings.LLM_LOCAL_MODEL})",
            "tier": "small", "context": "8k", "cost_inr_per_1k": [0.0, 0.0],
            "best_for": ["offline classification", "drafting (no data leaves device)"],
            "pii_allowed": True, "human_review": False,
        },
    ]


def default_model() -> str:
    return settings.GEMINI_FLASH_MODEL or "gemini-2.5-flash"
