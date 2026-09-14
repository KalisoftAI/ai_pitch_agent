"""Sync contacts from GCS into named users.

Examples
--------
    python scripts/sync_gcs_contacts.py \
        --user "Kalika Enterprises:kalika@kalisoftai.com" \
        --user "Kalisoft Admin:admin@kalisoftai.com"

    # restrict to specific GCS prefixes (repeatable)
    python scripts/sync_gcs_contacts.py \
        --user "Kalika Enterprises:kalika@kalisoftai.com" \
        --prefix all-sales-contacts-data/

Creates the user if missing, then imports every supported contact file
(CSV/Excel/VCF/JSON) under each prefix, skipping duplicates by email.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from sales_fastapi.config import settings  # noqa: E402
from sales_fastapi.database import SessionLocal, init_db  # noqa: E402
from sales_fastapi.importer import normalise_record, records_from_bytes  # noqa: E402
from sales_fastapi.models import Contact, User  # noqa: E402
from sales_fastapi.services import GCSStorage  # noqa: E402


def parse_user(spec: str) -> tuple[str, str]:
    if ":" not in spec:
        raise argparse.ArgumentTypeError("user must be NAME:EMAIL")
    name, email = spec.split(":", 1)
    return name.strip(), email.strip().lower()


def get_or_create_user(db, name: str, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            google_sub=f"seed-{email}",
            email=email,
            name=name,
            domain=email.split("@")[-1],
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"  created user #{user.id} {name} <{email}>")
    else:
        print(f"  using user #{user.id} {user.name} <{email}>")
    return user


def sync_user(db, user: User, prefixes: list[str], bucket: str) -> tuple[int, int, int]:
    gcs = GCSStorage(bucket_name=bucket)
    if not gcs.available:
        raise SystemExit(f"GCS is not available for bucket {bucket} (missing credentials)")

    seen: set[str] = set(
        row[0] for row in db.query(Contact.email).filter(Contact.user_id == user.id).all()
    )
    imported = skipped = scanned = 0
    for prefix in prefixes:
        blobs = gcs.list_contacts(prefix=prefix)
        scanned += len(blobs)
        for blob in blobs:
            raw = gcs.download_blob(blob["name"])
            if not raw:
                continue
            for record in records_from_bytes(blob["name"], raw):
                normalised = normalise_record(record)
                if not normalised or normalised["email"] in seen:
                    skipped += 1
                    continue
                seen.add(normalised["email"])
                db.add(
                    Contact(
                        user_id=user.id,
                        source="gcs",
                        gcs_path=blob["name"],
                        **normalised,
                    )
                )
                imported += 1
        db.commit()
    return scanned, imported, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync GCS contacts into named users")
    parser.add_argument("--user", action="append", required=True, help="NAME:EMAIL (repeatable)")
    parser.add_argument(
        "--bucket",
        default=settings.GCS_BUCKET_CONTACTS,
        help=f"GCS bucket. Default: {settings.GCS_BUCKET_CONTACTS}",
    )
    parser.add_argument(
        "--prefix",
        action="append",
        default=None,
        help=f"GCS prefix (repeatable). Default: {settings.GCS_PATH_CONTACTS}",
    )
    args = parser.parse_args()

    users = [parse_user(spec) for spec in args.user]
    prefixes = args.prefix or [settings.GCS_PATH_CONTACTS]

    init_db()
    db = SessionLocal()
    try:
        for name, email in users:
            print(f"Syncing {name} <{email}> from gs://{args.bucket}/{prefixes} ...")
            user = get_or_create_user(db, name, email)
            scanned, imported, skipped = sync_user(db, user, prefixes, args.bucket)
            total = db.query(Contact).filter(Contact.user_id == user.id).count()
            print(
                f"  scanned={scanned} imported={imported} skipped={skipped} "
                f"total_for_user={total}"
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
