"""instore mail insights + field-executive visit fields

Revision ID: 0007_instore_visits
Revises: 0006_sales_bi
Create Date: 2026-11-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_instore_visits"
down_revision: Union[str, None] = "0006_sales_bi"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column_backfill(table: str, column: str, col_type: sa.types.TypeEngine, fill: str) -> None:
    op.add_column(table, sa.Column(column, col_type, nullable=True))
    op.execute(sa.text(f"UPDATE {table} SET {column}='{fill}' WHERE {column} IS NULL"))
    with op.batch_alter_table(table) as batch_op:
        batch_op.alter_column(column, existing_type=col_type, nullable=False)


def upgrade() -> None:
    _add_column_backfill("company_visits", "meet_person", sa.String(length=255), "")
    _add_column_backfill("company_visits", "meet_home_location", sa.String(length=255), "")
    _add_column_backfill("company_visits", "previous_discussion", sa.Text(), "")
    _add_column_backfill("company_visits", "mail_chat_details", sa.Text(), "")
    _add_column_backfill("company_visits", "map_location", sa.String(length=512), "")


def downgrade() -> None:
    for column in (
        "map_location",
        "mail_chat_details",
        "previous_discussion",
        "meet_home_location",
        "meet_person",
    ):
        with op.batch_alter_table("company_visits") as batch_op:
            batch_op.drop_column(column)
