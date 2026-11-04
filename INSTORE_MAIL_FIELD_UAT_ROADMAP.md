# Instore Mail, Field Desk & UAT Roadmap

Status: implemented foundation · owner: Kalisoft AI / Kalika Enterprises
Last updated: 2026-11-03

## 1. Goal

Turn scattered mailbox and field signals into one operating loop:

1. Extract **instore mails** from a connected Gmail/IMAP mailbox or the existing
   `gcs_data/interaction_dump.json`.
2. Normalize sender, intent, attachments, date and contact link.
3. Publish a **GCS snapshot** plus graph nodes/edges and a missing-link report.
4. Surface counts, latest mails, missing links and field visits on the dashboard.
5. Let a **field executive** capture person met, meeting location, previous
   discussion, mail/chat trail and a map link against each company visit.
6. Answer questions with a **dynamic prompt** across Gemma 4 → local SLM →
   Gemini flash → echo, with a human-expertise selector and cost tracking.
7. Keep everything on the nightly scheduler and verify it through UAT.

## 2. Architecture

```text
                       ┌───────────────────────────────────────────┐
                       │              KALIKA COMMAND CENTER        │
                       │  dashboard summary / instore mail desk     │
                       └───────────────▲───────────────▲───────────┘
                                       │               │
                   /api/instore/*      │               │  /api/dashboard/summary
                   /api/visits         │               │  (instore + field blocks)
                                       │               │
┌──────────────────────┐      ┌────────┴─────────┐   ┌─┴────────────────────────┐
│ Gmail API / IMAP     │─────▶│  instore_mail.py │──▶│  gcs_data/instore_mails  │
│ interaction_dump.json│      │  normalize/link  │   │  .json (local snapshot)  │
└──────────────────────┘      │  insights/graph  │   └─────────┬────────────────┘
                              └────────┬─────────┘             │
                                       │                       ▼
                              ┌────────▼─────────┐   ┌──────────────────────────┐
                              │ SyncRun + audit  │   │ gs://kalika_enterprises/ │
                              │ ModelUsage cost  │   │ sales-app/instore_mails/ │
                              └──────────────────┘   └──────────────────────────┘
                                       ▲
                       ┌───────────────┴────────────────┐
                       │ scheduler: instore_mail_sync   │
                       │ daily 06:45 + manual sync      │
                       └────────────────────────────────┘

FIELD SAMPLE
company_visits += meet_person, meet_home_location, previous_discussion,
                  mail_chat_details, map_location
        │
        └──▶ dashboard.field.latest + Company history table + map link
```

## 3. Data contracts

### 3.1 Snapshot `gcs_data/instore_mails.json`

| Key | Meaning |
| --- | --- |
| `generated_at` | ISO timestamp |
| `data_available` | at least one mail was normalized |
| `source` | `gmail`, `imap`, `dump`; mailbox, scanned count, errors |
| `insights.total / linked / unlinked` | mail and contact-link counts |
| `insights.by_intent` | quote_request, order, payment, complaint, meeting_request, general |
| `insights.attachments / attachment_purposes` | file count and classified purpose |
| `insights.high_priority` | quote/order/payment/complaint/meeting |
| `insights.monthly_volume` | `YYYY-MM -> count` |
| `insights.forecast_next_month_mails` | 3-month rolling average |
| `insights.accuracy_pct` | weighted link/date/intent coverage |
| `mails[]` | normalized mail record incl. `from_email`, `domain`, `to`, `attachments`, `contact_id`, `link_status` |
| `missing_links` | count, domain counts, top 25 samples |
| `graph` | nodes, edges, stats (nodes/edges by kind/type, density) |

### 3.2 GCS locations

| Purpose | Bucket | Prefix |
| --- | --- | --- |
| Current snapshot | `GCS_BUCKET_MAIL` (default `kalika_enterprises`) | `GCS_PATH_INSTORE_MAILS` (`sales-app/instore_mails/`) |
| Daily archive | same | `sales-app/instore_mails/archive/YYYY-MM-DD-instore_mails.json` |
| Refined missing links | `GCS_BUCKET_MAIL` | local `gcs_data/graph/missing_links.json` ? `sales-app/instore_mails/graph/` |
| Mail graph extract | `GCS_BUCKET_MAIL` | local `gcs_data/graph/mail_nodes.json`, `mail_edges.json` ? `sales-app/instore_mails/graph/` |

### 3.3 Visit sample fields

| Field | Type | Use |
| --- | --- | --- |
| `meet_person` | varchar(255) | Who the executive actually met |
| `meet_home_location` | varchar(255) | Plant/office/home location |
| `previous_discussion` | text | Last discussion point |
| `mail_chat_details` | text | Mail/chat date, subject, sender |
| `map_location` | varchar(512) | Google Maps URL for routing |

Migration: `migrations/versions/0007_instore_visits.py`.
Idempotent dev fallback: `sales_fastapi/database.py::_ensure_columns`.

## 4. KPI definitions

| KPI | Formula | Good |
| --- | --- | --- |
| Mail volume | count of normalized mails in snapshot | trend stable/up |
| Contact-link rate | `linked / total` | ≥ 70% |
| Missing links | unlinked senders | falling |
| Quote velocity | `quote_request` per month | trend up |
| Order-mail count | `order` intent | trend up |
| Attachment coverage | mails with ≥1 attachment / total | ≥ 25% |
| Link accuracy | 0.5 link + 0.3 date + 0.2 intent | ≥ 85% |
| Field follow-ups | visits with `follow_up_date >= today` and not closed | reviewed daily |
| Chat cost | `ModelUsage.cost_micros` for `instore_mail_chat` | within monthly budget |
| Fallback rate | `fallback_used` calls / total | falling |

## 5. Phases

