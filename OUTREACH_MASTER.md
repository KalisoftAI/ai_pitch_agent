# Kalika Outreach - Master Guide

Single source of truth for the Sales / Outreach workspace (FastAPI + React, deployed on Cloud Run).
This file is not merged with the older notes; they were removed and their content is folded in here.

Related: the Kalika ERP system guide (architecture diagrams + September-November 2026 changes) is kept in
`docs/Kalika_ERP_Current_System.md`. The `docs/` folder is local-only and git-ignored in this repository.

## 1. What the app does

- **Contacts** - imported sales contacts (Excel/GCS), searchable, de-duplicated, filtered by funnel data.
- **Marketing Companies** - step workflow: pick contacts -> choose channel -> personalise -> preview -> send -> track.
- **Templates** - email (HTML) and WhatsApp/WeChat (plain text) templates, GCS + Excel import.
- **Campaigns** - one campaign per channel per send, with review/approve, retry and per-recipient tracking.
- **Insights** - campaign analytics (sent/opened/failed/pending by day, channel, campaign, contact group).
- **Email connections** - Gmail OAuth / IMAP+SMTP mailboxes, sync status, retention, test send.
- **Field desk / Visits** - visit history, voice notes, rate calculator shortcuts.
- **Sales BI, KPIs, Feedback, Scheduler, UAT & ops** - adjacent modules in the same shell.

All user-facing strings are ASCII. Analytics are computed from `Campaign`, `CampaignMessage` and contact
tables; no mock campaign data is generated. The only curated data is the optional "Load sample records"
button on the visits screen, which inserts a short built-in sample set for format review.

## 2. Architecture

```
                        +-----------------------------------------------+
  Browser (React 18)    |  frontend/src                                 |
  desktop + mobile      |    main.jsx    shell, auth, topbar, nav       |
                        |    features.jsx dashboard, MarketingCompanies,|
                        |                 Templates, SalesBi, Kpis       |
                        |    styles.css  layout, tables, cards, charts  |
                        +----------------------+------------------------+
                                               | fetch(/api/...) via Vite
                                               | proxy (dev) or same origin
                                               v
        +-----------------------------------------------------------------+
        |  Cloud Run: FastAPI app  (sales_fastapi.main:app)               |
        |                                                                 |
        |  routers/                                                       |
        |    auth, marketing_companies, campaigns, templates, email,      |
        |    visits, contacts, kpis, ops, ...                             |
        |  templating.py   render / render_resolved / looks_html          |
        |  mail_sync.py    IMAP UID + Message-ID sync, retention          |
        |  services.py     EmailExtractor, MailSender (SMTP)              |
        |  scheduler.py    mail sync, retention, analytics, KG refresh    |
        |  static/         built Vite bundle at /static/assets            |
        +------+---------------------+--------------------+---------------+
               |                     |                    |
               v                     v                    v
        +-------------+      +----------------+    +-------------------+
        | Postgres /  |      | GCS bucket     |    | Gmail / SMTP      |
        | SQLite      |      | kalika_        |    | mailbox (IMAP     |
        | Campaign,   |      | enterprises    |    | BODY.PEEK, SMTP   |
        | Message,    |      | Kalika_gmail_  |    | send with         |
        | Contact,    |      | data/, sales-  |    | Message-ID and    |
        | Template... |      | metadata/...   |    | retries)          |
        +-------------+      +----------------+    +-------------------+
```

## 3. Request and send flow

```
User action                Frontend                        Backend
-----------                --------                        -------
Open app              ->  /auth/me, /config, /health   ->  auth + settings
Insights tab          ->  /campaigns/analytics?days=N   ->  Campaign + CampaignMessage
                      ->  /email/sync/analytics?days=N      aggregates (all channels)
Filter contacts       ->  /marketing-companies?filters   ->  filtered page + /count
Select all matching   ->  /marketing-companies/ids       ->  up to 20k ids (truncated flag)
Compose + Preview     ->  POST /campaigns/{id}/preview   ->  render_resolved per contact
Send now              ->  POST /campaigns               ->  create campaign + messages
                      ->  POST /campaigns/{id}/send      ->  send loop (SMTP / WhatsApp)
Send for review       ->  POST /campaigns (auto_send=0)  ->  status pending_review
Approve               ->  POST /campaigns/{id}/approve  ->  approved
Retry failed          ->  POST /campaigns/{id}/retry    ->  re-send failed messages
Email opened          <-  GET /campaigns/track/open     ->  1x1 pixel, sets opened_at
Review results        ->  GET /campaigns/{id}            ->  per-message log
Dashboard refresh     ->  both analytics endpoints      ->  live counters
```

