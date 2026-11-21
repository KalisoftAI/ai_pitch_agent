"""add gmail drilldown state and ERP rate provenance

Revision ID: 0015_gmail_drilldown_and_erp_rates
Revises: 0014_sales_ops_studio
Create Date: 2026-11-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_gmail_drilldown_and_erp_rates"
down_revision: Union[str, None] = "0014_sales_ops_studio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    return column in {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if not _has_table("gmail_sync_states"):
        op.create_table(
            "gmail_sync_states",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("mailbox_id", sa.Integer(), nullable=False),
            sa.Column("history_id", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("message_ids", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("stats", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("last_status", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("last_error", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("last_sync_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("mailbox_id", name="uq_gmail_sync_mailbox"),
        )
        op.create_index("ix_gmail_sync_states_mailbox_id", "gmail_sync_states", ["mailbox_id"])
        op.create_index("ix_gmail_sync_states_user_id", "gmail_sync_states", ["user_id"])

    if not _has_table("gmail_messages"):
        op.create_table(
            "gmail_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("mailbox_id", sa.Integer(), nullable=False),
            sa.Column("message_id", sa.String(length=128), nullable=False),
            sa.Column("thread_id", sa.String(length=128), nullable=False, server_default=""),
            sa.Column("rfc822_message_id", sa.String(length=320), nullable=False, server_default=""),
            sa.Column("subject", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("sender", sa.String(length=320), nullable=False, server_default=""),
            sa.Column("sender_email", sa.String(length=320), nullable=False, server_default=""),
            sa.Column("recipients", sa.Text(), nullable=False, server_default=""),
            sa.Column("date", sa.String(length=128), nullable=False, server_default=""),
            sa.Column("internal_date", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("intent", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("client", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("context", sa.Text(), nullable=False, server_default=""),
            sa.Column("snippet", sa.Text(), nullable=False, server_default=""),
            sa.Column("body", sa.Text(), nullable=False, server_default=""),
            sa.Column("labels", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("attachments", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("gcs_processed_path", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("mailbox_id", "message_id", name="uq_gmail_mailbox_message"),
        )
        for column in ("user_id", "mailbox_id", "message_id", "thread_id", "subject", "sender_email", "intent", "client"):
            op.create_index(f"ix_gmail_messages_{column}", "gmail_messages", [column])

    if _has_table("product_rates"):
        for column, ddl in (
            ("source", "VARCHAR(32) NOT NULL DEFAULT 'manual'"),
            ("source_key", "VARCHAR(255) NOT NULL DEFAULT ''"),
            ("gcs_path", "VARCHAR(512) NOT NULL DEFAULT ''"),
            ("gcs_updated", "VARCHAR(64) NOT NULL DEFAULT ''"),
        ):
            if not _has_column("product_rates", column):
                op.execute(f"ALTER TABLE product_rates ADD COLUMN {column} {ddl}")
        for column in ("source", "source_key"):
            index = f"ix_product_rates_{column}"
            if index not in {idx["name"] for idx in sa.inspect(op.get_bind()).get_indexes("product_rates")}:
                op.create_index(index, "product_rates", [column])


def downgrade() -> None:
    for table in ("gmail_messages", "gmail_sync_states"):
        if _has_table(table):
            op.drop_table(table)
