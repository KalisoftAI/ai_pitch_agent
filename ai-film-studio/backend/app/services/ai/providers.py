from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import httpx

from app.core.config import Settings
from app.services.ai.pricing import estimate_cost


class ProviderError(RuntimeError):
    pass


class ProviderUnavailable(ProviderError):
    pass


@dataclass
class ProviderResponse:
    text: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    estimated_cost: float


@dataclass
class ConnectionResult:
    reachable: bool
    message: str
    latency_ms: int | None = None


class AIProvider:
    name = "base"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def test_connection(self, model: str) -> ConnectionResult:
        raise NotImplementedError

    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> ProviderResponse:
        raise NotImplementedError


class MockProvider(AIProvider):
    name = "mock"

    async def test_connection(self, model: str) -> ConnectionResult:
        return ConnectionResult(True, "Mock AI is ready (no external calls).", 1)

    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> ProviderResponse:
        await asyncio.sleep(0.05)
        prompt_tokens = max(1, len(prompt.split()) + len(system.split()))
        text = self._compose(prompt)
        completion_tokens = max(1, len(text.split()))
        return ProviderResponse(
            text=text,
            provider=self.name,
            model="mock-ai",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost=0.0,
        )

    def _compose(self, prompt: str) -> str:
        lower = prompt.lower()
        if "storyboard" in lower or "scene" in lower:
            return (
                "SCENE 1 | Hook | Open with a bold question that names the problem. | "
                "A dark studio desk with a glowing dashboard | 5\n"
                "SCENE 2 | Context | Explain why this matters for a growing business. | "
                "Animated charts rising over a navy background | 6\n"
                "SCENE 3 | Insight | Reveal the practical framework in three steps. | "
                "Three clean cards sliding into view | 7\n"
                "SCENE 4 | Proof | Show a realistic before and after workflow. | "
                "Split screen of manual work versus automated flow | 7\n"
                "SCENE 5 | Action | Give one concrete action to take today. | "
                "Close-up of a checklist being completed | 6\n"
                "SCENE 6 | Close | End with a confident call to action. | "
                "Logo reveal with violet accent and tagline | 5"
            )
        if "paragraph" in lower or "rewrite" in lower:
            return (
                "Here is a sharper version of that paragraph: it opens with a direct claim, "
                "grounds the idea in a familiar business situation, and ends with a clear action. "
                "The language is concise, confident, and ready to record."
            )
        return (
            "Most teams do not lose time because they lack information. They lose it because "
            "the information is scattered. Start by writing down the one decision this video "
            "should help your viewer make. Then build every scene around that single outcome. "
            "When the story is focused, the production becomes faster, cheaper, and far more "
            "persuasive."
        )


class GemmaProvider(AIProvider):
    name = "gemma"

    async def test_connection(self, model: str) -> ConnectionResult:
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.settings.gemma_base_url.rstrip('/')}/models",
                    headers=self._headers(),
                )
            latency = int((time.perf_counter() - started) * 1000)
            if response.status_code >= 400:
                raise ProviderUnavailable(
                    f"llama.cpp server responded {response.status_code}. "
                    "Start it with scripts/start_gemma.ps1."
                )
            return ConnectionResult(True, "Local Gemma server is reachable.", latency)
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(
                "Local Gemma server is not reachable. Run scripts/start_gemma.ps1 "
                f"and confirm GEMMA_BASE_URL ({self.settings.gemma_base_url})."
            ) from exc

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.settings.gemma_api_key:
            headers["Authorization"] = f"Bearer {self.settings.gemma_api_key}"
        return headers

    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> ProviderResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.settings.gemma_model_id,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": 0.95,
            "top_k": 64,
        }
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                response = await client.post(
                    f"{self.settings.gemma_base_url.rstrip('/')}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(
                "Local Gemma server is not reachable. Run scripts/start_gemma.ps1 first."
            ) from exc
        if response.status_code >= 400:
            raise ProviderUnavailable(
                f"Local Gemma request failed ({response.status_code}): {response.text[:300]}"
            )
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens") or max(1, len(prompt.split())))
        completion_tokens = int(
            usage.get("completion_tokens") or max(1, len(text.split()))
        )
        return ProviderResponse(
            text=text,
            provider=self.name,
            model=self.settings.gemma_model_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost=estimate_cost(
                self.settings.gemma_model_id, prompt_tokens, completion_tokens
            ),
        )


class GeminiProvider(AIProvider):
    name = "gemini"

    async def test_connection(self, model: str) -> ConnectionResult:
        if not self.settings.gemini_api_key:
            raise ProviderUnavailable("GEMINI_API_KEY is not configured.")
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}",
                    params={"key": self.settings.gemini_api_key},
                )
            latency = int((time.perf_counter() - started) * 1000)
            if response.status_code >= 400:
                raise ProviderUnavailable(
                    f"Gemini responded {response.status_code}: {response.text[:200]}"
                )
            return ConnectionResult(True, "Gemini API key accepted.", latency)
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"Gemini connection failed: {exc}") from exc

    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> ProviderResponse:
        if not self.settings.gemini_api_key:
            raise ProviderUnavailable("GEMINI_API_KEY is not configured.")
        body: dict = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    params={"key": self.settings.gemini_api_key},
                    json=body,
                )
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"Gemini request failed: {exc}") from exc
        if response.status_code >= 400:
            raise ProviderUnavailable(
                f"Gemini request failed ({response.status_code}): {response.text[:300]}"
            )
        data = response.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise ProviderUnavailable("Gemini returned no candidates.")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "\n".join(part.get("text", "") for part in parts).strip()
        usage = data.get("usageMetadata") or {}
        prompt_tokens = int(usage.get("promptTokenCount") or 0)
        completion_tokens = int(usage.get("candidatesTokenCount") or 0)
        return ProviderResponse(
            text=text,
            provider=self.name,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost=estimate_cost(model, prompt_tokens, completion_tokens),
        )


class ClaudeProvider(AIProvider):
    name = "claude"

    async def test_connection(self, model: str) -> ConnectionResult:
        if not self.settings.anthropic_api_key:
            raise ProviderUnavailable("ANTHROPIC_API_KEY is not configured.")
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=self._headers(),
                    json={
                        "model": model,
                        "max_tokens": 8,
                        "messages": [{"role": "user", "content": "ping"}],
                    },
                )
            latency = int((time.perf_counter() - started) * 1000)
            if response.status_code >= 400:
                raise ProviderUnavailable(
                    f"Claude responded {response.status_code}: {response.text[:200]}"
                )
            return ConnectionResult(True, "Claude API key accepted.", latency)
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"Claude connection failed: {exc}") from exc

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> ProviderResponse:
        if not self.settings.anthropic_api_key:
            raise ProviderUnavailable("ANTHROPIC_API_KEY is not configured.")
        body: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=self._headers(),
                    json=body,
                )
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"Claude request failed: {exc}") from exc
        if response.status_code >= 400:
            raise ProviderUnavailable(
                f"Claude request failed ({response.status_code}): {response.text[:300]}"
            )
        data = response.json()
        blocks = data.get("content") or []
        text = "\n".join(block.get("text", "") for block in blocks if block.get("type") == "text")
        usage = data.get("usage") or {}
        prompt_tokens = int(usage.get("input_tokens") or 0)
        completion_tokens = int(usage.get("output_tokens") or 0)
        return ProviderResponse(
            text=text,
            provider=self.name,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost=estimate_cost(model, prompt_tokens, completion_tokens),
        )
