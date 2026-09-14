"""outreach templates and campaigns

Revision ID: 0002_outreach
Revises: 0001_initial
Create Date: 2026-09-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_outreach"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "message_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("strategy", sa.String(length=32), nullable=False),
        sa.Column("funnel_stage", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("variables", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    for column in ("user_id", "name", "channel", "strategy"):
        op.create_index(f"ix_message_templates_{column}", "message_templates", [column])

    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("strategy", sa.String(length=32), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("ai_model", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("sent_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    for column in ("user_id", "channel", "status"):
        op.create_index(f"ix_campaigns_{column}", "campaigns", [column])

    op.create_table(
        "campaign_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("contact_id", sa.Integer(), nullable=False),
        sa.Column("to_address", sa.String(length=320), nullable=False),
        sa.Column("rendered_subject", sa.String(length=255), nullable=False),
        sa.Column("rendered_body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error", sa.String(length=512), nullable=False),
        sa.Column("provider_id", sa.String(length=128), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    for column in ("campaign_id", "user_id", "status"):
        op.create_index(f"ix_campaign_messages_{column}", "campaign_messages", [column])


def downgrade() -> None:
    for table in ("campaign_messages", "campaigns", "message_templates"):
        op.drop_table(table)
