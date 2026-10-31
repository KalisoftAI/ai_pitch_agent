from .auth import router as auth_router
from .campaigns import router as campaigns_router
from .contacts import router as contacts_router
from .dashboard import router as dashboard_router
from .email import router as email_router
from .erp import router as erp_router
from .events import router as events_router
from .feedback import router as feedback_router
from .feedback_pipeline import router as feedback_pipeline_router
from .google_email import router as google_email_router
from .governance import governance_router, llm_router
from .journey import router as journey_router
from .ops import router as ops_router
from .scheduler import router as scheduler_router
from .social import router as social_router
from .system import router as system_router
from .team import router as team_router
from .templates import router as templates_router
from .voice import router as voice_router
from .whatsapp import router as whatsapp_router

__all__ = [
    "auth_router",
    "campaigns_router",
    "contacts_router",
    "dashboard_router",
    "email_router",
    "erp_router",
    "events_router",
    "feedback_router",
    "feedback_pipeline_router",
    "google_email_router",
    "journey_router",
    "ops_router",
    "governance_router",
    "llm_router",
    "scheduler_router",
    "social_router",
    "system_router",
    "team_router",
    "templates_router",
    "voice_router",
    "whatsapp_router",
]