### Phase 0 — Discovery and data inventory (done)
- Inventory the GCS workbooks, interaction dump, graph exports and app DB.
- Confirm existing contact fields: email, phone, domain, company.
- Confirm existing LLM chain and model catalog (`gemma-4-27b-it`, flash).

### Phase 1 — Mail extraction (done)
- `sales_fastapi/instore_mail.py`: normalize mail, infer intent, classify
  attachments, link by email → phone → domain → company.
- `GmailExtractor.fetch_emails` now returns attachment metadata.
- IMAP fallback remains available through `EmailExtractor`.
- Dump fallback keeps the demo and offline refinement working.

### Phase 2 — Snapshot and GCS pipeline (done)
- `save_insights` writes the local cache and uploads current + daily archive.
- `load_insights` prefers local, then GCS, then an empty snapshot.
- `POST /api/instore/sync` records `SyncRun(job="instore_mail_sync")` and audit.
- `scripts/refine_instore_data.py` refreshes dump → snapshot + graph extracts.

### Phase 3 — Missing links and graph refinement (done, next iteration)
- Missing links grouped by sender domain and exposed as samples.
- Graph nodes: mail, sender, domain, intent, attachment, contact, missing_link.
- Graph edges: `SENT_BY`, `FROM_DOMAIN`, `HAS_INTENT`, `HAS_ATTACHMENT`,
  `LINKED_TO_CONTACT`, `MISSING_IN_CONTACTS`.
- `scripts/refine_instore_data.py` uploads `missing_links.json`,
  `mail_nodes.json` and `mail_edges.json` under `sales-app/instore_mails/graph/`.
- Next: merge these mail graph extracts into the main `nodes.json` / `edges.json`
  used by the graph database.

### Phase 4 — Dashboard and field desk (done)
- Dashboard `instore` block: total, linked, missing, intents, attachments,
  accuracy, forecast, graph stats, latest mails.
- Dashboard `field` block: visits, companies, this month, follow-ups,
  by-sales-person, latest visits with new sample fields.
- Rule-based recommendations when there is no snapshot or missing links exist.
- `Company history` captures and displays person, location, previous
  discussion, mail/chat details and a map link.

### Phase 5 — Dynamic prompt, Gemma 4 and human expertise (done)
- `GET /api/instore/prompts` returns the model ladder and five expertise lenses:
  sales strategist, key account manager, technical advisor, finance & pricing,
  field executive.
- `POST /api/instore/ask` injects the live snapshot into the prompt and routes:
  requested model → local SLM → Gemma 4 → Gemini flash → echo.
- Every call records `ModelUsage(task="instore_mail_chat")` for KPI/cost
  reporting and an audit event. Guardrails redact PII and cap input/output.

### Phase 6 — Scheduler and operations (done)
- `instore_mail_sync` added to `STANDARD_TASKS` at `45 6 * * *`.
- Manual sync is available from the Instore mails page.
- Next: process the scheduler queue in a worker (Cloud Run job or Redis worker)
  so the cron entry performs the sync without a user request.

### Phase 7 — UAT (one-week window)
- Use `DEPLOY_ENV=uat`, `UAT_ENABLED_UNTIL=2026-11-06`.
- Daily digest at 22:00 IST, weekly review Monday 20:00 IST.
- Human review remains required for prompts and field updates.

| Check | Pass condition |
| --- | --- |
| `GET /api/instore/summary` | 200 and a timestamp |
| `POST /api/instore/sync` | mail count > 0, `gcs_uploaded` true when ADC is set |
| Missing links | count and samples match the mailbox |
| `/api/instore/ask` | answer cites mails, records ModelUsage |
| Visit capture | five new fields round-trip through create/list |
| Dashboard | `instore` and `field` blocks render without error |
| Scheduler | `instore_mail_sync` listed with its cron |
| Logo | visible on login, sidebar and loading screen |
| Cost | instore chat cost within monthly budget |

### Phase 8 — Rollout and next scope
- Fix missing sender links from the dashboard samples.
- Add attachment body download for Gmail (currently metadata only).
- Merge mail graph extracts into the main graph and deduplicate senders.
- Add per-executive route plan using `map_location`.
- Add automatic draft follow-up replies with human approval.
- Extend cost/KPI dashboards with fallback rate and mail-to-order conversion.

## 6. API summary

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/instore/summary` | Snapshot KPIs, missing links, graph stats |
| GET | `/api/instore/mails` | Latest normalized mails (`limit`, `intent`, `only_missing`) |
| GET | `/api/instore/graph` | Mail graph nodes/edges |
| POST | `/api/instore/sync` | Fetch mailbox/dump, link, save local + GCS, audit |
| GET | `/api/instore/prompts` | Dynamic prompt preview, models, expertise |
| POST | `/api/instore/ask` | Snapshot-grounded answer with model fallback |

## 7. Commands

```powershell
# Backend checks
ruff check sales_fastapi tests
python -m pytest tests/test_instore.py -q

# Refresh local snapshot and graph extracts (no upload)
python scripts/refine_instore_data.py --no-upload

# Refresh and upload to GCS (needs ADC)
python scripts/refine_instore_data.py

# Migration
alembic upgrade head

# Frontend build into sales_fastapi/static
cd frontend
npm run build
```

## 8. Risks and guardrails

- **PII**: guardrails redact PII before any model call; do not log bodies.
- **Secrets**: `.env` and mail passwords are git-ignored; never commit them.
- **GCS fallback**: upload failure is non-fatal; local snapshot stays usable.
- **No live mailbox**: dump fallback is clearly labelled in `source.kind`.
- **Model cost**: flash is a fallback only; Gemma 4/local SLM is preferred.
- **Human review**: field updates and prompt changes still require approval.
