"""add marketing funnel progress and follow-up fields

Revision ID: 0010_marketing_pipeline
Revises: 0009_marketing_companies
Create Date: 2026-11-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_marketing_pipeline"
down_revision: Union[str, None] = "0009_marketing_companies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if "marketing_companies" not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns("marketing_companies")}


def upgrade() -> None:
    columns = _columns()
    if not columns:
        return
    additions = (
        ("funnel_stage", sa.String(length=32), "awareness"),
        ("sales_progress", sa.String(length=48), "new"),
        ("next_action", sa.Text(), ""),
        ("follow_up_date", sa.String(length=10), ""),
    )
    for name, column_type, default in additions:
        if name not in columns:
            op.add_column(
                "marketing_companies",
                sa.Column(name, column_type, nullable=False, server_default=default),
            )
    indexes = {
        index["name"] for index in sa.inspect(op.get_bind()).get_indexes("marketing_companies")
    }
    for name in ("funnel_stage", "sales_progress", "follow_up_date"):
        index_name = f"ix_marketing_companies_{name}"
        if index_name not in indexes:
            op.create_index(index_name, "marketing_companies", [name])


def downgrade() -> None:
    columns = _columns()
    if not columns:
        return
    indexes = {
        index["name"] for index in sa.inspect(op.get_bind()).get_indexes("marketing_companies")
    }
    for name in ("funnel_stage", "sales_progress", "follow_up_date"):
        index_name = f"ix_marketing_companies_{name}"
        if index_name in indexes:
            op.drop_index(index_name, table_name="marketing_companies")
    for name in ("follow_up_date", "next_action", "sales_progress", "funnel_stage"):
        if name in columns:
            op.drop_column("marketing_companies", name)
