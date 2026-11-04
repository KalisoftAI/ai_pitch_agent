"""marketing_companies table

Revision ID: 0009_marketing_companies
Revises: 0008_tally_prompt_review
Create Date: 2026-11-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_marketing_companies"
down_revision: Union[str, None] = "0008_tally_prompt_review"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _existing_indexes(table: str) -> set[str]:
    return {idx["name"] for idx in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if "marketing_companies" in _existing_tables():
        return
    op.create_table(
        "marketing_companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("company", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("company_key", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("contact_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("phone", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("email", sa.String(length=320), nullable=False, server_default=""),
        sa.Column("category", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("call_status", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("requirements", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_sheet", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("source_row", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "user_id", "company_key", name="uq_marketing_company_user_key"
        ),
    )
    existing = _existing_indexes("marketing_companies")
    for column in ("user_id", "company", "company_key"):
        name = f"ix_marketing_companies_{column}"
        if name not in existing:
            op.create_index(name, "marketing_companies", [column])


def downgrade() -> None:
    if "marketing_companies" in _existing_tables():
        op.drop_table("marketing_companies")
