from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
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
    role: Mapped[str] = mapped_column(String(32), default="sales", index=True)
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


class MailSyncState(Base):
    """Persistent IMAP sync checkpoint per connection (UIDVALIDITY/last UID/dedup).

    Backs incremental "new mail only" fetches; message_ids keeps the last
    processed Message-IDs so repeated UIDs never reprocess. Daily stats power the
    outreach dashboard KPIs (fetched/processed) without re-scanning GCS.
    """

    __tablename__ = "mail_sync_states"
    __table_args__ = (UniqueConstraint("connection_id", name="uq_mail_sync_connection"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    connection_id: Mapped[int] = mapped_column(Integer, index=True)
    mailbox: Mapped[str] = mapped_column(String(64), default="INBOX")
    uidvalidity: Mapped[int] = mapped_column(Integer, default=0)
    last_uid: Mapped[int] = mapped_column(Integer, default=0)
    message_ids: Mapped[list] = mapped_column(JSON, default=list)  # capped to recent ids
    stats: Mapped[dict] = mapped_column(JSON, default=dict)  # {"daily": {"YYYY-MM-DD": {...}}}
    gcs_last_prefix: Mapped[str] = mapped_column(String(512), default="")
    last_status: Mapped[str] = mapped_column(String(32), default="")
    last_error: Mapped[str] = mapped_column(String(512), default="")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


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


class GmailSyncState(Base):
    """Incremental Gmail history checkpoint per connected mailbox."""

    __tablename__ = "gmail_sync_states"
    __table_args__ = (UniqueConstraint("mailbox_id", name="uq_gmail_sync_mailbox"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    mailbox_id: Mapped[int] = mapped_column(Integer, index=True)
    history_id: Mapped[str] = mapped_column(String(64), default="")
    message_ids: Mapped[list] = mapped_column(JSON, default=list)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    last_status: Mapped[str] = mapped_column(String(32), default="")
    last_error: Mapped[str] = mapped_column(String(512), default="")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class GmailMessage(Base):
    """Normalized Gmail message for second-level conversation/attachment drilldown."""

    __tablename__ = "gmail_messages"
    __table_args__ = (
        UniqueConstraint("mailbox_id", "message_id", name="uq_gmail_mailbox_message"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    mailbox_id: Mapped[int] = mapped_column(Integer, index=True)
    message_id: Mapped[str] = mapped_column(String(128), index=True)
    thread_id: Mapped[str] = mapped_column(String(128), index=True, default="")
    rfc822_message_id: Mapped[str] = mapped_column(String(320), default="")
    subject: Mapped[str] = mapped_column(String(512), default="", index=True)
    sender: Mapped[str] = mapped_column(String(320), default="")
    sender_email: Mapped[str] = mapped_column(String(320), default="", index=True)
    recipients: Mapped[str] = mapped_column(Text, default="")
    date: Mapped[str] = mapped_column(String(128), default="")
    internal_date: Mapped[str] = mapped_column(String(64), default="")
    intent: Mapped[str] = mapped_column(String(64), default="", index=True)
    client: Mapped[str] = mapped_column(String(255), default="", index=True)
    context: Mapped[str] = mapped_column(Text, default="")
    snippet: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")
    labels: Mapped[list] = mapped_column(JSON, default=list)
    attachments: Mapped[list] = mapped_column(JSON, default=list)
    gcs_processed_path: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


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


class PromptReview(Base):
    """A human comment or refinement proposal for a weekly prompt sample."""

    __tablename__ = "prompt_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt_id: Mapped[str] = mapped_column(String(16), index=True, default="")
    prompt_version: Mapped[str] = mapped_column(String(32), default="")
    task: Mapped[str] = mapped_column(String(64), default="")
    comment: Mapped[str] = mapped_column(Text, default="")
    proposed_change: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), index=True, default="pending")
    submitted_by: Mapped[str] = mapped_column(String(255), default="")
    submitted_by_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    reviewed_by: Mapped[str] = mapped_column(String(255), default="")
    review_note: Mapped[str] = mapped_column(Text, default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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
    category: Mapped[str] = mapped_column(String(128), index=True, default="")
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
    image_url: Mapped[str] = mapped_column(String(1024), default="")
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
    contact_name: Mapped[str] = mapped_column(String(255), default="")
    to_address: Mapped[str] = mapped_column(String(320), default="")
    rendered_subject: Mapped[str] = mapped_column(String(255), default="")
    rendered_body: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str] = mapped_column(String(1024), default="")
    status: Mapped[str] = mapped_column(String(32), index=True, default="pending_review")
    error: Mapped[str] = mapped_column(String(512), default="")
    provider_id: Mapped[str] = mapped_column(String(128), default="")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ErpDispatch(Base):
    """Dispatch rows synced daily from the ERP report (ERP-V1/Reports -> Dispatch)."""

    __tablename__ = "erp_dispatch"
    __table_args__ = (
        UniqueConstraint("report_date", "dispatch_no", name="uq_erp_dispatch_day_no"),
    )

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


class TallySale(Base):
    """One Tally Sales Register line synced from gs://kalika_enterprises/kalika_sales2026/."""

    __tablename__ = "tally_sales"
    __table_args__ = (
        UniqueConstraint("source_file", "source_row", name="uq_tally_sale_source_row"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_file: Mapped[str] = mapped_column(String(255), index=True, default="")
    source_row: Mapped[int] = mapped_column(Integer, default=0)
    sale_date: Mapped[str] = mapped_column(String(10), index=True, default="")
    period: Mapped[str] = mapped_column(String(7), index=True, default="")
    buyer: Mapped[str] = mapped_column(String(255), index=True, default="")
    buyer_address: Mapped[str] = mapped_column(Text, default="")
    consignee: Mapped[str] = mapped_column(String(255), default="")
    gstin: Mapped[str] = mapped_column(String(32), index=True, default="")
    voucher_type: Mapped[str] = mapped_column(String(64), default="")
    voucher_no: Mapped[str] = mapped_column(String(64), index=True, default="")
    item_name: Mapped[str] = mapped_column(String(512), default="")
    quantity: Mapped[float] = mapped_column(Float, default=0)
    rate: Mapped[float] = mapped_column(Float, default=0)
    value: Mapped[float] = mapped_column(Float, default=0)
    invoice_total: Mapped[float] = mapped_column(Float, default=0)
    tax: Mapped[float] = mapped_column(Float, default=0)
    synced_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class IntegrationSetting(Base):
    """Key/value settings (YouTube API key, channel id, sync schedule...)."""

    __tablename__ = "integration_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


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


class Product(Base):
    """Sales product master."""

    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("user_id", "code", name="uq_product_user_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    code: Mapped[str] = mapped_column(String(64), index=True, default="")
    name: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str] = mapped_column(String(128), default="", index=True)
    unit: Mapped[str] = mapped_column(String(32), default="kg")
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ProductRate(Base):
    """A product rate submission with internal approval workflow."""

    __tablename__ = "product_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), index=True)
    rate: Mapped[float] = mapped_column(Float, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    unit: Mapped[str] = mapped_column(String(32), default="kg")
    effective_date: Mapped[str] = mapped_column(String(10), index=True, default="")
    status: Mapped[str] = mapped_column(String(16), index=True, default="pending")
    submitted_by: Mapped[str] = mapped_column(String(255), default="")
    approved_by: Mapped[str] = mapped_column(String(255), default="")
    source: Mapped[str] = mapped_column(String(32), default="manual", index=True)
    source_key: Mapped[str] = mapped_column(String(255), default="", index=True)
    gcs_path: Mapped[str] = mapped_column(String(512), default="")
    gcs_updated: Mapped[str] = mapped_column(String(64), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class CompanyVisit(Base):
    """A salesperson's company visit with optional GCS media attachments."""

    __tablename__ = "company_visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    contact_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    company: Mapped[str] = mapped_column(String(255), index=True, default="")
    contact_name: Mapped[str] = mapped_column(String(255), default="")
    contact_phone: Mapped[str] = mapped_column(String(64), default="")
    visit_date: Mapped[str] = mapped_column(String(10), index=True, default="")
    visit_type: Mapped[str] = mapped_column(String(32), index=True, default="in_person")
    sales_person: Mapped[str] = mapped_column(String(255), index=True, default="")
    purpose: Mapped[str] = mapped_column(String(512), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    # Field-executive sample: who/where we met, what was discussed earlier,
    # the mail/chat trail, and a map pin for route planning.
    meet_person: Mapped[str] = mapped_column(String(255), default="")
    meet_home_location: Mapped[str] = mapped_column(String(255), default="")
    previous_discussion: Mapped[str] = mapped_column(Text, default="")
    mail_chat_details: Mapped[str] = mapped_column(Text, default="")
    map_location: Mapped[str] = mapped_column(String(512), default="")
    outcome: Mapped[str] = mapped_column(String(64), default="")
    next_action: Mapped[str] = mapped_column(Text, default="")
    follow_up_date: Mapped[str] = mapped_column(String(10), default="")
    status: Mapped[str] = mapped_column(String(32), index=True, default="completed")
    media: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class SocialMetric(Base):
    """A platform metric snapshot (real API value or an explicit sync status)."""

    __tablename__ = "social_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    platform: Mapped[str] = mapped_column(String(32), index=True, default="")
    metric: Mapped[str] = mapped_column(String(64), index=True, default="")
    value: Mapped[float] = mapped_column(Float, default=0)
    period: Mapped[str] = mapped_column(String(16), index=True, default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    captured_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MarketingCompany(Base):
    """A company from the Kalika marketing list.

    The marketing workbook holds three overlapping company lists and a calling-log
    sheet. Rows are keyed by a normalised company name per user so the same
    company merged from multiple sheets collapses to a single row.
    """

    __tablename__ = "marketing_companies"
    __table_args__ = (
        UniqueConstraint("user_id", "company_key", name="uq_marketing_company_user_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)

    company: Mapped[str] = mapped_column(String(255), index=True, default="")
    company_key: Mapped[str] = mapped_column(String(255), index=True, default="")
    contact_name: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(255), default="")
    email: Mapped[str] = mapped_column(String(320), default="")
    category: Mapped[str] = mapped_column(String(255), default="")
    call_status: Mapped[str] = mapped_column(String(255), default="")
    requirements: Mapped[str] = mapped_column(Text, default="")
    funnel_stage: Mapped[str] = mapped_column(String(32), default="awareness", index=True)
    sales_progress: Mapped[str] = mapped_column(String(48), default="new", index=True)
    next_action: Mapped[str] = mapped_column(Text, default="")
    follow_up_date: Mapped[str] = mapped_column(String(10), default="", index=True)
    source_sheet: Mapped[str] = mapped_column(String(255), default="")
    source_file: Mapped[str] = mapped_column(String(255), index=True, default="")
    source_row: Mapped[int] = mapped_column(Integer, default=0)
    marketing_approved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    source_reference: Mapped[str] = mapped_column(String(512), default="")
    segment: Mapped[str] = mapped_column(String(64), default="", index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class TaskApproval(Base):
    """A backend subtask awaiting human acceptance before it is processed.

    Subtasks are proposed either by the system (LLM-driven data-refinement
    suggestions, with a model confidence score) or by a user, and only run after
    an admin (ai.solutions) approves them. This keeps the cost-effective Gemma /
    Gemini-Flash pipeline under human review.
    """

    __tablename__ = "task_approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    title: Mapped[str] = mapped_column(String(255), default="")
    area: Mapped[str] = mapped_column(String(64), index=True, default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(32), default="user")  # user | llm | system
    status: Mapped[str] = mapped_column(String(16), index=True, default="pending")
    decided_by: Mapped[str] = mapped_column(String(255), default="")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class OutreachSmartTemplate(Base):
    """Approved WhatsApp template with personalised, rate-aware body content."""

    __tablename__ = "outreach_smart_templates"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_outreach_smart_template_user_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    name: Mapped[str] = mapped_column(String(128), index=True)
    category: Mapped[str] = mapped_column(String(64), default="", index=True)
    body: Mapped[str] = mapped_column(Text, default="")
    variables: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), index=True, default="draft")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str] = mapped_column(String(255), default="")
    approved_by: Mapped[str] = mapped_column(String(255), default="")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class OutreachWhatsAppCampaign(Base):
    """A WhatsApp outreach run that is reviewed before any message is sent."""

    __tablename__ = "outreach_whatsapp_campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    name: Mapped[str] = mapped_column(String(160), index=True)
    template_id: Mapped[int] = mapped_column(Integer, index=True)
    segment: Mapped[str] = mapped_column(String(64), default="", index=True)
    rate_ids: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(24), index=True, default="pending_review")
    total: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    delivered_count: Mapped[int] = mapped_column(Integer, default=0)
    read_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str] = mapped_column(String(255), default="")
    approved_by: Mapped[str] = mapped_column(String(255), default="")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class OutreachWhatsAppMessage(Base):
    """One personalised WhatsApp message with delivery/read engagement state."""

    __tablename__ = "outreach_whatsapp_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    campaign_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("outreach_whatsapp_campaigns.id"), index=True
    )
    contact_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    contact_type: Mapped[str] = mapped_column(String(32), default="marketing_companies")
    phone: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    company: Mapped[str] = mapped_column(String(255), default="")
    rendered_body: Mapped[str] = mapped_column(Text, default="")
    links: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), index=True, default="pending_review")
    provider_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    track_token: Mapped[str] = mapped_column(String(64), default="", index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class OutreachEngagementEvent(Base):
    """Provider or landing-page engagement event for an outreach message."""

    __tablename__ = "outreach_engagement_events"
    __table_args__ = (
        UniqueConstraint("provider_event_id", name="uq_outreach_engagement_provider_event"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    message_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("outreach_whatsapp_messages.id"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    provider_event_id: Mapped[str | None] = mapped_column(
        String(128), default=None, nullable=True, index=True
    )
    target_url: Mapped[str] = mapped_column(String(1024), default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AdminFeatureFlag(Base):
    """Isolated sales-ops/studio feature flag; existing ERP flags are untouched."""

    __tablename__ = "admin_feature_flags"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    daily_limit: Mapped[int] = mapped_column(Integer, default=0)
    updated_by: Mapped[str] = mapped_column(String(255), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class SalesOpsDailyCounter(Base):
    """Per-day safe automation counters for WhatsApp and YouTube quota."""

    __tablename__ = "sales_ops_daily_counters"

    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    whatsapp_sent: Mapped[int] = mapped_column(Integer, default=0)
    yt_quota_used: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class SalesOpsBarcodeScan(Base):
    """Mobile camera barcode + confirmed weight event for ERP follow-up."""

    __tablename__ = "sales_ops_barcode_scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    barcode: Mapped[str] = mapped_column(String(128), index=True)
    sku: Mapped[str] = mapped_column(String(64), default="", index=True)
    net_weight_kg: Mapped[float] = mapped_column(Float, default=0.0)
    customer_name: Mapped[str] = mapped_column(String(255), default="")
    customer_email: Mapped[str] = mapped_column(String(255), default="")
    customer_whatsapp: Mapped[str] = mapped_column(String(64), default="")
    trigger_followup: Mapped[bool] = mapped_column(Boolean, default=True)
    followup_status: Mapped[str] = mapped_column(String(32), index=True, default="LOGGED")
    gcs_uri: Mapped[str] = mapped_column(String(512), default="")
    created_by: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class SalesOpsDispatch(Base):
    """Human-reviewed omni-channel campaign preview/dispatch record."""

    __tablename__ = "sales_ops_dispatches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    contact_name: Mapped[str] = mapped_column(String(255), default="")
    company_name: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(64), default="", index=True)
    email: Mapped[str] = mapped_column(String(255), default="")
    channels: Mapped[list] = mapped_column(JSON, default=list)
    preview: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), index=True, default="pending_review")
    approved_by: Mapped[str] = mapped_column(String(255), default="")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class SalesOpsYouTubeSignal(Base):
    """Quota-guarded YouTube discovery result and extracted hook pattern."""

    __tablename__ = "sales_ops_youtube_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query: Mapped[str] = mapped_column(String(255), index=True)
    video_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    title: Mapped[str] = mapped_column(String(512), default="")
    video_url: Mapped[str] = mapped_column(String(1024), default="")
    channel: Mapped[str] = mapped_column(String(255), default="")
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    hook_pattern: Mapped[str] = mapped_column(Text, default="")
    source_mode: Mapped[str] = mapped_column(String(32), default="deterministic_stub")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class StudioRefinement(Base):
    """Prompt refinement result with model/cost provenance for admin review."""

    __tablename__ = "studio_refinements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    prompt_text: Mapped[str] = mapped_column(Text, default="")
    refined_prompt: Mapped[str] = mapped_column(Text, default="")
    model_choice: Mapped[str] = mapped_column(String(32), index=True)
    template_path: Mapped[str] = mapped_column(String(512), default="")
    aspect_ratio: Mapped[str] = mapped_column(String(8), default="16:9")
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    source_mode: Mapped[str] = mapped_column(String(32), default="deterministic_fallback")
    gcs_uri: Mapped[str] = mapped_column(String(512), default="")
    created_by: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
