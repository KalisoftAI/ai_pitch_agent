from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------- Auth ----------
class GoogleLoginIn(BaseModel):
    id_token: str = Field(..., description="Google Identity Services ID token (JWT)")


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    picture: str
    domain: str


# ---------- Contacts ----------
class ContactBase(BaseModel):
    company: str = Field(default="", max_length=255)
    name: str = Field(default="", max_length=255)
    email: str = Field(..., min_length=3, max_length=320)
    phone: str = Field(default="", max_length=64)
    domain: str = Field(default="", max_length=255)
    intent: str = Field(default="", max_length=64)
    context: str = Field(default="", max_length=10_000)
    linkedin_company: str = Field(default="", max_length=512)
    linkedin_profiles: list[str] = Field(default_factory=list)
    address: str = Field(default="", max_length=2_000)
    purchase_contact_name: str = Field(default="", max_length=255)
    purchase_contact_role: str = Field(default="", max_length=255)
    purchase_contact_email: str = Field(default="", max_length=320)
    purchase_contact_phone: str = Field(default="", max_length=64)
    tags: list[str] = Field(default_factory=list)
    notes: str = Field(default="", max_length=10_000)


class ContactCreate(ContactBase):
    source: str = "manual"
    gcs_path: str = ""


class ContactUpdate(BaseModel):
    company: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    domain: Optional[str] = None
    intent: Optional[str] = None
    context: Optional[str] = None
    linkedin_company: Optional[str] = None
    linkedin_profiles: Optional[list[str]] = None
    address: Optional[str] = None
    purchase_contact_name: Optional[str] = None
    purchase_contact_role: Optional[str] = None
    purchase_contact_email: Optional[str] = None
    purchase_contact_phone: Optional[str] = None
    tags: Optional[list[str]] = None
    notes: Optional[str] = None


