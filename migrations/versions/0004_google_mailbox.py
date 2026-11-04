from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_google_mailbox"
down_revision: Union[str, None] = "0003_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "google_mailboxes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("email_address", sa.String(length=320), nullable=False),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=False),
        sa.Column("token_expiry", sa.DateTime(), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("is_connected", sa.Boolean(), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "email_address", name="uq_google_mailbox_user_email"),
    )
    op.create_index("ix_google_mailboxes_user_id", "google_mailboxes", ["user_id"])
    op.create_index("ix_google_mailboxes_email_address", "google_mailboxes", ["email_address"])


def downgrade() -> None:
    op.drop_index("ix_google_mailboxes_email_address", table_name="google_mailboxes")
    op.drop_index("ix_google_mailboxes_user_id", table_name="google_mailboxes")
    op.drop_table("google_mailboxes")
