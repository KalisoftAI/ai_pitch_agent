"""Cron executor: voice_transcription_sync.

Runs the voice pipeline (L0 audio probe -> L1 transcribe -> L2-L4 layers with
Gemma SLM first) for every audio file under the configured GCS prefix.

Usage:
    python scripts/voice_sync.py [--force]

In Cloud Run this is invoked by the scheduler job; locally it mirrors the API
behaviour without needing an interactive token.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sales_fastapi.database import SessionLocal, init_db  # noqa: E402
from sales_fastapi.models import User  # noqa: E402
from sales_fastapi.routers.voice import _audio_blobs, _process_blob  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="reprocess already-done files")
    parser.add_argument("--email", default="ai.solutions@kalisoftai.in")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == args.email).first()
        if user is None:
            user = db.query(User).first()
        if user is None:
            print("no user found; create one via the API first")
            return
        blobs = _audio_blobs()
        print(f"voice_sync: {len(blobs)} audio file(s) under prefix")
        for blob in blobs:
            row = _process_blob(db, user, blob, force=args.force)
            print(json.dumps({"file": row.file_name, "status": row.status, "mode": (row.layers or {}).get("mode"),
                              "duration_sec": row.duration_sec, "error": row.error}, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