class ContactOut(ContactBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    gcs_path: str
    created_at: datetime
    updated_at: datetime


# ---------- Email ----------
class EmailConnectionCreate(BaseModel):
    email_address: str = Field(..., min_length=3, max_length=320)
    imap_host: str = Field(default="", max_length=255)
    imap_port: int = 993
    smtp_host: str = Field(default="", max_length=255)
    smtp_port: int = 587
    password: str = Field(default="", max_length=512, description="App password; stored encrypted")


class EmailConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email_address: str
    imap_host: str
    imap_port: int
    smtp_host: str
    smtp_port: int
    is_connected: bool


class SendMailIn(BaseModel):
    to: str = Field(..., min_length=3, max_length=320)
    subject: str = Field(..., min_length=1, max_length=998)
    body: str = Field(..., min_length=1, max_length=100_000)


class SchedulerRunIn(BaseModel):
    notify_email: bool = True


class EmailFetchIn(BaseModel):
    query: str = Field(default="", max_length=256)
    sender: str = Field(default="", max_length=320)
    intent: str = Field(default="", max_length=64)
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    unread_only: bool = False
    include_context: bool = True
    include_body: bool = False
    context_chars: int = Field(default=280, ge=80, le=1000)
    limit: int = Field(default=15, ge=1, le=50)

    @model_validator(mode="after")
    def validate_date_window(self):
        if self.since and self.until and self.since.date() > self.until.date():
            raise ValueError("since must be on or before until")
        return self


class EmailMessageContextOut(BaseModel):
    uid: str
    subject: str
    sender: str
    date: str
    intent: str
    context: str = ""
    body: Optional[str] = None


class EmailFetchOut(BaseModel):
    connection_id: int
    source: str = "imap"
    count: int
    scanned: int
    messages: list[EmailMessageContextOut]
    filters: dict[str, Any]
    options: dict[str, Any]


class GoogleMailboxOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email_address: str
    is_connected: bool
    scopes: str
    last_checked_at: Optional[datetime] = None


class GoogleOAuthAuthorizeOut(BaseModel):
    authorization_url: str
    expires_in: int


# ---------- LinkedIn / Reddit ----------
class LinkedInSearchIn(BaseModel):
    keywords: list[str] = Field(default_factory=lambda: ["procurement", "scm", "hiring"])
    location: str = ""


class RedditSearchIn(BaseModel):
    subreddits: list[str] = Field(default_factory=lambda: ["jobs", "recruiting"])
    keywords: list[str] = Field(default_factory=lambda: ["hiring", "procurement"])


class YouTubeSearchIn(BaseModel):
    queries: list[str] = Field(default_factory=lambda: ["hiring procurement", "supply chain"])
    max_results: int = Field(default=10, ge=1, le=50)


# ---------- WhatsApp ----------
class WhatsAppSendIn(BaseModel):
    phone_number: str
    message: str


# ---------- Wechaty gateway / WhatsApp ----------
class WhatsAppSendRequest(BaseModel):
    to: str = Field(..., min_length=1, max_length=128)
    text: str = Field(..., min_length=1, max_length=4096)


class WhatsAppSendResponse(BaseModel):
    ok: bool
    id: str
    to: str
    status: str
    provider: str = ""


class WhatsAppInbound(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = ""
    from_id: str = Field(default="", alias="from")
    from_name: str = ""
    room: Optional[str] = None
    text: str = Field(default="", max_length=10_000)
    timestamp: Optional[int] = None
    provider: str = ""


class WhatsAppMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phone_number: str
    message: str
    status: str
    created_at: datetime


# ---------- Message templates ----------
class TemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    channel: str = Field(default="email", max_length=32)
    strategy: str = Field(default="cold_outreach", max_length=32)
    funnel_stage: str = Field(default="awareness", max_length=32)
    subject: str = Field(default="", max_length=255)
    body: str = Field(default="", max_length=20_000)
    variables: list[str] = Field(default_factory=list)
    is_active: bool = True


class TemplateCreate(TemplateBase):
    pass


class TemplateUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    channel: Optional[str] = Field(default=None, max_length=32)
    strategy: Optional[str] = Field(default=None, max_length=32)
    funnel_stage: Optional[str] = Field(default=None, max_length=32)
    subject: Optional[str] = Field(default=None, max_length=255)
    body: Optional[str] = Field(default=None, max_length=20_000)
    variables: Optional[list[str]] = None
    is_active: Optional[bool] = None


class TemplateOut(TemplateBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


# ---------- Campaigns (bulk outreach) ----------
class CampaignFilter(BaseModel):
    intent: str = ""
    source: str = ""
    q: str = ""
    limit: int = Field(default=50, ge=1, le=1000)


class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    channel: str = Field(default="email", max_length=32)
    strategy: str = Field(default="cold_outreach", max_length=32)
    template_id: int
    use_ai: bool = True
    filter: CampaignFilter = Field(default_factory=CampaignFilter)


class CampaignMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int
    contact_id: int
    to_address: str
    rendered_subject: str
    rendered_body: str
    status: str
    error: str
    provider_id: str
    sent_at: Optional[datetime] = None
    created_at: datetime


class CampaignMessageUpdate(BaseModel):
    rendered_subject: Optional[str] = Field(default=None, max_length=255)
    rendered_body: Optional[str] = Field(default=None, max_length=20_000)
    approve: bool = False


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    channel: str
    strategy: str
    template_id: int
    ai_model: str
    status: str
    total: int
    sent_count: int
    failed_count: int
    created_at: datetime
    updated_at: datetime


class CampaignDetail(CampaignOut):
    messages: list[CampaignMessageOut] = Field(default_factory=list)


class CampaignSendResult(BaseModel):
    campaign_id: int
    status: str
    sent: int
    failed: int
    skipped: int


# ---------- Feedback ----------
class FeedbackIn(BaseModel):
    category: str = Field(default="general", max_length=32)
    rating: int = Field(default=5, ge=1, le=5)
    message: str = Field(..., min_length=1, max_length=5_000)
    page: str = Field(default="", max_length=64)


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    rating: int
    message: str
    page: str
    status: str
    notified: bool
    created_at: datetime


# ---------- Governance / Audit ----------
class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    resource_type: str
    resource_id: str
    status: str
    created_at: datetime


# ---------- LLM / SLM routing ----------
class LLMRunIn(BaseModel):
    task: str = Field(..., min_length=1, max_length=64)
    prompt: str = Field(..., min_length=1, max_length=20_000)
    system: str = Field(default="", max_length=10_000)
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)


class LLMRunOut(BaseModel):
    task: str
    tier: str
    provider: str
    model: str
    output: str
    input_tokens: int
    output_tokens: int
    cost_micros: int
    fallback_used: bool
    guardrails: dict[str, Any]


# ---------- Events ----------
class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    event_url: str
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    when_text: str
    location: str
    mode: str
    status: str
    organiser: str
    attendance: str
    about: str
    todo: str
    source_sheet: str
    source_row: int


class EventSummaryOut(BaseModel):
    events: int = 0
    upcoming: int = 0
    next_30_days: int = 0
    past: int = 0
    online: int = 0
    in_person: int = 0
    hybrid: int = 0
    unscheduled: int = 0
    recipients: int = 0
    queued_messages: int = 0
    sent_messages: int = 0
    failed_messages: int = 0
    last_imported_at: Optional[datetime] = None


class EventImportIn(BaseModel):
    source_path: str = Field(default="", max_length=512)
    include_contacts: bool = True
    include_events: bool = True


class EventImportOut(BaseModel):
    events_imported: int = 0
    events_updated: int = 0
    contacts_imported: int = 0
    contacts_updated: int = 0
    sheets: list[str] = Field(default_factory=list)
    source: str = ""


class EventRecipientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phone: str
    name: str
    company: str
    notes: str


class EventTemplateOut(BaseModel):
    event_id: int
    template: str
    variables: list[str] = Field(default_factory=list)
    preview: str = ""
    preview_name: str = ""
    recipient_count: int = 0


class EventScheduleIn(BaseModel):
    recipient_ids: list[int] = Field(default_factory=list, max_length=200)
    # Omitted means "use the default event template"; an empty string is a
    # client bug and is rejected by the router.
    template: Optional[str] = Field(default=None, max_length=4_096)
    scheduled_at: Optional[datetime] = None
    preview_only: bool = False


class EventScheduleOut(BaseModel):
    event_id: int
    queued: int = 0
    skipped: int = 0
    scheduled_at: Optional[datetime] = None
    preview: str = ""
    unresolved: list[str] = Field(default_factory=list)
    message_ids: list[int] = Field(default_factory=list)


class EventMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    recipient_id: int
    phone: str
    body: str
    status: str
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    error: str
    created_at: datetime


class EventMessageListOut(BaseModel):
    items: list[EventMessageOut] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)


class EventSendResultOut(BaseModel):
    message_id: int
    ok: bool
    status: str
    phone: str = ""
    error: str = ""
