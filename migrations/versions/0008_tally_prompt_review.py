"""Bring tally_sales + prompt_reviews under migration control.

These tables were originally created by ``Base.metadata.create_all`` at app
startup, so production databases already have them. The upgrade therefore
creates each table/index only when it is missing (idempotent), keeping SQLite
(CI), Postgres (Cloud SQL) and fresh installs all at the same head.

Revision ID: 0008_tally_prompt_review
Revises: 0007_instore_visits
Create Date: 2026-11-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_tally_prompt_review"
down_revision: Union[str, None] = "0007_instore_visits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _existing_indexes(table: str) -> set[str]:
    return {idx["name"] for idx in sa.inspect(op.get_bind()).get_indexes(table)}


def _create_tally_sales() -> None:
    if "tally_sales" in _existing_tables():
        return
    op.create_table(
        "tally_sales",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_file", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("source_row", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sale_date", sa.String(length=10), nullable=False, server_default=""),
        sa.Column("period", sa.String(length=7), nullable=False, server_default=""),
        sa.Column("buyer", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("buyer_address", sa.Text(), nullable=False, server_default=""),
        sa.Column("consignee", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("gstin", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("voucher_type", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("voucher_no", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("item_name", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("value", sa.Float(), nullable=False, server_default="0"),
        sa.Column("invoice_total", sa.Float(), nullable=False, server_default="0"),
        sa.Column("tax", sa.Float(), nullable=False, server_default="0"),
        sa.Column("synced_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("source_file", "source_row", name="uq_tally_sale_source_row"),
    )


def _create_prompt_reviews() -> None:
    if "prompt_reviews" in _existing_tables():
        return
    op.create_table(
        "prompt_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prompt_id", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("prompt_version", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("task", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("proposed_change", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("submitted_by", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("submitted_by_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reviewed_by", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("review_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def _ensure_indexes(table: str, columns: list[str]) -> None:
    existing = _existing_indexes(table)
    for column in columns:
        name = f"ix_{table}_{column}"
        if name not in existing:
            op.create_index(name, table, [column])


def upgrade() -> None:
    _create_tally_sales()
    _create_prompt_reviews()
    _ensure_indexes(
        "tally_sales",
        ["buyer", "gstin", "period", "sale_date", "source_file", "voucher_no"],
    )
    _ensure_indexes("prompt_reviews", ["prompt_id", "status", "submitted_by_id"])


def downgrade() -> None:
    tables = _existing_tables()
    if "prompt_reviews" in tables:
        op.drop_table("prompt_reviews")
    if "tally_sales" in tables:
        op.drop_table("tally_sales")
