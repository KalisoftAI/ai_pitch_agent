"""Copy local SQLite data into Cloud SQL, then reconcile row counts.

Uses the Cloud SQL Python connector (ADC) so no proxy binary or public IP is
needed. Idempotent: uses ORM merge by primary key, so re-runs update in place.

    python scripts/migrate_sqlite_to_cloudsql.py \
        --instance gen-lang-client-0132243782:us-central1:kalisoft-sales-data

Connection user/db/password come from .env (POSTGRES_USER / POSTGRES_DB /
POSTGRES_PASSWORD) unless overridden with flags.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from sales_fastapi import models  # noqa: E402
from sales_fastapi.config import settings  # noqa: E402
from sales_fastapi.database import Base  # noqa: E402

# Parent-before-child order so foreign-key references exist.
MODELS = [
    models.User,
    models.Contact,
    models.EmailConnection,
    models.LinkedInProfile,
    models.RedditPost,
    models.WhatsAppMessage,
    models.MessageTemplate,
    models.Campaign,
    models.CampaignMessage,
    models.AuditLog,
    models.ModelUsage,
]


def make_remote_engine(instance: str, user: str, password: str, database: str):
    from google.cloud.sql.connector import Connector

    connector = Connector()

    def getconn():
        return connector.connect(instance, "pg8000", user=user, password=password, db=database)

    engine = create_engine("postgresql+pg8000://", creator=getconn, pool_pre_ping=True)
    return engine, connector


def copy_table(local: Session, remote: Session, model) -> tuple[int, int]:
    try:
        rows = local.query(model).all()
    except Exception as exc:  # noqa: BLE001 - table may be absent locally
        print(f"  {model.__tablename__}: source unavailable ({type(exc).__name__})")
        return 0, remote.query(func.count(model.id)).scalar() or 0

    table = model.__table__
    columns = [column.name for column in table.columns]
    payload = [{name: getattr(row, name) for name in columns} for row in rows]
    if payload:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        batch_size = 500
        for start in range(0, len(payload), batch_size):
            batch = payload[start : start + batch_size]
            remote.execute(pg_insert(table).values(batch).on_conflict_do_nothing())
        remote.commit()
    return len(rows), remote.query(func.count(model.id)).scalar() or 0


def reset_sequences(remote: Session) -> None:
    """Advance Postgres sequences past explicitly inserted ids."""
    for model in MODELS:
        table = model.__tablename__
        try:
            remote.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence(:t, 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table}), 1))"
                ),
                {"t": table},
            )
        except Exception:  # noqa: BLE001 - table/sequence may not exist
            remote.rollback()
    remote.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate SQLite -> Cloud SQL")
    parser.add_argument("--local-db", default=settings.SQLITE_PATH)
    parser.add_argument("--instance", default=settings.CLOUD_SQL_CONNECTION_NAME, required=False)
    parser.add_argument("--user", default=settings.POSTGRES_USER)
    parser.add_argument("--password", default=settings.POSTGRES_PASSWORD)
    parser.add_argument("--db", default=settings.POSTGRES_DB)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.instance:
        raise SystemExit("--instance or CLOUD_SQL_CONNECTION_NAME is required")

    local_engine = create_engine(f"sqlite:///{args.local_db}")
    print(f"Source: sqlite:///{args.local_db}")
    print(f"Target: {args.instance} db={args.db} user={args.user}")

    if args.dry_run:
        local = Session(local_engine)
        for model in MODELS:
            try:
                count = local.query(func.count(model.id)).scalar()
            except Exception:  # noqa: BLE001
                count = "n/a"
            print(f"  {model.__tablename__}: {count}")
        local.close()
        return

    remote_engine, connector = make_remote_engine(args.instance, args.user, args.password, args.db)
    Base.metadata.create_all(bind=remote_engine)

    local = Session(local_engine)
    remote = Session(remote_engine)
    try:
        print("Copying tables ...")
        for model in MODELS:
            source_count, target_count = copy_table(local, remote, model)
            status = "OK" if source_count == target_count else "MISMATCH"
            print(f"  {model.__tablename__:20s} source={source_count:<6} target={target_count:<6} {status}")

        reset_sequences(remote)

        print("\nReconcile by user (contacts):")
        local_users = {u.id: u.email for u in local.query(models.User).all()}
        ok = True
        for user_id, email in local_users.items():
            src = (
                local.query(func.count(models.Contact.id))
                .filter(models.Contact.user_id == user_id)
                .scalar()
                or 0
            )
            dst = (
                remote.query(func.count(models.Contact.id))
                .filter(models.Contact.user_id == user_id)
                .scalar()
                or 0
            )
            mark = "OK" if src == dst else "MISMATCH"
            ok = ok and src == dst
            print(f"  user {user_id} {email:35s} source={src:<6} target={dst:<6} {mark}")

        print("\nRECONCILE:", "PASS" if ok else "FAIL")
    finally:
        local.close()
        remote.close()
        connector.close()


if __name__ == "__main__":
    main()
