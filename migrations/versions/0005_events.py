from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_events"
down_revision: Union[str, None] = "0004_google_mailbox"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("event_url", sa.String(length=512), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=True),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("when_text", sa.String(length=512), nullable=False),
        sa.Column("location", sa.String(length=512), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("organiser", sa.String(length=255), nullable=False),
        sa.Column("attendance", sa.String(length=128), nullable=False),
        sa.Column("about", sa.Text(), nullable=False),
        sa.Column("todo", sa.Text(), nullable=False),
        sa.Column("source_sheet", sa.String(length=64), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "fingerprint", name="uq_event_user_fingerprint"),
    )
    op.create_index("ix_events_user_id", "events", ["user_id"])
    op.create_index("ix_events_title", "events", ["title"])
    op.create_index("ix_events_starts_at", "events", ["starts_at"])
    op.create_index("ix_events_mode", "events", ["mode"])
    op.create_index("ix_events_status", "events", ["status"])

    op.create_table(
        "event_recipients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("source_sheet", sa.String(length=64), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "phone", name="uq_event_recipient_user_phone"),
    )
    op.create_index("ix_event_recipients_user_id", "event_recipients", ["user_id"])
    op.create_index("ix_event_recipients_phone", "event_recipients", ["phone"])
    op.create_index("ix_event_recipients_company", "event_recipients", ["company"])

    op.create_table(
        "event_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("recipient_id", sa.Integer(), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["recipient_id"], ["event_recipients.id"]),
    )
    op.create_index("ix_event_messages_user_id", "event_messages", ["user_id"])
    op.create_index("ix_event_messages_event_id", "event_messages", ["event_id"])
    op.create_index("ix_event_messages_recipient_id", "event_messages", ["recipient_id"])
    op.create_index("ix_event_messages_status", "event_messages", ["status"])
    op.create_index("ix_event_messages_scheduled_at", "event_messages", ["scheduled_at"])


def downgrade() -> None:
    op.drop_index("ix_event_messages_scheduled_at", table_name="event_messages")
    op.drop_index("ix_event_messages_status", table_name="event_messages")
    op.drop_index("ix_event_messages_recipient_id", table_name="event_messages")
    op.drop_index("ix_event_messages_event_id", table_name="event_messages")
    op.drop_index("ix_event_messages_user_id", table_name="event_messages")
    op.drop_table("event_messages")

    op.drop_index("ix_event_recipients_company", table_name="event_recipients")
    op.drop_index("ix_event_recipients_phone", table_name="event_recipients")
    op.drop_index("ix_event_recipients_user_id", table_name="event_recipients")
    op.drop_table("event_recipients")

    op.drop_index("ix_events_status", table_name="events")
    op.drop_index("ix_events_mode", table_name="events")
    op.drop_index("ix_events_starts_at", table_name="events")
    op.drop_index("ix_events_title", table_name="events")
    op.drop_index("ix_events_user_id", table_name="events")
    op.drop_table("events")
