"""align migrations with current ops and outreach models

Revision ID: 0016_ops_mail_and_marketing_alignment
Revises: 0015_gmail_drilldown_and_erp_rates
Create Date: 2026-11-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_ops_mail_and_marketing_alignment"
down_revision: Union[str, None] = "0015_gmail_drilldown_and_erp_rates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    return column in {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def _has_index(table: str, index: str) -> bool:
    return index in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if not _has_table("mail_sync_states"):
        op.create_table(
            "mail_sync_states",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("connection_id", sa.Integer(), nullable=False),
            sa.Column("mailbox", sa.String(length=64), nullable=False, server_default="INBOX"),
            sa.Column("uidvalidity", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_uid", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("message_ids", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("stats", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("gcs_last_prefix", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("last_status", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("last_error", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("last_sync_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("connection_id", name="uq_mail_sync_connection"),
        )
    if _has_table("mail_sync_states"):
        for column in ("connection_id", "user_id"):
            index = f"ix_mail_sync_states_{column}"
            if not _has_index("mail_sync_states", index):
                op.create_index(index, "mail_sync_states", [column])

    if not _has_table("task_approvals"):
        op.create_table(
            "task_approvals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("title", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("area", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("detail", sa.Text(), nullable=False, server_default=""),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
            sa.Column("source", sa.String(length=32), nullable=False, server_default="user"),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
            sa.Column("decided_by", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("decided_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
    if _has_table("task_approvals"):
        for column in ("user_id", "area", "status"):
            index = f"ix_task_approvals_{column}"
            if not _has_index("task_approvals", index):
                op.create_index(index, "task_approvals", [column])

    for table in ("campaign_messages", "campaigns"):
        if _has_table(table) and not _has_column(table, "image_url"):
            op.add_column(
                table,
                sa.Column("image_url", sa.String(length=1024), nullable=False, server_default=""),
            )

    if _has_table("marketing_companies"):
        if not _has_column("marketing_companies", "source_file"):
            op.add_column(
                "marketing_companies",
                sa.Column("source_file", sa.String(length=255), nullable=False, server_default=""),
            )
        with op.batch_alter_table("marketing_companies", recreate="always") as batch:
            for column in ("phone", "call_status", "source_sheet"):
                if column in {
                    item["name"]
                    for item in sa.inspect(op.get_bind()).get_columns("marketing_companies")
                }:
                    batch.alter_column(
                        column,
                        type_=sa.String(length=255),
                        existing_type=sa.String(length=64),
                        existing_nullable=False,
                        existing_server_default="",
                    )
        for column in ("marketing_approved", "segment", "source_file"):
            index = f"ix_marketing_companies_{column}"
            if not _has_index("marketing_companies", index):
                op.create_index(index, "marketing_companies", [column])

    if _has_table("message_templates"):
        if not _has_column("message_templates", "category"):
            op.add_column(
                "message_templates",
                sa.Column("category", sa.String(length=128), nullable=False, server_default=""),
            )
        if not _has_index("message_templates", "ix_message_templates_category"):
            op.create_index("ix_message_templates_category", "message_templates", ["category"])

    if _has_table("outreach_engagement_events"):
        index = "ix_outreach_engagement_events_provider_event_id"
        if not _has_index("outreach_engagement_events", index):
            op.create_index(index, "outreach_engagement_events", ["provider_event_id"])


def downgrade() -> None:
    if _has_table("outreach_engagement_events"):
        index = "ix_outreach_engagement_events_provider_event_id"
        if _has_index("outreach_engagement_events", index):
            op.drop_index(index, table_name="outreach_engagement_events")
    if _has_table("message_templates"):
        if _has_index("message_templates", "ix_message_templates_category"):
            op.drop_index("ix_message_templates_category", table_name="message_templates")
        if _has_column("message_templates", "category"):
            op.drop_column("message_templates", "category")
    if _has_table("marketing_companies"):
        for column in ("marketing_approved", "segment", "source_file"):
            index = f"ix_marketing_companies_{column}"
            if _has_index("marketing_companies", index):
                op.drop_index(index, table_name="marketing_companies")
        if _has_column("marketing_companies", "source_file"):
            op.drop_column("marketing_companies", "source_file")
        with op.batch_alter_table("marketing_companies", recreate="always") as batch:
            for column in ("phone", "call_status", "source_sheet"):
                if column in {
                    item["name"]
                    for item in sa.inspect(op.get_bind()).get_columns("marketing_companies")
                }:
                    batch.alter_column(
                        column,
                        type_=sa.String(length=64),
                        existing_type=sa.String(length=255),
                        existing_nullable=False,
                        existing_server_default="",
                    )
    for table in ("campaigns", "campaign_messages"):
        if _has_table(table) and _has_column(table, "image_url"):
            op.drop_column(table, "image_url")
    for table in ("task_approvals", "mail_sync_states"):
        if _has_table(table):
            op.drop_table(table)
