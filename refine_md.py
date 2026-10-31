"""Refine Kalika_Real_Time_Customer_Feedback_System.md with current build status:
feedback triggering pipeline LIVE (segments + user template selection + wa.me send);
QR-based sharing moved to NEXT SCOPE. Push to GCS."""
import os
import google.auth
from google.cloud import storage

BASE = os.path.dirname(os.path.abspath(__file__))
MD = os.path.join(BASE, "gcs_data", "sales-metadata__Kalika_Real_Time_Customer_Feedback_System.md")
GCS_DEST = "sales-metadata/Kalika_Real_Time_Customer_Feedback_System.md"

with open(MD, "r", encoding="utf-8") as fh:
    content = fh.read()

# 1) Tag the QR strategy section as next scope
content = content.replace(
    "## 5. QR Code Strategy",
    "## 5. QR Code Strategy\n\n> **STATUS: NEXT SCOPE.** QR-based entry is not part of the current build. "
    "The live pipeline (section 16.9) sends personalised messages directly via wa.me click-to-send. "
    "This section stays as the design reference for the QR phase.",
)

# 2) Refresh the section-16 scope note
old_scope = "> Built from current live samples: 376 unique contact phones"
if old_scope in content:
    content = content.replace(
        "> Scope: ready-to-use WhatsApp text templates **with attachments**, click-to-send (`wa.me`) deep links,\n"
        "> category-wise follow-up flows, action→intent→metric mapping for the dashboard, and the Python API\n"
        "> sync layer (Gemma + Gemini Flash model chain) with task/subtask selection and a regular feedback loop.",
        "> Scope: ready-to-use WhatsApp text templates **with attachments**, click-to-send (`wa.me`) deep links,\n"
        "> category-wise follow-up flows, action→intent→metric mapping for the dashboard, and the Python API\n"
        "> sync layer (Gemma + Gemini Flash model chain) with task/subtask selection and a regular feedback loop.\n"
        "> **QR-based sharing is NEXT SCOPE — the current build sends messages only (see 16.9).**",
    )

# 3) Append build-status subsection (idempotent)
marker = "\n### 16.9 Build Status"
if marker in content:
    content = content.split(marker)[0].rstrip() + "\n"

BUILD_STATUS = """
### 16.9 Build Status — 30-Oct-2026 (pipeline build started)

**LIVE NOW — customer feedback triggering pipeline** (`/api/pipeline/*`, FastAPI `kalisoft-sales`):

```text
 USER selects SEGMENT (card)            USER selects TEMPLATE (dropdown)
  recent_orders | new_customers | leads   e.g. WA-FU-01 / WA-RT-01 / WA-ORD-01
                 |                            |
                 v                            v
        POST /api/pipeline/preview  -> personalised messages + wa.me link per row
                 |
                 +--> per-row "Open WhatsApp" (wa.me) -> agent taps Send   [SEND PATH A]
                 |
                 +--> POST /api/pipeline/queue -> whatsapp_messages        [SEND PATH B]
                      (status=pending, human-reviewed send path)
```

| Item | Status | Detail |
|---|---|---|
| Segment: recent orders | LIVE | 89 ERP orders loaded from latest ERP-V1 report; 22 matched to contact phones (auto company-name match) |
| Segment: new customers | LIVE | 473 reachable (GCS contact sync, last 7 days, with phone) |
| Segment: leads | LIVE | 477 reachable (call-status / requirement notes; sorted not-answered -> busy -> call-later -> details-sent) |
| Template selection by user | LIVE | 11 templates across segments (WA-ORD-01, WA-FBK-01/02/06, WA-NEW-01/02, WA-FU-01/02/03, WA-RT-01, WA-EXP-01) |
| Personalised messages | LIVE | Variables {name} {company} {order_no} {amount} {status} {rates} {doc links}; agent name from session |
| Send via wa.me click-to-send | LIVE | Per-row link opens WhatsApp with message ready; invalid/landline numbers flagged "no phone" |
| Send via reviewed queue | LIVE | `POST /api/pipeline/queue` -> `whatsapp_messages` (pending) |
| UI | LIVE | "Feedback pipeline" tab — segment cards, template dropdown, preview table, mobile + desktop responsive |
| Attachments | LIVE (as links) | catalogue / profile / poly-calc docs shared as secure GCS links inside message text |
| **QR-based sharing** | **NEXT SCOPE** | QR entry points (general/delivery/product), scan analytics, print-ready QR sheets — not in this build |
| WhatsApp Business API auto-send | NEXT SCOPE | Template approval + unattended sending; current build keeps human tap-to-send |
| ERP live lookup | NEXT SCOPE | Direct ERP API; current build reads the latest published ERP report snapshot |

New endpoints: `GET /api/pipeline/segments` · `GET /api/pipeline/templates?segment=` ·
`POST /api/pipeline/preview` · `POST /api/pipeline/queue` · `GET /api/pipeline/queue`

Next scope queue: (1) QR generation + scan tracking per section 5; (2) Gemma/Flash auto-personalisation
per contact (chain ready in `gemma_service.py`); (3) webhook intent classification driving next-best-action;
(4) WhatsApp Business API template approval for unattended sending.
"""

content = content.rstrip() + "\n" + BUILD_STATUS

with open(MD, "w", encoding="utf-8") as fh:
    fh.write(content)
print("Markdown refined:", MD, f"({len(content)} chars)")

creds, _ = google.auth.default()
client = storage.Client(credentials=creds)
bucket = client.bucket("kalika_enterprises")
blob = bucket.blob(GCS_DEST)
blob.upload_from_filename(MD)
print(f"Pushed to gs://kalika_enterprises/{GCS_DEST} ({os.path.getsize(MD)} bytes)")
