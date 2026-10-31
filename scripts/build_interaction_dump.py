"""Cron script: build the interaction dump JSON.

- Downloads WhatsApp chat export zips from gs://kalika_enterprises/kalika backup/
- Parses every chat (messages, participants, dates, media markers)
- Lists real attachments per chat (name, size, media type)
- Adds outbound interactions from the app DB (whatsapp_messages queue)
- Writes gcs_data/interaction_dump.json

Run with the project venv:  .venv\\Scripts\\python.exe scripts\\build_interaction_dump.py
"""
import io
import json
import os
import sqlite3
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sales_fastapi.interaction_dump import build_dump, classify_media, parse_whatsapp_chat  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / "gcs_data" / "interaction_dump.json"
DB = BASE / "sales_pipeline.db"
BUCKET = "kalika_enterprises"
PREFIX = "kalika backup/"


def load_outbound(db_path: Path) -> list[dict]:
    if not db_path.exists():
        return []
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(
        "SELECT id, phone_number, message, status, created_at FROM whatsapp_messages ORDER BY id DESC LIMIT 500")]
    con.close()
    return [{
        "type": "whatsapp_outbound",
        "id": r["id"],
        "to": r["phone_number"],
        "date": str(r["created_at"]),
        "body_preview": (r["message"] or "")[:200],
        "status": r["status"],
        "attachments": [],
        "source": "app_db.whatsapp_messages",
    } for r in rows]


def main() -> None:
    import google.auth
    from google.cloud import storage

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    creds, _ = google.auth.default()
    client = storage.Client(credentials=creds)
    bucket = client.bucket(BUCKET)
    blobs = [b for b in client.list_blobs(bucket, prefix=PREFIX) if b.name.endswith(".zip")]
    print(f"found {len(blobs)} chat zips under gs://{BUCKET}/{PREFIX}")

    chats = []
    for b in blobs:
        try:
            raw = b.download_as_bytes()
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                txt = next((i.filename for i in z.infolist() if i.filename.lower().endswith(".txt")), None)
                attachments = [
                    {"name": i.filename, "size_bytes": int(i.file_size),
                     "media_type": classify_media(i.filename)}
                    for i in z.infolist()
                    if not i.filename.lower().endswith(".txt") and not i.is_dir()
                ]
                parsed = parse_whatsapp_chat(z.read(txt).decode("utf-8", errors="replace")) if txt else parse_whatsapp_chat("")
            import re as _re
            title = _re.sub(r"^WhatsApp Chat with\s+", "", Path(b.name).stem)
            chats.append({"chat": title, "file": Path(b.name).name, "gcs": f"gs://{BUCKET}/{b.name}",
                          **parsed, "attachments": attachments})
            print(f"  OK {Path(b.name).name}: {parsed['message_count']} msgs, {len(attachments)} attachments")
        except Exception as e:  # keep going on a bad zip
            print(f"  FAIL {b.name}: {e}")

    mails = load_outbound(DB)
    dump = build_dump(chats, mails, sources=[f"gs://{BUCKET}/{PREFIX}", "app_db.whatsapp_messages"])
    OUT.write_text(json.dumps(dump, indent=1, ensure_ascii=False), encoding="utf-8")
    print("dump written:", OUT)
    print(json.dumps(dump["stats"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
