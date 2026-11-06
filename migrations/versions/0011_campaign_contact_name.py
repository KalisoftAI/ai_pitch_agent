"""add contact_name + opened_at to campaign_messages

Revision ID: 0011_campaign_contact_name
Revises: 0010_marketing_pipeline
Create Date: 2026-11-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_campaign_contact_name"
down_revision: Union[str, None] = "0010_marketing_pipeline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if "campaign_messages" not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns("campaign_messages")}


def upgrade() -> None:
    columns = _columns()
    if not columns:
        return
    for name, column_type in (
        ("contact_name", sa.String(length=255)),
        ("opened_at", sa.DateTime()),
    ):
        if name not in columns:
            op.add_column(
                "campaign_messages",
                sa.Column(name, column_type, nullable=False if name == "contact_name" else True,
                          server_default="" if name == "contact_name" else None),
            )


def downgrade() -> None:
    columns = _columns()
    for name in ("opened_at", "contact_name"):
        if name in columns:
            op.drop_column("campaign_messages", name)