Formats: WhatsApp/WeChat bodies must be plain text. `looks_html` is enforced on template create/update,
campaign create and send. HTML is allowed for email and rendered into a sanitized iframe preview.

## 4. Outreach workflow (UI steps)

```
Step 1 SELECT                 Step 2 CONFIGURE              Step 3 PREVIEW / SEND
+----------------------+      +----------------------+      +----------------------+
| search + filters     |      | channel:             |      | first-contact render |
| multi-select checkbox| ---> |   email / whatsapp / | ---> | unresolved token flag|
| Select page          |      |   both               |      | HTML-on-WA warning   |
| Select all matching  |      | template picker      |      | email-ready count    |
| group select         |      |   View / Edit        |      | WhatsApp-ready count |
| remove dupes         |      | subject + body       |      | channel validity     |
| sticky summary:      |      | compat panel if HTML |      | Send now / Review    |
|  N email / M whatsapp|      | image / video chips  |      | creates 1-2 campaigns|
+----------------------+      +----------------------+      +----------+-----------+
                                                                       |
                                                                       v
                                                  +------------------------------------+
                                                  | Campaign detail: status, sent/viewed|
                                                  | timestamps, errors, retry failed    |
                                                  +------------------------------------+
```

## 5. Data model (outreach core)

```
MarketingCompany 1 ---- n CampaignMessage n ---- 1 Campaign
  id                      id                       id
  company                 campaign_id              user_id
  contact_name            contact_id               name / channel
  designation (UI "-")    to_address               strategy / template_id
  email / phone           rendered_subject         status
  category (group)        rendered_body            total / sent_count / failed_count
  call_status             status                   created_at
  requirements            sent_at / opened_at
  funnel_stage            error / provider_id
  source_file/sheet       contact_name, image_url
```

- Tracking: emails embed a 1x1 pixel to `/campaigns/track/open?...` built from `request.base_url` (HTTPS in
  production). Opens set `CampaignMessage.opened_at`; the dashboard reads opens from messages with status
  `opened` (analytics `opened` field, surfaced as `outreach.delivered`).
- Channel counts: KPI "Sent" = email + WhatsApp messages accepted (status `sent` or `opened`); "Opened" =
  `opened` status; "Pending" = `pending_review`/`approved`/`queued` counted by `created_at`.
- Explicit `contact_ids` are never truncated; the old `.limit(filter.limit)` was removed.
- Route order: `GET /campaigns/analytics` is declared before `GET /campaigns/{campaign_id}` so the path
  parameter route cannot shadow it (previously returned 422 and broke the dashboard).

## 6. Dashboard reference (MarketingCompanies -> Dashboard)

Two calls, same range (`days` = 7 / 14 / 30 / 90, default 14):

1. `GET /api/email/sync/analytics?days=N` - mail sync counters, outreach KPIs, connection health.
2. `GET /api/campaigns/analytics?days=N` - channel, campaign and group breakdowns.

```
KPI row (click any tile for a drill-down modal)
+--------------+ +----------+ +--------+ +--------+ +--------+ +---------+
| Emails       | | Processed| | Sent   | | Opened | | Failed | | Pending |
| fetched      | | norm+GCS | | all ch | | pixel  | | errors | | review  |
+--------------+ +----------+ +--------+ +--------+ +--------+ +---------+

Health strip: mailboxes connected, IMAP host, last sync, GCS prefix, retention windows, dedup skipped

Charts
  1. Daily mail & outreach activity - stacked bars: fetched / processed / sent / failed
     (day click -> per-day counters, includes duplicates skipped and opened)
  2. WhatsApp vs Email outreach - horizontal bars sent / failed / pending, plus processed trend line
     (row click -> campaigns for that channel)
  3. Campaign performance (top 8) - sent/failed/pending bars
     (row click -> per-recipient message log)
```

Insights tab (`GET /campaigns/analytics`): totals for sent / opened / failed / pending / campaigns, daily
chart, by-channel table, by-campaign table (top 25) and by-contact-group table (top 15, joined on
`MarketingCompany.category`). `note` and `days` are returned so the UI can label the window.

## 7. Current data snapshot (local dev DB)

Source: `sales_pipeline.db` in the repo root, last written 2026-11-08. This is the local development
snapshot, not the production Cloud SQL database; production numbers must be read from the live app/API
with a signed-in account.

Core tables:

