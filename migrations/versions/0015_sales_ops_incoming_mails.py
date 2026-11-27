"""add sales ops incoming mail records and sync checkpoint

Revision ID: 0015_sales_ops_incoming_mails
Revises: 0014_sales_ops_studio
Create Date: 2026-11-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_sales_ops_incoming_mails"
down_revision: Union[str, None] = "0014_sales_ops_studio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has_table("sales_ops_mail_sync_states"):
        op.create_table(
            "sales_ops_mail_sync_states",
            sa.Column("mailbox", sa.String(length=320), primary_key=True),
            sa.Column("last_uid", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("cursor_uid", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("backfill_complete", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("last_sync_at", sa.DateTime(), nullable=True),
            sa.Column("last_status", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("last_error", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("fetched_total", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("new_total", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    if not _has_table("sales_ops_incoming_mails"):
        op.create_table(
            "sales_ops_incoming_mails",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("mailbox", sa.String(length=320), nullable=False, server_default=""),
            sa.Column("company", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("sender_name", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("sender_email", sa.String(length=320), nullable=False, server_default=""),
            sa.Column("sender_raw", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("subject", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("received_at", sa.DateTime(), nullable=False),
            sa.Column("received_date", sa.String(length=10), nullable=False, server_default=""),
            sa.Column("received_time", sa.String(length=8), nullable=False, server_default=""),
            sa.Column("body_snippet", sa.Text(), nullable=False, server_default=""),
            sa.Column("ai_summary", sa.Text(), nullable=False, server_default=""),
            sa.Column(
                "summary_source",
                sa.String(length=64),
                nullable=False,
                server_default="deterministic_fallback",
            ),
            sa.Column("message_id", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("imap_uid", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("dedup_key", sa.String(length=64), nullable=False),
            sa.Column("gcs_uri", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("created_by", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("dedup_key", name="uq_sales_ops_incoming_mails_dedup"),
        )
        for column in ("mailbox", "company", "sender_email", "received_at", "received_date", "created_at"):
            op.create_index(
                f"ix_sales_ops_incoming_mails_{column}", "sales_ops_incoming_mails", [column]
            )
        op.create_index(
            "ix_sales_ops_incoming_mails_imap_uid", "sales_ops_incoming_mails", ["imap_uid"]
        )


def downgrade() -> None:
    for table in ("sales_ops_incoming_mails", "sales_ops_mail_sync_states"):
        if _has_table(table):
            op.drop_table(table)
