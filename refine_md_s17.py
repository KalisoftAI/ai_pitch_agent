"""Append section 17 (crons, interaction dump, graph preprocessing) to the feedback MD; push to GCS."""
import os
import google.auth
from google.cloud import storage

BASE = os.path.dirname(os.path.abspath(__file__))
MD = os.path.join(BASE, "gcs_data", "sales-metadata__Kalika_Real_Time_Customer_Feedback_System.md")
GCS_DEST = "sales-metadata/Kalika_Real_Time_Customer_Feedback_System.md"

SECTION = r"""

---

## 17. Backend Crons, Interaction Dump & Graph Pre-Processing — 30-Oct-2026 Update

### 17.1 Updated cron set (backend scheduler)

`POST /api/cron/run` now sweeps **11 registered tasks** (scheduler backend: in-memory locally, Redis in
production; Cloud Scheduler → `/api/scheduler/run` on cron expressions):

| Cron task | Schedule | Purpose |
|---|---|---|
| sync_gcs_contacts | `0 */6 * * *` | Import contacts from GCS bucket |
| refresh_email_connections | `*/30 * * * *` | Re-test IMAP/SMTP connections |
| linkedin_hiring_alerts / reddit_hiring_alerts | `0 8 * * *` | Daily hiring-signal sweeps |
| youtube_signal_scan | `0 9 * * *` | YouTube signal scan (future) |
| whatsapp_reminders | `0 10 * * *` | Queue follow-up reminders |
| events_whatsapp_due | `*/15 * * * *` | Dispatch due event messages |
| **pipeline_feedback_due** | `0 * * * *` | **NEW** — send-due pass over feedback-pipeline queue (recent orders / new customers / leads) |
| **build_interaction_dump** | `0 2 * * *` | **NEW** — parse chat exports + app outbox → `interaction_dump.json` (with attachment details) |
| **rebuild_graph_preprocessing** | `30 2 * * *` | **NEW** — networkx graph build → nodes/edges/gexf (future graph DB) |
| kpi_snapshot | `0 23 * * *` | Nightly KPI snapshot |

### 17.2 Interaction dump (mails + chats → JSON)

`scripts/build_interaction_dump.py` → `gcs_data/interaction_dump.json`. First run stats:

| Metric | Value |
|---|---|
| Chat exports parsed (kalika backup/) | **85 chats** |
| Total messages | **4,419** |
| Unique participants | **89** |
| Attachments catalogued (name + size + media type) | **528** (420 images · 52 documents · 48 contact cards · 7 videos · 1 audio) |
| `<Media omitted>` references in texts | 1,056 |
| Outbound interactions (app whatsapp_messages queue) | 27 |

Each chat entry: `chat, file, gcs path, participants, message_count, date_range, messages[{date,time,sender,text,has_media,attachments_inline}], attachments[{name,size_bytes,media_type}]`.
Each mail entry (normalised): `type, subject, from, to, date, body_preview(200), attachments[{name,size_bytes,media_type}], source`.

```text
 kalika backup/*.zip ──┐
                       ├──> parse (WA text regex + zip listing) ──> interaction_dump.json
 app outbox (sqlite) ──┘                    + classify media         (chats[] + mails[] + stats)
```

### 17.3 Graph pre-processing (networkx) — future graph-database scope

`sales_fastapi/graph_build.py` + `scripts/rebuild_graph.py` → `gcs_data/graph/{nodes.json, edges.json, graph.gexf, graph_stats.json}`.

Current numbers (first build, 30-Oct-2026):

| Metric | Value |
|---|---|
| Nodes | **9,123** (contact 8,795 · domain 222 · intent 6 · chat_thread 85 · erp_customer 15) |
| Edges | **9,419** (CONTACT_HAS_INTENT 8,795 · CONTACT_IN_DOMAIN 611 · ORDER_BY_CONTACT 13 · CHAT_MAPS_TO_CONTACT 0*) |
| Density / components | 0.000113 / 88 weakly-connected |
| Top hubs | intent:general (8,574) · domain:gmail.com (307) · intent:procurement (68) · intent:sales (65) · domain:cummins.com (21) |

*Chat→contact phone mapping produced 0 edges on first run — chat titles carry counterparty numbers that are not yet
contacts; improving this mapping is queued work.

```text
 contacts (8,795) ──HAS_INTENT──> intent nodes (6)
        │
        ├──IN_DOMAIN──> domain nodes (222)            networkx DiGraph
        │                                                    │
 chat threads (85) ──MAPS_TO──> contact (by phone)          v
 erp customers (15) ──BY_CONTACT──> contact (company)   nodes.json + edges.json
                                                         + graph.gexf ──> FUTURE: Neo4j/Neptune
```

**Future scope (graph DB):** load GEXF into Neo4j/Neptune; add REPLIED_TO edges from webhook replies;
MESSAGE_ABOUT product nodes; centrality-based lead scoring; community detection for account clusters.

### 17.4 Tests

`tests/test_graph_and_dump.py` — **10 tests passing** (venv pytest): chat parsing (incl. multi-line continuation +
inline attachment markers + media-omitted), media classification, zip reading, mail-record normalisation with
attachment details, dump stats, phone normalisation (landline rejection for wa.me), template fill + link build,
template catalog integrity, graph build (incl. placeholder-domain exclusion), graph stats + GEXF export.
"""

with open(MD, "r", encoding="utf-8") as fh:
    content = fh.read()
marker = "\n---\n\n## 17. Backend Crons"
if marker in content:
    content = content.split(marker)[0]
content = content.rstrip() + SECTION
with open(MD, "w", encoding="utf-8") as fh:
    fh.write(content)
print("MD updated:", len(content), "chars")

creds, _ = google.auth.default()
client = storage.Client(credentials=creds)
blob = client.bucket("kalika_enterprises").blob(GCS_DEST)
blob.upload_from_filename(MD)
print(f"Pushed to gs://kalika_enterprises/{GCS_DEST} ({os.path.getsize(MD)} bytes)")