```
contacts                 8796     marketing_companies       1033
tally_sales              5902     campaign_messages            32
campaigns                  14     message_templates            26
whatsapp_messages          27     company_visits                3
erp_orders                 89     erp_dispatch                117
users                       7     email_connections             0
audit_logs                158     sync_runs                    12
```

Marketing companies:

```
with email                         481 / 1033
with phone                         536 / 1033
with category                      489 / 1033
funnel_stage                       all "awareness"
call_status   (blank) 643 | invalid number 126 | not answered 122 | busy now 42
              call later 14 | switched off 10 | invalid no 10 | unavailable 6
category      (blank) 544 | no requirement 26 | Details sent call if required 26
              Trading / general business 14 | not interested 11 | Manufacturer 6 ...
```

Campaign and message states (all time):

```
campaigns by channel/status
  email     completed 1 (10 recipients) | failed 1 (3) | partial 1 (3) | pending_review 3 (3)
  whatsapp  completed 1 (5 recipients)  | pending_review 7 (8)

campaign_messages
  sent           5   (campaign 1, WhatsApp, 2026-09-14)
  failed         6   (campaigns 10 and 11, no sent_at recorded)
  pending_review 21  (campaigns 2-9 and 12-14)
  opened         0

templates
  email 11 | whatsapp 12 | linkedin 2 | wechat 1
```

What the dashboard shows for the 14-day window ending 2026-11-16 (window starts 2026-11-03):

```
campaigns in window            12  (ids 3-14, all created 2026-11-07)
KPI Emails fetched              0  (no mailbox connected in this snapshot)
KPI Processed                   0
KPI Sent                        0  (sent messages are from the September WhatsApp campaign)
KPI Opened                      0
KPI Failed                      0  (KPI uses sent_at; failed rows have no sent_at)
KPI Pending                    11  (pending_review created inside the window)
channel bars: email 5 campaigns / 9 recipients / 3 failed
              whatsapp 7 campaigns / 8 recipients / 0 failed
```

Data-quality note visible in this snapshot: campaign counters and message rows disagree - `failed_count`
sums to 3 while 6 messages have status `failed` (campaign 10 is `partial` with 3 failed messages but a 0
counter, campaign 11 has 3/3). Analytics keep both views: campaign counters drive the channel bars, message
rows drive the KPI and opens.

## 8. Local development

Backend (Python 3.11+ with project deps):

```powershell
C:\Python314\python.exe -m uvicorn sales_fastapi.main:app --reload --port 8000
```

Frontend:

```powershell
npm --prefix frontend install
npm --prefix frontend run dev     # http://localhost:5173, proxies /api to :8000
npm --prefix frontend run build   # writes sales_fastapi/static/assets, served by FastAPI
```

Database: SQLite by default (`SQLITE_PATH`), Postgres via `DATABASE_URL` / `POSTGRES_*` /
`CLOUD_SQL_CONNECTION_NAME`. Migrations: `alembic upgrade head` (latest `0011_campaign_contact_name`).

### Environment variables (most used)

| Area | Variables |
| --- | --- |
| App | `ENV`, `PROJECT_NAME`, `FRONTEND_URL` |
| DB | `DATABASE_URL`, `SQLITE_PATH`, `POSTGRES_*`, `CLOUD_SQL_CONNECTION_NAME` |
| GCP | `GOOGLE_CLOUD_PROJECT`, `GCS_BUCKET_CONTACTS`, `GCS_PATH_CONTACTS`, `GCS_BUCKET_MEDIA`, `GCS_BUCKET_MAIL`, `GCS_PATH_GMAIL`, `GCS_PATH_VISITS`, `GCS_PATH_INSTORE_MAILS` |
| Auth | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_ALLOWED_DOMAINS`, `GOOGLE_ALLOWED_EMAILS`, `GOOGLE_REDIRECT_URI`, `AUTH_DEV_MODE`, `AUTH_DEV_ALLOWED_EMAILS` |
| Mail | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `IMAP_HOST`, `IMAP_PORT`, mailbox OAuth settings |
| Mail sync | `MAIL_SYNC_BATCH` (20-50), `MAIL_RETENTION_RAW_DAYS` (180), `MAIL_RETENTION_PROCESSED_DAYS` (365), `MAIL_RETENTION_ATTACHMENTS_DAYS` (90), `MAIL_RETENTION_LOGS_DAYS` (365) |
| Sales Ops mail | `SALES_OPS_INSTOR_MAILBOX` (defaults to `GMAIL_ADDRESS_KALIKA2`), `SALES_OPS_INSTOR_APP_PASSWORD`, `SALES_OPS_INSTOR_SENDERS`, `SALES_OPS_INSTOR_SYNC_LIMIT` |
| Knowledge graph | `KNOWLEDGE_GRAPH_GCS_PREFIX`, `KNOWLEDGE_GRAPH_CHAT_ENABLED`, `KNOWLEDGE_GRAPH_REFRESH_DAYS` |
| Cache | `REDIS_URL`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB` |

