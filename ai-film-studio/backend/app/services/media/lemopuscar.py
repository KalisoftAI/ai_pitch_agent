"""Adapter boundary for a future Lemo-Opuscar integration.

The engine is intentionally not reimplemented here. The adapter reports
availability and raises a clear error until a real integration is validated.
"""


class LemoOpuscarAdapter:
    name = "lemo-opuscar"

    def is_available(self) -> bool:
        return False

    def render(self, *args, **kwargs) -> str:
        raise NotImplementedError(
            "Lemo-Opuscar integration is not enabled. Validate the upstream engine "
            "separately before making it the default renderer."
        )
