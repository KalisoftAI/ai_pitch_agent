"""add outreach whatsapp automation tables

Revision ID: 0012_outreach_whatsapp
Revises: 0011_campaign_contact_name
Create Date: 2026-11-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_outreach_whatsapp"
down_revision: Union[str, None] = "0011_campaign_contact_name"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if not _has_table("outreach_smart_templates"):
        op.create_table(
            "outreach_smart_templates",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("category", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("body", sa.Text(), nullable=False, server_default=""),
            sa.Column("variables", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_by", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("approved_by", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "name", name="uq_outreach_smart_template_user_name"),
        )
        op.create_index("ix_outreach_smart_templates_user_id", "outreach_smart_templates", ["user_id"])
        op.create_index("ix_outreach_smart_templates_name", "outreach_smart_templates", ["name"])
        op.create_index("ix_outreach_smart_templates_status", "outreach_smart_templates", ["status"])
        op.create_index("ix_outreach_smart_templates_category", "outreach_smart_templates", ["category"])

    if not _has_table("outreach_whatsapp_campaigns"):
        op.create_table(
            "outreach_whatsapp_campaigns",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("template_id", sa.Integer(), nullable=False),
            sa.Column("segment", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("rate_ids", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="pending_review"),
            sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("sent_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("delivered_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("read_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_by", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("approved_by", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        for column in ("user_id", "name", "template_id", "segment", "status"):
            op.create_index(f"ix_outreach_whatsapp_campaigns_{column}", "outreach_whatsapp_campaigns", [column])

    if not _has_table("outreach_whatsapp_messages"):
        op.create_table(
            "outreach_whatsapp_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column(
                "campaign_id",
                sa.Integer(),
                sa.ForeignKey("outreach_whatsapp_campaigns.id"),
                nullable=False,
            ),
            sa.Column("contact_id", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "contact_type",
                sa.String(length=32),
                nullable=False,
                server_default="marketing_companies",
            ),
            sa.Column("phone", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("company", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("rendered_body", sa.Text(), nullable=False, server_default=""),
            sa.Column("links", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="pending_review"),
            sa.Column("provider_id", sa.String(length=128), nullable=False, server_default=""),
            sa.Column("track_token", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
            sa.Column("delivered_at", sa.DateTime(), nullable=True),
            sa.Column("read_at", sa.DateTime(), nullable=True),
            sa.Column("failed_at", sa.DateTime(), nullable=True),
            sa.Column("error", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        for column in ("user_id", "campaign_id", "contact_id", "phone", "status", "provider_id", "track_token"):
            op.create_index(f"ix_outreach_whatsapp_messages_{column}", "outreach_whatsapp_messages", [column])

    if not _has_table("outreach_engagement_events"):
        op.create_table(
            "outreach_engagement_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column(
                "message_id",
                sa.Integer(),
                sa.ForeignKey("outreach_whatsapp_messages.id"),
                nullable=False,
            ),
            sa.Column("event_type", sa.String(length=32), nullable=False),
            sa.Column("provider_event_id", sa.String(length=128), nullable=True),
            sa.Column("target_url", sa.String(length=1024), nullable=False, server_default=""),
            sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("meta", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("occurred_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("provider_event_id", name="uq_outreach_engagement_provider_event"),
        )
        for column in ("user_id", "message_id", "event_type", "occurred_at"):
            op.create_index(f"ix_outreach_engagement_events_{column}", "outreach_engagement_events", [column])

    if _has_table("marketing_companies"):
        for name, column_type, server_default in (
            ("marketing_approved", sa.Boolean(), sa.false()),
            ("source_reference", sa.String(length=512), ""),
            ("segment", sa.String(length=64), ""),
        ):
            if not _has_column("marketing_companies", name):
                op.add_column(
                    "marketing_companies",
                    sa.Column(name, column_type, nullable=False, server_default=server_default),
                )


def downgrade() -> None:
    for name in ("segment", "source_reference", "marketing_approved"):
        if _has_column("marketing_companies", name):
            op.drop_column("marketing_companies", name)
    for table in (
        "outreach_engagement_events",
        "outreach_whatsapp_messages",
        "outreach_whatsapp_campaigns",
        "outreach_smart_templates",
    ):
        if _has_table(table):
            op.drop_table(table)