## 9. Auth and access

- Google Sign-In (`/auth/google`) for allowed domains/emails, plus password login (`/auth/password`).
- Token in `sessionStorage` (`sales_token`); `request()` clears it and emits `auth-expired` on 401.
- Roles gate admin-only operations (imports, sync, UAT).

## 10. API map (high level)

- `POST /auth/google`, `POST /auth/password`, `GET /auth/me`, `GET /config`, `GET /health`
- `GET /marketing-companies` (filters: `q, category, call_status, funnel_stage, sales_progress,
  due_follow_up, requirements_only, has_phone, has_email, missing_email, missing_phone, ids, sort, limit,
  offset`), `GET /marketing-companies/count`, `GET /marketing-companies/ids`
- `GET /marketing-companies/stats` (cached), `/activity`, `/duplicates`, `/segments`, `/sources`;
  `POST /marketing-companies/import`, `/sync`; `PATCH /marketing-companies/{id}`
- `GET/POST /templates`, `PATCH/DELETE /templates/{id}`, `/templates/meta`, `/seed`, `/sync-gcs`,
  `/sync-specific`, `/import-whatsapp`, `/upload`
- `POST /campaigns`, `GET /campaigns`, `GET /campaigns/analytics?days=N`, `GET /campaigns/{id}`,
  `/campaigns/{id}/preview`, `/approve`, `/send`, `/retry`, `GET /campaigns/track/open`
- Email: `/email/connections`, `/email/sync`, `/email/sync/state`, `/email/sync/analytics?days=N`,
  `/email/retention`, `/email/test-send`, default-connection endpoints
- Sales Ops mail desk: `GET /v1/sales-ops/mail/instor` (date/time-grouped Instor India mails with AI
  summaries; throttled auto-sync), `POST /v1/sales-ops/mail/instor/sync` (manual/IMAP pull)
- Visits: `GET /visits`, `POST /visits/samples` (built-in sample records only)

## 11. Manual test path

1. Insights tab: tiles Sent/Opened/Failed/Pending/Campaigns, daily chart, channel and campaign breakdowns.
2. Contacts: filters, "Select page", "Select all matching", group select, remove dupes; summary counts.
3. Templates: View (iframe for email, bubble for WhatsApp), Edit raw body, channel select, save validation.
4. Personalisation: variables resolved for the first selected contact; unresolved tokens flagged.
5. Preview: channel-valid recipients, HTML-on-WhatsApp warning, total approved count.
6. Send now / Send for review; both-channel sends create two campaigns.
7. Campaign detail: per-message status, timestamps, errors, retry failed.

## 12. Testing and CI

```powershell
C:\Python314\python.exe tests_e2e_mail.py     # 20 in-process checks with fake IMAP/GCS/SMTP
C:\Python314\Scripts\ruff.exe check sales_fastapi
npm --prefix frontend run build
```

CI (`.github/workflows/ci.yml`) also runs `ruff format --check`, `pytest --cov-fail-under=70` and a
model/migration parity check.

## 13. Deployment

- Push to `main`; CI builds and CD deploys to Cloud Run:
  `https://kalisoft-sales-19782268668.asia-south1.run.app`.
- Health: `GET /api/health` (expects `database: ok`).
- Static assets are served from `/static/assets/index-<hash>.js|css` (not `/assets`).
- After deploy, confirm the served bundle hash matches `sales_fastapi/static/assets`.

## 14. Known gaps / follow-ups

- `MailSyncState` has no Alembic migration, so the model/migration parity CI job fails
  (`migrations/versions/0011_campaign_contact_name.py` is the latest). Deferred to avoid an unnecessary
  migration; add `0012_mail_sync_state.py` when approved.
- CI already fails on unrelated pre-existing lint/coverage issues.
- `MarketingCompany` has no `designation` column; the UI shows `-` rather than inventing one.
- The live Kalika Sales Tracker feed is not wired; the visits button inserts curated sample records only.
- Campaign counters and message rows can disagree (see snapshot note); the dashboard surfaces both.
- Visits, Scheduler and UAT modules are functional but outside the core outreach workflow.
