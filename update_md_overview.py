"""Append WhatsApp Template & Follow-Up Messaging Overview (section 16) to the
Kalika_Real_Time_Customer_Feedback_System.md and push updated file to GCS."""
import os
import google.auth
from google.cloud import storage

BASE = os.path.dirname(os.path.abspath(__file__))
MD = os.path.join(BASE, "gcs_data", "sales-metadata__Kalika_Real_Time_Customer_Feedback_System.md")
GCS_DEST = "sales-metadata/Kalika_Real_Time_Customer_Feedback_System.md"

SECTION = r"""

---

## 16. WhatsApp Template & Follow-Up Messaging System — Overview

> Scope: ready-to-use WhatsApp text templates **with attachments**, click-to-send (`wa.me`) deep links,
> category-wise follow-up flows, action→intent→metric mapping for the dashboard, and the Python API
> sync layer (Gemma + Gemini Flash model chain) with task/subtask selection and a regular feedback loop.
> Built from current live samples: 376 unique contact phones, 9 months of sales registers (5,149 invoices,
> ₹27.58 Cr gross, 124 customers), 48 WhatsApp chat exports, the 13-product rate list, and the
> Kalisoft AI Sales Pipeline FastAPI service (`kalisoft-sales`, asia-south1).

### 16.1 End-to-End Flow (ASCII)

```text
+------------------------- DATA SOURCES (gs://kalika_enterprises) -------------------------+
| sales-contacts/ (376 phones) | kalika_sales2026/ (5,149 invoices) | kalika backup/ (48   |
| WhatsApp chats)              | ERP-V1/Reports/ (orders/dispatch)  | sales-metadata/ docs |
+-------------------------------------------+------------------------------------------------+
                                            v
                              CONTACT & CONTEXT RESOLVER
                              (dedupe phone -> customer/lead,
                               last call status, last order, rates)
                                            v
+-------------------------------- TEMPLATE ENGINE ----------------------------------------+
| Category templates (follow-up / rates / catalogue / order / delivery / payment / expo)   |
|   + variables {name} {company} {product} {rate} {order_no}                               |
|   + attachment picker (catalogue PDF, rate sheet, calc sheet, profile PDF, logo)         |
+-------------------------------------------+----------------------------------------------+
                                            v
                               AI PERSONALIZATION (Python API)
                    POST /api/llm/run  {task, subtask, model_pref}
              model chain: gemma-3-27b-it -> gemma-3-12b-it
                           -> gemini-2.5-flash -> gemini-2.0-flash
              (user selects task & subtask; safe placeholder fallback)
                                            v
+------------------------------ SEND CHANNELS (2 options) ---------------------------------+
| A) CLICK-TO-SEND: https://wa.me/<phone>?text=<urlencoded msg + doc link>                 |
|      -> opens WhatsApp directly with message in the send box (agent taps Send)           |
| B) API SEND: POST /api/whatsapp/send (wechaty gateway) / POST /api/social/whatsapp/      |
|      messages (queue) -> supports media attachments & automation                         |
+-------------------------------------------+----------------------------------------------+
                                            v
                                   CUSTOMER REPLIES / EVENTS
                          POST /api/whatsapp/webhook (inbound capture)
                                            v
+----------------------------------- FEEDBACK LOOP ----------------------------------------+
| intent classify (Gemma) -> update contact status -> recommend next action                 |
| -> schedule follow-up (/api/events/messages/send-due, /api/scheduler/run)                 |
+-------------------------------------------+----------------------------------------------+
                                            v
                            DASHBOARD METRICS  (/api/kpi/* + feedback KPIs)
              delivery rate | reply rate | intent mix | conversion | rating | resolution
```

### 16.2 Attachment (Document) Library

| Doc ID | Document | GCS path | Public link used inside messages | Used with template categories |
|---|---|---|---|---|
| DOC-CAT | Product catalogue PDF | `ERP-V1/New_kalika_enterprises_catalog.pdf` | `https://storage.googleapis.com/kalika_enterprises/ERP-V1/New_kalika_enterprises_catalog.pdf` | catalogue, follow-up, expo |
| DOC-RATE | Rate list (13 products) | `sales-contacts/pune region contacts (1).xlsx` → sheet `Products details` | share as text block in message (rates below) | rates, quotation |
| DOC-POLY | Poly bag calculation sheet | `sales-metadata/POLY BAG CALACULATION SHEET.xlsx` | `https://storage.googleapis.com/kalika_enterprises/sales-metadata/POLY%20BAG%20CALACULATION%20SHEET.xlsx` | quotation, rates |
| DOC-PROF | Company profile | `kalika backup/KALIKA.pdf` | `https://storage.googleapis.com/kalika_enterprises/kalika%20backup/KALIKA.pdf` | first-touch, expo |
| DOC-FEAT | ERP/app features | `ERP-V1/software-docs/Kalika_Feat.pdf` | `https://storage.googleapis.com/kalika_enterprises/ERP-V1/software-docs/Kalika_Feat.pdf` | product/ERP demos |
| DOC-LOGO | Brand logo | `docs/Ecom/kalika logo.jpeg` | `https://storage.googleapis.com/kalika_enterprises/docs/Ecom/kalika%20logo.jpeg` | all (branding) |
| DOC-DASH | Data dashboard summary | `sales-metadata/Kalika_Dashboard_Summary.xlsx` | `https://storage.googleapis.com/kalika_enterprises/sales-metadata/Kalika_Dashboard_Summary.xlsx` | internal reviews |

> Note: `wa.me` links carry **text only** — attachments are shared as the secure HTTPS doc links above inside the
> message body. True media attachments (PDF/image as WhatsApp media) go through the API channel
> (`POST /api/whatsapp/send` / gateway) which supports media payloads.

### 16.3 Message Template Catalog (by category, with variables + attachment)

Variables: `{name}` contact person · `{company}` · `{product}` · `{rate}` · `{order_no}` · `{doc_link}` · `{agent}`

| ID | Category | Intent | Template text (paste-ready) | Attachment |
|---|---|---|---|---|
| WA-FU-01 | Follow-up — Not answered (59+17 cases in lists) | re-engagement | "Namaste {name} ji, this is {agent} from Kalika Enterprises (Ahmednagar). Tried reaching you regarding packaging materials — stretch film, BOPP tape, VCI bags, polybags. Sharing our catalogue: {doc_link}. Please reply YES for a callback or send your requirement here." | DOC-CAT |
| WA-FU-02 | Follow-up — Busy / call later (25+ cases) | re-engagement | "Namaste {name} ji, following up as requested. Kalika Enterprises — manufacturer of stretch film ₹168/kg, BOPP tape ₹30–32/pc, VCI bags ₹182/kg. Rate list & catalogue: {doc_link}. When can I call for 2 minutes?" | DOC-CAT, DOC-RATE |
| WA-FU-03 | Follow-up — Details already sent (Sheet11: 13/22 'Details sent') | nurture | "Namaste {name} ji, earlier we shared Kalika Enterprises product details. Checking if you need current rates or samples for {product}. Polybag calc sheet for reference: {doc_link}. Happy to send a quotation today." | DOC-POLY |
| WA-RT-01 | Rate share (rates seen in order chats) | conversion | "Namaste {name} ji, current Kalika rates — Stretch film 23–51 mic ₹168/kg · VCI bags 50 mic ₹182/kg · Regular polybags ₹170–172/kg · Printed polybags ₹182/kg · BOPP tape 2\" ₹30–32/pc · Hand gloves 40/60/80 gm ₹6.50/8/9–9.50 per pc. GST extra. Order on WhatsApp or reply for PI." | DOC-RATE |
| WA-QT-01 | Quotation follow-up (quotation sent log) | conversion | "Namaste {name} ji, gentle reminder on the Kalika quotation shared for {product}. Prices valid this week. Reply 1 to confirm, 2 to revise quantity, 3 for a call." | DOC-POLY |
| WA-ORD-01 | Order update (order group: 186 order msgs) | retention | "Namaste {name} ji, your Kalika order {order_no} update: {status}. Expected dispatch: {date}. Any change in quantity, reply before 5 PM today. — {agent}" | — |
| WA-DSP-01 | Dispatch update (ERP: 44 partially dispatched) | retention | "Namaste {name} ji, dispatch update for {order_no}: {dispatched_qty} of {schedule_qty} sent today. Balance {balance} planned for {next_date}. E-way/invoice copy: {doc_link}" | invoice/challan link |
| WA-PAY-01 | Payment reminder (45-day terms = 859 invoices) | collections | "Namaste {name} ji, gentle payment reminder from Kalika Enterprises — invoice {order_no} ({amount}) is due as per {terms} terms. Please share UTR once done. Thank you!" | invoice link |
| WA-FBK-01 | Feedback welcome (spec Message 1) | feedback | "👋 Hello from Kalika Enterprises! How can we help today? 📦 Catalogue · 🚚 Delivery Status · ⭐ Feedback · 🛠️ Report Issue · 💬 Talk to Team. Your feedback matters!" | DOC-CAT |
| WA-FBK-02 | Delivery feedback (spec Message 2) | feedback | "🚚 How was your recent Kalika delivery? ✅ On time · ⏳ Late · 📦 Not received · 🤝 Delivery-team feedback. Tap to reply — 10 seconds only." | — |
| WA-EXP-01 | Expo follow-up (Packvision: 111 leads) | re-engagement | "Namaste {name} ji, thank you for visiting Kalika Enterprises at Packvision. As discussed, sharing catalogue + rates: {doc_link}. Can we send samples of {product} this week?" | DOC-CAT, DOC-PROF |
| WA-NEW-01 | First touch (main list: 152 companies) | acquisition | "Namaste {name} ji, {agent} from Kalika Enterprises, Ahmednagar — packaging manufacturer (stretch/shrink film, BOPP & masking tape, VCI, tarpaulin, HDPE/poly bags, gloves). Profile: {doc_link}. Any current requirement?" | DOC-PROF |

### 16.4 Click-to-Send (wa.me) Deep-Link Spec

```text
FORMAT:   https://wa.me/<country_code><phone>?text=<urlencoded(template_text + "\n\n" + doc_link)>
EXAMPLE (WA-RT-01 to +91 98220 00000):
https://wa.me/919822000000?text=Namaste%20Patil%20ji%2C%20current%20Kalika%20rates%20%E2%80%94%20Stretch%20film%20%E2%82%B9168%2Fkg%20%C2%B7%20VCI%20bags%20%E2%82%B9182%2Fkg%20...%20Catalogue%3A%20https%3A%2F%2Fstorage.googleapis.com%2Fkalika_enterprises%2FERP-V1%2FNew_kalika_enterprises_catalog.pdf
```

| Field | Rule |
|---|---|
| phone | 10+ digits, country code, no `+`/spaces (source: 376 unique phones in marketing lists) |
| text | URL-encoded; keep < 1000 chars; emoji allowed |
| attachment | as `https://storage.googleapis.com/...` link inside text (wa.me cannot attach files) |
| behavior | opens WhatsApp app/web directly on the send screen — agent reviews and taps **Send** |
| fallback | invalid numbers (90+ in lists) are filtered before link generation |

### 16.5 Actions → Intent → Dashboard Metrics (recommendation set)

| # | Action (trigger) | Template | Intent class | Primary metric | Secondary metrics | Data source |
|---|---|---|---|---|---|---|
| 1 | Call outcome = not answered → send WA-FU-01 within 2h | WA-FU-01 | re-engagement | reply rate % | callback booked, link clicks | contacts call status (174) |
| 2 | Call outcome = busy/call later → WA-FU-02 next day 10 AM | WA-FU-02 | re-engagement | callback rate % | time-to-callback | call logs (25+) |
| 3 | Details sent ≥3 days ago, no reply → WA-FU-03 | WA-FU-03 | nurture | requirement confirmed % | quotation requests | Sheet11 (13 leads) |
| 4 | Rate requested (chat keyword 'rate') → WA-RT-01 instantly | WA-RT-01 | conversion | quotation sent count | order conversion % | WhatsApp rate threads |
| 5 | Quotation sent +7 days → WA-QT-01 | WA-QT-01 | conversion | quote→order % | revision requests | calling log (Sheet3) |
| 6 | New order in ERP → WA-ORD-01 | WA-ORD-01 | retention | ack rate % | change requests | ERP Orders (89, 10 new) |
| 7 | Partial dispatch in ERP → WA-DSP-01 | WA-DSP-01 | retention | customer ack % | balance-clearance days | Dispatch (44 partial) |
| 8 | Invoice age > terms (45d=859, 60d=384 invoices) → WA-PAY-01 weekly | WA-PAY-01 | collections | collected-in-week % | overdue ageing | sales registers |
| 9 | Delivery completed → WA-FBK-02 after 4h | WA-FBK-02 | feedback | feedback response % | avg rating | dispatch events |
| 10 | Expo lead imported (Packvision 111) → WA-EXP-01 in 24h | WA-EXP-01 | re-engagement | sample-request rate % | meeting booked | events module |
| 11 | New contact added (main list 152) → WA-NEW-01 | WA-NEW-01 | acquisition | first-reply % | opt-out % | contacts module |
| 12 | Low rating / issue words → create ticket + notify team | (spec Msg 4) | support | first-response time | resolution time, reopen % | feedback module |

### 16.6 Python API Sync — Model Chain with User-Selected Task/Subtask

```text
Dashboard UI (user picks):
  TASK     = follow_up | rates | order_update | feedback | payment | expo
  SUBTASK  = template_id (WA-FU-01...) + audience filter + tone (formal/casual/marathi)
      |
      v
GET  /api/llm/tasks            -> list available tasks
GET  /api/llm/plan/{task}      -> show plan (prompt, inputs, outputs) before running
POST /api/llm/run              -> {task, subtask, contacts[], model_pref}
      |
      v
Model chain (gemma_service.py):  gemma-3-27b-it -> gemma-3-12b-it
                                 -> gemini-2.5-flash -> gemini-2.0-flash
                                 -> safe placeholder fallback (always sendable)
      |
      v
Personalized messages -> review table -> per-row [wa.me OPEN-AND-SEND] button
                                     or POST /api/social/whatsapp/messages (queue)
                                     or POST /api/whatsapp/send (gateway, media OK)
```

| API | Purpose | Dashboard usage |
|---|---|---|
| `GET /api/llm/tasks` | list AI tasks | task dropdown |
| `GET /api/llm/plan/{task}` | preview plan | "what will happen" panel |
| `POST /api/llm/run` | run personalization (Gemma→Flash chain) | generate batch |
| `POST /api/social/whatsapp/messages` | queue messages | bulk send queue |
| `POST /api/whatsapp/send` | direct gateway send (supports media) | single/attachment send |
| `POST /api/whatsapp/webhook` | inbound replies | feedback loop input |
| `GET /api/kpi/outreach` | send/open/reply KPIs | outreach tiles |
| `POST /api/events/messages/send-due` | send scheduled follow-ups | daily batch |

### 16.7 Feedback Loop — Regular Execution

```text
        +----------------------+        every night (POST /api/cron/run)
        |  COLLECT             |<------- webhook replies, call logs, ERP events,
        |  (replies/events)    |         quotation responses, payments
        +----------+-----------+
                   v
        |  CLASSIFY            |  Gemma intent classification:
        |  intent + sentiment  |  interested / not-interested / rate-request /
        +----------+-----------+  order-query / complaint / payment-done / wrong-number
                   v
        |  UPDATE STATE        |  contact status, last-intent, next-best-action,
        |                      |  ticket create/close, opt-out honored
        +----------+-----------+
                   v
        |  ACT                 |  schedule next follow-up (max 1 reminder / 24–48h),
        |                      |  escalate complaints, push due messages (send-due)
        +----------+-----------+
                   v
        |  MEASURE             |  /api/kpi/* refresh: reply rate, intent mix,
        +----------------------+  conversion, feedback rating, resolution time
                   |
                   +----> loops back to COLLECT (daily cadence, weekly review)
```

| Cadence | Job | Endpoint |
|---|---|---|
| Real-time | inbound reply → intent + ticket/route | `POST /api/whatsapp/webhook` |
| Hourly | send due scheduled follow-ups | `POST /api/events/messages/send-due` |
| Nightly | full sync: contacts, replies, ERP status → recompute next actions | `POST /api/cron/run` |
| Weekly | payment reminders (WA-PAY-01), quotation ageing (WA-QT-01) | `POST /api/scheduler/run` |
| Monthly | template performance review → retire/rewrite low performers | governance + KPI review |

### 16.8 Dashboard Metric Tiles (powered by the loop)

| Tile | Metric | Source of truth |
|---|---|---|
| Outreach | messages sent / delivered / replied today | whatsapp gateway + webhook |
| Intent mix | interested vs not-interested vs rate-request vs complaint | Gemma classification |
| Follow-up health | due follow-ups, overdue, completed | events scheduler |
| Conversion | quotations sent → orders won (%) | ERP orders + calling log |
| Collections | overdue invoices, collected-this-week | sales registers |
| Satisfaction | avg rating, complaints open/resolved, resolution time | feedback module |
| Channel | wa.me clicks vs API sends vs replies | outreach KPIs |
| Model | Gemma vs Flash usage, fallback count, cost | `/api/kpi/costs`, `/api/governance/usage` |

> Implementation order: (1) template catalog + wa.me generator using current contact lists → (2) webhook +
> intent classification loop → (3) scheduler cadence → (4) KPI tiles. Templates above are drafts from real
> samples — verify WhatsApp Business template approval + consent before automated sending.
"""

with open(MD, "r", encoding="utf-8") as fh:
    content = fh.read()

# idempotent: drop any previous copy of section 16
marker = "\n---\n\n## 16. WhatsApp Template & Follow-Up Messaging System"
if marker in content:
    content = content.split(marker)[0]

updated = content.rstrip() + SECTION
with open(MD, "w", encoding="utf-8") as fh:
    fh.write(updated)
print("Markdown updated locally:", MD, f"({len(updated)} chars)")

creds, _ = google.auth.default()
client = storage.Client(credentials=creds)
bucket = client.bucket("kalika_enterprises")
blob = bucket.blob(GCS_DEST)
blob.upload_from_filename(MD)
print(f"Pushed to gs://kalika_enterprises/{GCS_DEST} ({os.path.getsize(MD)} bytes)")
