from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    google_sub: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    picture: Mapped[str] = mapped_column(String(512), default="")
    domain: Mapped[str] = mapped_column(String(255), default="", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    password_hash: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Contact(Base):
    """A sales contact, optionally enriched with company / SCM details."""

    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("user_id", "email", name="uq_contact_user_email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)

    # Core
    company: Mapped[str] = mapped_column(String(255), default="", index=True)
    name: Mapped[str] = mapped_column(String(255), default="", index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    phone: Mapped[str] = mapped_column(String(64), default="")

    # Segregation axes
    domain: Mapped[str] = mapped_column(String(255), default="", index=True)
    intent: Mapped[str] = mapped_column(String(64), default="", index=True)
    context: Mapped[str] = mapped_column(Text, default="")

    # Enrichment
    linkedin_company: Mapped[str] = mapped_column(String(512), default="")
    linkedin_profiles: Mapped[list] = mapped_column(JSON, default=list)
    address: Mapped[str] = mapped_column(Text, default="")
    purchase_contact_name: Mapped[str] = mapped_column(String(255), default="")
    purchase_contact_role: Mapped[str] = mapped_column(String(255), default="")
    purchase_contact_email: Mapped[str] = mapped_column(String(320), default="")
    purchase_contact_phone: Mapped[str] = mapped_column(String(64), default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")

    # Provenance
    source: Mapped[str] = mapped_column(String(32), default="manual", index=True)
    gcs_path: Mapped[str] = mapped_column(String(512), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class EmailConnection(Base):
    __tablename__ = "email_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    email_address: Mapped[str] = mapped_column(String(320), index=True)
    imap_host: Mapped[str] = mapped_column(String(255), default="")
    imap_port: Mapped[int] = mapped_column(Integer, default=993)
    smtp_host: Mapped[str] = mapped_column(String(255), default="")
    smtp_port: Mapped[int] = mapped_column(Integer, default=587)
    # Fernet-encrypted app password (never returned by the API).
    secret_encrypted: Mapped[str] = mapped_column(Text, default="")
    is_connected: Mapped[bool] = mapped_column(Boolean, default=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class GoogleMailbox(Base):
    __tablename__ = "google_mailboxes"
    __table_args__ = (
        UniqueConstraint("user_id", "email_address", name="uq_google_mailbox_user_email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    email_address: Mapped[str] = mapped_column(String(320), index=True)
    access_token_encrypted: Mapped[str] = mapped_column(Text, default="")
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, default="")
    token_expiry: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scopes: Mapped[str] = mapped_column(Text, default="")
    is_connected: Mapped[bool] = mapped_column(Boolean, default=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class LinkedInProfile(Base):
    __tablename__ = "linkedin_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    profile_url: Mapped[str] = mapped_column(String(512), index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    headline: Mapped[str] = mapped_column(String(512), default="")
    company: Mapped[str] = mapped_column(String(255), default="")
    location: Mapped[str] = mapped_column(String(255), default="")
    skills: Mapped[list] = mapped_column(JSON, default=list)
    source_keyword: Mapped[str] = mapped_column(String(255), default="")
    extracted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RedditPost(Base):
    __tablename__ = "reddit_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    post_url: Mapped[str] = mapped_column(String(512), index=True)
    title: Mapped[str] = mapped_column(String(512), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    subreddit: Mapped[str] = mapped_column(String(128), default="")
    alerts_related: Mapped[list] = mapped_column(JSON, default=list)
    extracted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    phone_number: Mapped[str] = mapped_column(String(64), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Event(Base):
    """An exhibition, webinar or meetup imported from the event workbook."""

    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("user_id", "fingerprint", name="uq_event_user_fingerprint"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), default="")
    title: Mapped[str] = mapped_column(String(255), index=True, default="")
    event_url: Mapped[str] = mapped_column(String(512), default="")
    starts_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    when_text: Mapped[str] = mapped_column(String(512), default="")
    location: Mapped[str] = mapped_column(String(512), default="")
    mode: Mapped[str] = mapped_column(String(32), default="unknown", index=True)
    status: Mapped[str] = mapped_column(String(32), default="upcoming", index=True)
    organiser: Mapped[str] = mapped_column(String(255), default="")
    attendance: Mapped[str] = mapped_column(String(128), default="")
    about: Mapped[str] = mapped_column(Text, default="")
    todo: Mapped[str] = mapped_column(Text, default="")
    source_sheet: Mapped[str] = mapped_column(String(64), default="")
    source_row: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class EventRecipient(Base):
    """A WhatsApp contact extracted from the workbook contacts sheet."""

    __tablename__ = "event_recipients"
    __table_args__ = (UniqueConstraint("user_id", "phone", name="uq_event_recipient_user_phone"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    phone: Mapped[str] = mapped_column(String(32), index=True, default="")
    name: Mapped[str] = mapped_column(String(255), default="")
    company: Mapped[str] = mapped_column(String(255), default="", index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    source_sheet: Mapped[str] = mapped_column(String(64), default="")
    source_row: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class EventMessage(Base):
    """A queued WhatsApp message for one event recipient."""

    __tablename__ = "event_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    event_id: Mapped[int] = mapped_column(Integer, ForeignKey("events.id"), index=True)
    recipient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("event_recipients.id"), index=True
    )
    phone: Mapped[str] = mapped_column(String(32), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AuditLog(Base):
    """Append-only security/audit trail. Details are always PII-redacted."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    action: Mapped[str] = mapped_column(String(128), index=True)
    resource_type: Mapped[str] = mapped_column(String(64), default="")
    resource_id: Mapped[str] = mapped_column(String(128), default="")
    tenant_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    status: Mapped[str] = mapped_column(String(32), default="success", index=True)
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class ModelUsage(Base):
    """Per-call LLM usage/cost ledger for budget and cost optimisation."""

    __tablename__ = "model_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    task: Mapped[str] = mapped_column(String(64), index=True)
    tier: Mapped[str] = mapped_column(String(16), default="")
    provider: Mapped[str] = mapped_column(String(32), default="")
    model: Mapped[str] = mapped_column(String(128), default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_micros: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class Feedback(Base):
    """User feedback submitted from the UI; triggers a mail notification."""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    category: Mapped[str] = mapped_column(String(32), default="general", index=True)
    rating: Mapped[int] = mapped_column(Integer, default=5)
    message: Mapped[str] = mapped_column(Text, default="")
    page: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MessageTemplate(Base):
    """Reusable outreach template for a channel and sales-funnel strategy."""

    __tablename__ = "message_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    name: Mapped[str] = mapped_column(String(128), index=True)
    channel: Mapped[str] = mapped_column(String(32), index=True, default="email")
    strategy: Mapped[str] = mapped_column(String(32), index=True, default="cold_outreach")
    funnel_stage: Mapped[str] = mapped_column(String(32), default="awareness")
    subject: Mapped[str] = mapped_column(String(255), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    variables: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Campaign(Base):
    """A bulk outreach run built from a template and a contact selection."""

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    name: Mapped[str] = mapped_column(String(160), default="")
    channel: Mapped[str] = mapped_column(String(32), index=True, default="email")
    strategy: Mapped[str] = mapped_column(String(32), default="cold_outreach")
    template_id: Mapped[int] = mapped_column(Integer, default=0)
    ai_model: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(32), index=True, default="pending_review")
    total: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class CampaignMessage(Base):
    """A single personalised message within a campaign (human-reviewable)."""

    __tablename__ = "campaign_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    contact_id: Mapped[int] = mapped_column(Integer, default=0)
    to_address: Mapped[str] = mapped_column(String(320), default="")
    rendered_subject: Mapped[str] = mapped_column(String(255), default="")
    rendered_body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), index=True, default="pending_review")
    error: Mapped[str] = mapped_column(String(512), default="")
    provider_id: Mapped[str] = mapped_column(String(128), default="")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ErpDispatch(Base):
    """Dispatch rows synced daily from the ERP report (ERP-V1/Reports -> Dispatch)."""

    __tablename__ = "erp_dispatch"
    __table_args__ = (UniqueConstraint("report_date", "dispatch_no", name="uq_erp_dispatch_day_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_date: Mapped[str] = mapped_column(String(10), index=True, default="")
    dispatch_no: Mapped[str] = mapped_column(String(64), index=True, default="")
    customer: Mapped[str] = mapped_column(String(255), index=True, default="")
    plant: Mapped[str] = mapped_column(String(64), index=True, default="")
    sales_person: Mapped[str] = mapped_column(String(128), default="")
    schedule_qty: Mapped[float] = mapped_column(Integer, default=0)
    dispatched_qty: Mapped[float] = mapped_column(Integer, default=0)
    balance_qty: Mapped[float] = mapped_column(Integer, default=0)
    pct_complete: Mapped[float] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), index=True, default="")
    synced_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ErpOrder(Base):
    """Order rows synced from the ERP report (Orders sheet)."""

    __tablename__ = "erp_orders"
    __table_args__ = (UniqueConstraint("report_date", "order_no", name="uq_erp_order_day_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_date: Mapped[str] = mapped_column(String(10), index=True, default="")
    order_no: Mapped[str] = mapped_column(String(64), index=True, default="")
    customer: Mapped[str] = mapped_column(String(255), index=True, default="")
    order_date: Mapped[str] = mapped_column(String(10), index=True, default="")
    required_date: Mapped[str] = mapped_column(String(10), default="")
    status: Mapped[str] = mapped_column(String(32), index=True, default="")
    total_value: Mapped[float] = mapped_column(Integer, default=0)
    synced_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class IntegrationSetting(Base):
    """Key/value settings (YouTube API key, channel id, sync schedule...)."""

    __tablename__ = "integration_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class SyncRun(Base):
    """Audit trail for sync jobs (ERP dispatch, YouTube, graph, dump)."""

    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True, default="ok")
    detail: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class JourneyEvent(Base):
    """Customer-journey event (stage transitions, feedback, purchases, stories)."""

    __tablename__ = "journey_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    contact_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    customer_type: Mapped[str] = mapped_column(String(32), index=True, default="lead")
    stage: Mapped[str] = mapped_column(String(32), index=True, default="awareness")
    event: Mapped[str] = mapped_column(String(64), index=True, default="")
    channel: Mapped[str] = mapped_column(String(32), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class VoiceTranscript(Base):
    """Call-recording transcription + layered analysis (sound, tone, context, lead)."""

    __tablename__ = "voice_transcripts"
    __table_args__ = (UniqueConstraint("gcs_path", name="uq_voice_transcript_path"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    gcs_path: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    file_name: Mapped[str] = mapped_column(String(255), index=True, default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    gcs_updated: Mapped[str] = mapped_column(String(64), default="")
    duration_sec: Mapped[float] = mapped_column(Integer, default=0)
    sample_rate: Mapped[int] = mapped_column(Integer, default=0)
    channels: Mapped[int] = mapped_column(Integer, default=0)
    mean_volume_db: Mapped[float] = mapped_column(Integer, default=0)
    max_volume_db: Mapped[float] = mapped_column(Integer, default=0)
    silence_ratio: Mapped[float] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), index=True, default="pending")
    language: Mapped[str] = mapped_column(String(16), default="")
    transcript: Mapped[str] = mapped_column(Text, default="")
    speakers: Mapped[dict] = mapped_column(JSON, default=dict)
    layers: Mapped[dict] = mapped_column(JSON, default=dict)
    tone: Mapped[dict] = mapped_column(JSON, default=dict)
    lead: Mapped[dict] = mapped_column(JSON, default=dict)
    model: Mapped[str] = mapped_column(String(128), default="")
    error: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TeamMessage(Base):
    """Internal team chat — daily rate reviews + field-executive voice/text updates.

    kind: rate_review | field_update | general
    status: pending -> approved | rejected  (two-option approval for field updates)
    """

    __tablename__ = "team_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    author_name: Mapped[str] = mapped_column(String(255), default="")
    author_role: Mapped[str] = mapped_column(String(64), default="sales")
    kind: Mapped[str] = mapped_column(String(32), index=True, default="general")
    body: Mapped[str] = mapped_column(Text, default="")
    transcript_id: Mapped[int] = mapped_column(Integer, default=0)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), index=True, default="posted")
    reviewed_by: Mapped[str] = mapped_column(String(255), default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
