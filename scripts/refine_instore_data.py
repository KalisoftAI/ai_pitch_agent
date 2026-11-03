"""Refine the GCS interaction dump into instore-mail insights.

Reads:
  gcs_data/interaction_dump.json
  contacts from the app database (when available)

Writes:
  gcs_data/instore_mails.json
  gcs_data/graph/missing_links.json
  gcs_data/graph/mail_nodes.json
  gcs_data/graph/mail_edges.json

Uploads the snapshot to GCS unless --no-upload is passed. Upload is best-effort:
when ADC is not configured the local files are still written.

Usage:
  python scripts/refine_instore_data.py
  python scripts/refine_instore_data.py --no-upload
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sales_fastapi.config import settings  # noqa: E402
from sales_fastapi.database import SessionLocal  # noqa: E402
from sales_fastapi.instore_mail import (  # noqa: E402
    build_insights,
    load_dump_mails,
    save_insights,
)
from sales_fastapi.models import Contact  # noqa: E402
from sales_fastapi.services import GCSStorage  # noqa: E402


def _contacts() -> list[dict]:
    db = SessionLocal()
    try:
        return [
            {"id": row.id, "name": row.name, "email": row.email, "phone": row.phone,
             "domain": row.domain, "company": row.company}
            for row in db.query(Contact).all()
        ]
    except Exception:  # noqa: BLE001 - offline refinement must still work
        return []
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Refine instore-mail insights")
    parser.add_argument("--no-upload", action="store_true", help="write local files only")
    args = parser.parse_args()

    mails = load_dump_mails(ROOT / "gcs_data" / "interaction_dump.json")
    contacts = _contacts()
    insights = build_insights(
        mails,
        contacts,
        source={"kind": "interaction_dump", "dump": "gcs_data/interaction_dump.json"},
    )
    stored = save_insights(insights, upload=not args.no_upload)

    graph_dir = ROOT / "gcs_data" / "graph"
    graph_dir.mkdir(parents=True, exist_ok=True)
    missing = insights.get("missing_links", {})
    (graph_dir / "missing_links.json").write_text(
        json.dumps(missing, indent=2), encoding="utf-8"
    )
    graph = insights.get("graph", {})
    (graph_dir / "mail_nodes.json").write_text(
        json.dumps(graph.get("nodes", []), indent=2), encoding="utf-8"
    )
    (graph_dir / "mail_edges.json").write_text(
        json.dumps(graph.get("edges", []), indent=2), encoding="utf-8"
    )

    uploaded_graph = 0
    if not args.no_upload:
        gcs = GCSStorage(bucket_name=settings.GCS_BUCKET_MAIL)
        prefix = f"{settings.GCS_PATH_INSTORE_MAILS}graph/"
        for name in ("missing_links.json", "mail_nodes.json", "mail_edges.json"):
            payload = json.loads((graph_dir / name).read_text(encoding="utf-8"))
            if gcs.upload_json(f"{prefix}{name}", payload):
                uploaded_graph += 1

    print(json.dumps({
        "mails": insights["insights"]["total"],
        "linked": insights["insights"]["linked"],
        "missing_links": missing.get("count", 0),
        "attachments": insights["insights"]["attachments"],
        "accuracy_pct": insights["insights"]["accuracy_pct"],
        "graph_nodes": graph.get("stats", {}).get("nodes", 0),
        "graph_edges": graph.get("stats", {}).get("edges", 0),
        "local": stored["path"],
        "gcs_uploaded": stored["gcs_uploaded"],
        "gcs_graph_files": uploaded_graph,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
