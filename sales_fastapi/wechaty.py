"""Wechaty gateway client and webhook signature verification.

The FastAPI service talks to the Node Wechaty gateway over HTTP and verifies the
HMAC signature on inbound webhooks. All calls degrade gracefully when the gateway
or feature flag is unavailable.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx

from .config import settings

META_GRAPH_BASE = "https://graph.facebook.com/v21.0"


class WechatyGateway:
    def __init__(
        self, base_url: str | None = None, token: str | None = None, timeout: int | None = None
    ):
        self.base_url = (base_url or settings.WECHATY_GATEWAY_URL).rstrip("/")
        self.token = token if token is not None else settings.WECHATY_GATEWAY_TOKEN
        self.timeout = timeout or settings.WECHATY_TIMEOUT_SECONDS

    @property
    def meta_configured(self) -> bool:
        return bool(settings.WHATSAPP_API_KEY and settings.WHATSAPP_PHONE_NUMBER_ID)

    @property
    def available(self) -> bool:
        return bool(settings.WHATSAPP_ENABLED and (self.meta_configured or self.base_url))

    def _headers(self) -> dict[str, str]:
        return {"x-gateway-token": self.token} if self.token else {}

    def health(self) -> dict[str, Any]:
        if self.meta_configured:
            return {"available": True, "provider": "meta-cloud"}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(f"{self.base_url}/health")
                response.raise_for_status()
                return {"available": True, **response.json()}
        except Exception as exc:  # noqa: BLE001 - status endpoint must not raise
            return {"available": False, "error": type(exc).__name__}

    def send_text(self, to: str, text: str) -> dict[str, Any]:
        if self.meta_configured:
            return self._send_meta(to, text)
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/send",
                json={"to": to, "text": text},
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()

    def _send_meta(self, to: str, text: str) -> dict[str, Any]:
        url = f"{META_GRAPH_BASE}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
        headers = {"Authorization": f"Bearer {settings.WHATSAPP_API_KEY}"}
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
        message_id = (result.get("messages") or [{}])[0].get("id", "")
        return {
            "id": message_id,
            "to": to,
            "text": text,
            "status": "sent",
            "provider": "meta-cloud",
        }

    def simulate_inbound(self, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/simulate/inbound",
                json=payload,
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()


def verify_webhook_signature(raw_body: bytes, signature: str, secret: str | None = None) -> bool:
    """Constant-time HMAC-SHA256 check. Returns True when no secret is configured."""
    secret = secret if secret is not None else settings.WECHATY_WEBHOOK_SECRET
    if not secret:
        return True
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")
