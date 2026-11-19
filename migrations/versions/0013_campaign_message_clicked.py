"""add campaign message click tracking

Revision ID: 0013_campaign_message_clicked
Revises: 0012_outreach_whatsapp
Create Date: 2026-11-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_campaign_message_clicked"
down_revision: Union[str, None] = "0012_outreach_whatsapp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, name: str) -> bool:
    return name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if not _has_column("campaign_messages", "clicked_at"):
        op.add_column("campaign_messages", sa.Column("clicked_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    if _has_column("campaign_messages", "clicked_at"):
        op.drop_column("campaign_messages", "clicked_at")
