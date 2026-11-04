"""sales bi + missing tables: products, product rates, company visits, social metrics,
erp dispatch/orders, integration settings, sync runs, journey events, voice
transcripts, team messages; users.role + users.password_hash

Revision ID: 0006_sales_bi
Revises: 0005_events
Create Date: 2026-10-31
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_sales_bi"
down_revision: Union[str, None] = "0005_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column_backfill(table: str, column: str, col_type: sa.types.TypeEngine, fill: str) -> None:
    """Add a NOT NULL column to an existing table, batch-safe for SQLite.

    The model keeps a Python-side default only, so no server default remains in
    the final schema and `alembic check` parity holds on SQLite and Postgres.
    """
    op.add_column(table, sa.Column(column, col_type, nullable=True))
    op.execute(sa.text(f"UPDATE {table} SET {column}='{fill}' WHERE {column} IS NULL"))
    with op.batch_alter_table(table) as batch_op:
        batch_op.alter_column(column, existing_type=col_type, nullable=False)


def upgrade() -> None:
    _add_column_backfill("users", "role", sa.String(length=32), "sales")
    op.create_index("ix_users_role", "users", ["role"])
    _add_column_backfill("users", "password_hash", sa.String(length=255), "")

    op.create_table(
        "erp_dispatch",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_date", sa.String(length=10), nullable=False),
        sa.Column("dispatch_no", sa.String(length=64), nullable=False),
        sa.Column("customer", sa.String(length=255), nullable=False),
        sa.Column("plant", sa.String(length=64), nullable=False),
        sa.Column("sales_person", sa.String(length=128), nullable=False),
        sa.Column("schedule_qty", sa.Integer(), nullable=False),
        sa.Column("dispatched_qty", sa.Integer(), nullable=False),
        sa.Column("balance_qty", sa.Integer(), nullable=False),
        sa.Column("pct_complete", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("report_date", "dispatch_no", name="uq_erp_dispatch_day_no"),
    )
    op.create_index("ix_erp_dispatch_report_date", "erp_dispatch", ["report_date"])
    op.create_index("ix_erp_dispatch_dispatch_no", "erp_dispatch", ["dispatch_no"])
    op.create_index("ix_erp_dispatch_customer", "erp_dispatch", ["customer"])
    op.create_index("ix_erp_dispatch_plant", "erp_dispatch", ["plant"])
    op.create_index("ix_erp_dispatch_status", "erp_dispatch", ["status"])

    op.create_table(
        "erp_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_date", sa.String(length=10), nullable=False),
        sa.Column("order_no", sa.String(length=64), nullable=False),
        sa.Column("customer", sa.String(length=255), nullable=False),
        sa.Column("order_date", sa.String(length=10), nullable=False),
        sa.Column("required_date", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_value", sa.Integer(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("report_date", "order_no", name="uq_erp_order_day_no"),
    )
    op.create_index("ix_erp_orders_report_date", "erp_orders", ["report_date"])
    op.create_index("ix_erp_orders_order_no", "erp_orders", ["order_no"])
    op.create_index("ix_erp_orders_customer", "erp_orders", ["customer"])
    op.create_index("ix_erp_orders_order_date", "erp_orders", ["order_date"])
    op.create_index("ix_erp_orders_status", "erp_orders", ["status"])

    op.create_table(
        "integration_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_integration_settings_key", "integration_settings", ["key"], unique=True)

    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_sync_runs_job", "sync_runs", ["job"])
    op.create_index("ix_sync_runs_status", "sync_runs", ["status"])

    op.create_table(
        "journey_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("contact_id", sa.Integer(), nullable=False),
        sa.Column("customer_type", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_journey_events_user_id", "journey_events", ["user_id"])
    op.create_index("ix_journey_events_contact_id", "journey_events", ["contact_id"])
    op.create_index("ix_journey_events_customer_type", "journey_events", ["customer_type"])
    op.create_index("ix_journey_events_stage", "journey_events", ["stage"])
    op.create_index("ix_journey_events_event", "journey_events", ["event"])

    op.create_table(
        "voice_transcripts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("gcs_path", sa.String(length=512), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("gcs_updated", sa.String(length=64), nullable=False),
        sa.Column("duration_sec", sa.Integer(), nullable=False),
        sa.Column("sample_rate", sa.Integer(), nullable=False),
        sa.Column("channels", sa.Integer(), nullable=False),
        sa.Column("mean_volume_db", sa.Integer(), nullable=False),
        sa.Column("max_volume_db", sa.Integer(), nullable=False),
        sa.Column("silence_ratio", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("speakers", sa.JSON(), nullable=False),
        sa.Column("layers", sa.JSON(), nullable=False),
        sa.Column("tone", sa.JSON(), nullable=False),
        sa.Column("lead", sa.JSON(), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("error", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("gcs_path", name="uq_voice_transcript_path"),
    )
    op.create_index("ix_voice_transcripts_user_id", "voice_transcripts", ["user_id"])
    op.create_index("ix_voice_transcripts_gcs_path", "voice_transcripts", ["gcs_path"], unique=True)
    op.create_index("ix_voice_transcripts_file_name", "voice_transcripts", ["file_name"])
    op.create_index("ix_voice_transcripts_status", "voice_transcripts", ["status"])

    op.create_table(
        "team_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("author_name", sa.String(length=255), nullable=False),
        sa.Column("author_role", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("transcript_id", sa.Integer(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reviewed_by", sa.String(length=255), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_team_messages_user_id", "team_messages", ["user_id"])
    op.create_index("ix_team_messages_kind", "team_messages", ["kind"])
    op.create_index("ix_team_messages_status", "team_messages", ["status"])

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "code", name="uq_product_user_code"),
    )
    op.create_index("ix_products_user_id", "products", ["user_id"])
    op.create_index("ix_products_code", "products", ["code"])
    op.create_index("ix_products_name", "products", ["name"])
    op.create_index("ix_products_category", "products", ["category"])
    op.create_index("ix_products_is_active", "products", ["is_active"])

    op.create_table(
        "product_rates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("rate", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("effective_date", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("submitted_by", sa.String(length=255), nullable=False),
        sa.Column("approved_by", sa.String(length=255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
    )
    op.create_index("ix_product_rates_user_id", "product_rates", ["user_id"])
    op.create_index("ix_product_rates_product_id", "product_rates", ["product_id"])
    op.create_index("ix_product_rates_effective_date", "product_rates", ["effective_date"])
    op.create_index("ix_product_rates_status", "product_rates", ["status"])

    op.create_table(
        "company_visits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("contact_id", sa.Integer(), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("contact_name", sa.String(length=255), nullable=False),
        sa.Column("contact_phone", sa.String(length=64), nullable=False),
        sa.Column("visit_date", sa.String(length=10), nullable=False),
        sa.Column("visit_type", sa.String(length=32), nullable=False),
        sa.Column("sales_person", sa.String(length=255), nullable=False),
        sa.Column("purpose", sa.String(length=512), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("outcome", sa.String(length=64), nullable=False),
        sa.Column("next_action", sa.Text(), nullable=False),
        sa.Column("follow_up_date", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("media", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_company_visits_user_id", "company_visits", ["user_id"])
    op.create_index("ix_company_visits_contact_id", "company_visits", ["contact_id"])
    op.create_index("ix_company_visits_company", "company_visits", ["company"])
    op.create_index("ix_company_visits_visit_date", "company_visits", ["visit_date"])
    op.create_index("ix_company_visits_visit_type", "company_visits", ["visit_type"])
    op.create_index("ix_company_visits_sales_person", "company_visits", ["sales_person"])
    op.create_index("ix_company_visits_status", "company_visits", ["status"])

    op.create_table(
        "social_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("metric", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_social_metrics_user_id", "social_metrics", ["user_id"])
    op.create_index("ix_social_metrics_platform", "social_metrics", ["platform"])
    op.create_index("ix_social_metrics_metric", "social_metrics", ["metric"])
    op.create_index("ix_social_metrics_period", "social_metrics", ["period"])


def downgrade() -> None:
    op.drop_index("ix_social_metrics_period", table_name="social_metrics")
    op.drop_index("ix_social_metrics_metric", table_name="social_metrics")
    op.drop_index("ix_social_metrics_platform", table_name="social_metrics")
    op.drop_index("ix_social_metrics_user_id", table_name="social_metrics")
    op.drop_table("social_metrics")

    op.drop_index("ix_company_visits_status", table_name="company_visits")
    op.drop_index("ix_company_visits_sales_person", table_name="company_visits")
    op.drop_index("ix_company_visits_visit_type", table_name="company_visits")
    op.drop_index("ix_company_visits_visit_date", table_name="company_visits")
    op.drop_index("ix_company_visits_company", table_name="company_visits")
    op.drop_index("ix_company_visits_contact_id", table_name="company_visits")
    op.drop_index("ix_company_visits_user_id", table_name="company_visits")
    op.drop_table("company_visits")

    op.drop_index("ix_product_rates_status", table_name="product_rates")
    op.drop_index("ix_product_rates_effective_date", table_name="product_rates")
    op.drop_index("ix_product_rates_product_id", table_name="product_rates")
    op.drop_index("ix_product_rates_user_id", table_name="product_rates")
    op.drop_table("product_rates")

    op.drop_index("ix_products_is_active", table_name="products")
    op.drop_index("ix_products_category", table_name="products")
    op.drop_index("ix_products_name", table_name="products")
    op.drop_index("ix_products_code", table_name="products")
    op.drop_index("ix_products_user_id", table_name="products")
    op.drop_table("products")

    op.drop_index("ix_team_messages_status", table_name="team_messages")
    op.drop_index("ix_team_messages_kind", table_name="team_messages")
    op.drop_index("ix_team_messages_user_id", table_name="team_messages")
    op.drop_table("team_messages")

    op.drop_index("ix_voice_transcripts_status", table_name="voice_transcripts")
    op.drop_index("ix_voice_transcripts_file_name", table_name="voice_transcripts")
    op.drop_index("ix_voice_transcripts_gcs_path", table_name="voice_transcripts")
    op.drop_index("ix_voice_transcripts_user_id", table_name="voice_transcripts")
    op.drop_table("voice_transcripts")

    op.drop_index("ix_journey_events_event", table_name="journey_events")
    op.drop_index("ix_journey_events_stage", table_name="journey_events")
    op.drop_index("ix_journey_events_customer_type", table_name="journey_events")
    op.drop_index("ix_journey_events_contact_id", table_name="journey_events")
    op.drop_index("ix_journey_events_user_id", table_name="journey_events")
    op.drop_table("journey_events")

    op.drop_index("ix_sync_runs_status", table_name="sync_runs")
    op.drop_index("ix_sync_runs_job", table_name="sync_runs")
    op.drop_table("sync_runs")

    op.drop_index("ix_integration_settings_key", table_name="integration_settings")
    op.drop_table("integration_settings")

    op.drop_index("ix_erp_orders_status", table_name="erp_orders")
    op.drop_index("ix_erp_orders_order_date", table_name="erp_orders")
    op.drop_index("ix_erp_orders_customer", table_name="erp_orders")
    op.drop_index("ix_erp_orders_order_no", table_name="erp_orders")
    op.drop_index("ix_erp_orders_report_date", table_name="erp_orders")
    op.drop_table("erp_orders")

    op.drop_index("ix_erp_dispatch_status", table_name="erp_dispatch")
    op.drop_index("ix_erp_dispatch_plant", table_name="erp_dispatch")
    op.drop_index("ix_erp_dispatch_customer", table_name="erp_dispatch")
    op.drop_index("ix_erp_dispatch_dispatch_no", table_name="erp_dispatch")
    op.drop_index("ix_erp_dispatch_report_date", table_name="erp_dispatch")
    op.drop_table("erp_dispatch")

    op.drop_index("ix_users_role", table_name="users")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("password_hash")
        batch_op.drop_column("role")
