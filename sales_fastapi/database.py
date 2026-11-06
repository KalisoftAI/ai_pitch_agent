"""Database engine / session factory.

Resolution order:
1. DATABASE_URL env var (used by tests -> sqlite, and by Cloud Run -> postgres)
2. CLOUD_SQL_CONNECTION_NAME -> Postgres over the Cloud SQL unix socket
3. POSTGRES_HOST -> plain Postgres TCP
4. Fallback -> local SQLite file (zero-config developer mode)
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


def _build_url() -> str:
    if settings.DATABASE_URL:
        return settings.DATABASE_URL

    if settings.CLOUD_SQL_CONNECTION_NAME:
        return (
            "postgresql+psycopg2://"
            f"{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
            f"@/{settings.POSTGRES_DB}"
            f"?host=/cloudsql/{settings.CLOUD_SQL_CONNECTION_NAME}"
        )

    if settings.POSTGRES_HOST:
        return (
            "postgresql+psycopg2://"
            f"{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
            f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
        )

    return f"sqlite:///{settings.SQLITE_PATH}"


DATABASE_URL = _build_url()

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that yields a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401  (register mappers)

    Base.metadata.create_all(bind=engine)
    _ensure_columns()


def _ensure_columns() -> None:
    """Idempotent column adds for existing databases (create_all only makes new tables)."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "users" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("users")}
        if "password_hash" not in cols:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) DEFAULT ''")
                )
        if "role" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(32) DEFAULT 'sales'"))
    if "company_visits" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("company_visits")}
        for column, ddl in (
            ("meet_person", "VARCHAR(255) DEFAULT ''"),
            ("meet_home_location", "VARCHAR(255) DEFAULT ''"),
            ("previous_discussion", "TEXT DEFAULT ''"),
            ("mail_chat_details", "TEXT DEFAULT ''"),
            ("map_location", "VARCHAR(512) DEFAULT ''"),
        ):
            if column not in cols:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE company_visits ADD COLUMN {column} {ddl}"))
    if "marketing_companies" in insp.get_table_names():
        cols = {c["name"]: c for c in insp.get_columns("marketing_companies")}
        for column in ("phone", "call_status", "source_sheet"):
            col = cols.get(column)
            length = getattr(col.get("type"), "length", None) if col else None
            if col is not None and length is not None and length < 255:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            f"ALTER TABLE marketing_companies "
                            f"ALTER COLUMN {column} TYPE VARCHAR(255)"
                        )
                    )
        # Sales-pipeline fields added after the table was first created.
        for column, ddl in (
            ("funnel_stage", "VARCHAR(32) DEFAULT 'awareness'"),
            ("sales_progress", "VARCHAR(48) DEFAULT 'new'"),
            ("next_action", "TEXT DEFAULT ''"),
            ("follow_up_date", "VARCHAR(10) DEFAULT ''"),
        ):
            if column not in cols:
                with engine.begin() as conn:
                    conn.execute(
                        text(f"ALTER TABLE marketing_companies ADD COLUMN {column} {ddl}")
                    )
    if "campaign_messages" in insp.get_table_names():
        # Older campaign_messages predate contact_name/opened_at tracking.
        cols = {c["name"] for c in insp.get_columns("campaign_messages")}
        for column, ddl in (
            ("contact_name", "VARCHAR(255) DEFAULT ''"),
            ("sent_at", "TIMESTAMP"),
            ("opened_at", "TIMESTAMP"),
        ):
            if column not in cols:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE campaign_messages ADD COLUMN {column} {ddl}"))
        if "status" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE campaign_messages ADD COLUMN status VARCHAR(32) DEFAULT 'pending_review'"))
    if "message_templates" in insp.get_table_names():
        # Older databases were created before strategy/funnel_stage/variables
        # existed; create_all never alters existing tables, so add them here.
        json_default = "'[]'::json" if engine.dialect.name == "postgresql" else "'[]'"
        cols = {c["name"] for c in insp.get_columns("message_templates")}
        for column, ddl in (
            ("strategy", "VARCHAR(32) DEFAULT 'cold_outreach'"),
            ("funnel_stage", "VARCHAR(32) DEFAULT 'awareness'"),
            ("subject", "VARCHAR(255) DEFAULT ''"),
            ("body", "TEXT DEFAULT ''"),
            ("variables", f"JSON DEFAULT {json_default}"),
            ("is_active", "BOOLEAN DEFAULT TRUE"),
        ):
            if column not in cols:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE message_templates ADD COLUMN {column} {ddl}"))
