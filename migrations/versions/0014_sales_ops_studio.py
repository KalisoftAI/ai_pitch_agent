"""add isolated sales ops and studio tables

Revision ID: 0014_sales_ops_studio
Revises: 0013_campaign_message_clicked
Create Date: 2026-11-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_sales_ops_studio"
down_revision: Union[str, None] = "0013_campaign_message_clicked"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has_table("admin_feature_flags"):
        op.create_table(
            "admin_feature_flags",
            sa.Column("name", sa.String(length=64), primary_key=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("daily_limit", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_by", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_admin_feature_flags_enabled", "admin_feature_flags", ["enabled"])

    if not _has_table("sales_ops_daily_counters"):
        op.create_table(
            "sales_ops_daily_counters",
            sa.Column("day", sa.String(length=10), primary_key=True),
            sa.Column("whatsapp_sent", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("yt_quota_used", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    if not _has_table("sales_ops_barcode_scans"):
        op.create_table(
            "sales_ops_barcode_scans",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("barcode", sa.String(length=128), nullable=False),
            sa.Column("sku", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("net_weight_kg", sa.Float(), nullable=False, server_default="0"),
            sa.Column("customer_name", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("customer_email", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("customer_whatsapp", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("trigger_followup", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column(
                "followup_status", sa.String(length=32), nullable=False, server_default="LOGGED"
            ),
            sa.Column("gcs_uri", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("created_by", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        for column in ("user_id", "barcode", "sku", "followup_status", "created_at"):
            op.create_index(
                f"ix_sales_ops_barcode_scans_{column}", "sales_ops_barcode_scans", [column]
            )

    if not _has_table("sales_ops_dispatches"):
        op.create_table(
            "sales_ops_dispatches",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("contact_name", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("company_name", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("phone", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("email", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("channels", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("preview", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column(
                "status", sa.String(length=32), nullable=False, server_default="pending_review"
            ),
            sa.Column("approved_by", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        for column in ("user_id", "phone", "status", "created_at"):
            op.create_index(f"ix_sales_ops_dispatches_{column}", "sales_ops_dispatches", [column])

    if not _has_table("sales_ops_youtube_signals"):
        op.create_table(
            "sales_ops_youtube_signals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("query", sa.String(length=255), nullable=False),
            sa.Column("video_id", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("title", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("video_url", sa.String(length=1024), nullable=False, server_default=""),
            sa.Column("channel", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("hook_pattern", sa.Text(), nullable=False, server_default=""),
            sa.Column(
                "source_mode",
                sa.String(length=32),
                nullable=False,
                server_default="deterministic_stub",
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        for column in ("query", "video_id", "created_at"):
            op.create_index(
                f"ix_sales_ops_youtube_signals_{column}", "sales_ops_youtube_signals", [column]
            )

    if not _has_table("studio_refinements"):
        op.create_table(
            "studio_refinements",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("prompt_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("refined_prompt", sa.Text(), nullable=False, server_default=""),
            sa.Column("model_choice", sa.String(length=32), nullable=False),
            sa.Column("template_path", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("aspect_ratio", sa.String(length=8), nullable=False, server_default="16:9"),
            sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
            sa.Column(
                "source_mode",
                sa.String(length=32),
                nullable=False,
                server_default="deterministic_fallback",
            ),
            sa.Column("gcs_uri", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("created_by", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        for column in ("user_id", "model_choice", "created_at"):
            op.create_index(f"ix_studio_refinements_{column}", "studio_refinements", [column])


def downgrade() -> None:
    for table in (
        "studio_refinements",
        "sales_ops_youtube_signals",
        "sales_ops_dispatches",
        "sales_ops_barcode_scans",
        "sales_ops_daily_counters",
        "admin_feature_flags",
    ):
        if _has_table(table):
            op.drop_table(table)
