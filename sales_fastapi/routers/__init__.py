from .auth import router as auth_router
from .campaigns import router as campaigns_router
from .contacts import router as contacts_router
from .email import router as email_router
from .governance import governance_router, llm_router
from .social import router as social_router
from .system import router as system_router
from .templates import router as templates_router
from .whatsapp import router as whatsapp_router

__all__ = [
    "auth_router",
    "campaigns_router",
    "contacts_router",
    "email_router",
    "governance_router",
    "llm_router",
    "social_router",
    "system_router",
    "templates_router",
    "whatsapp_router",
]
