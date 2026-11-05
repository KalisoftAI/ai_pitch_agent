# Kalisoft AI Sales Pipeline - Architecture, Current & Future

> Single FastAPI service + React SPA, deployed to Cloud Run from GitHub Actions.
> One codebase, three environments (`main` -> production, `UAT` -> staging,
> `DEV` -> development). Cost-first: Gemma-first LLM chain, scaled-to-zero Cloud
> Run, JSON-in-GCS for review data (no graph SQL tables).

---

## 1. End-to-end architecture

```text
                              +--------------------------------------------------+
                              |                     USERS                        |
                              |   Admin (Kalika)   Sales (field desk)   Viewer    |
                              +-----------------------+--------------------------+
                                                      | HTTPS
                                                      v
 +--------------------------------------------------------------------------------+
 |                         FRONTEND  (React + Vite SPA)                            |
 |  sales_fastapi/static/assets/index-*.js  +  index-*.css   (served by FastAPI)   |
 |  Tabs: Dashboard . Sales BI . Field Desk . Message Studio . Campaigns .         |
 |        Events . Approvals/Review (admin) . Graph review (DEV/UAT only) .        |
 |  Auth: password login + Google sign-in (optional) . Env badge from /api/health  |
 +--------------------------------------+-----------------------------------------+
                                        |  /api/*  (JSON, Bearer JWT)
                                        v
 +--------------------------------------------------------------------------------+
 |                    FASTAPI APP  (one Cloud Run container)                       |
 |  middleware: explicit CORS . TrustedHost . rate-limit . PII redaction .         |
 |              security headers . request-size cap . audit log                    |
 |                                                                                 |
 |  routers  (~220 /api routes)                                                    |
 |    auth . users . team . contacts . sales . journey . visits . events           |
 |    erp . tally . dashboard . kpi . pipeline . catalog . category-campaigns      |
 |    campaigns . templates . email . instore . marketing-companies . social       |
 |    whatsapp . voice . feedback . governance . llm . ops . security              |
 |    sync . approvals . knowledge-graph . scheduler . health . config             |
 |                                                                                 |
 |  layers:  routers -> schemas -> services -> models -> governance/audit/llm      |
 +----+-------------+--------------+----------------+--------------+--------------+
      |             |              |                |              |
      v             v              v                v              v
 +---------+  +-----------+  +------------+  +------------+  +------------------+
 | Cloud   |  | Secret    |  | GCS        |  | LLM Router |  | Scheduler        |
 | SQL     |  | Manager   |  | buckets    |  | Gemma ->   |  | APScheduler +    |
 | Postgres|  | SECRET_KEY|  | datapoint/ |  | Flash ->   |  | POST /cron       |
 | sales   |  | DATABASE  |  | ERP/Tally/ |  | echo       |  | 2h sync, daily   |
 | data    |  | URL       |  | mail/KG    |  | cost ledger|  | reports, etc.    |
 +---------+  +-----------+  +-----+------+  +-----+------+  +------------------+
                                    |               |
                                    v               v
                     +----------------------------------------------------+
                     | External: Gemini API . Google OAuth/Gmail .        |
                     | YouTube Data API . WhatsApp/WeChaty .              |
                     | LinkedIn/Reddit signals . Google Analytics (GA4)   |
                     +----------------------------------------------------+
```

### Request path
`Browser -> Cloud Run (FastAPI) -> router -> service -> SQLAlchemy model (Cloud SQL)
-> Pydantic schema -> JSON`. Long/async work goes through the scheduler queue and
`SyncRun`/audit tables; GCS is the source of truth for bulk source files.

---

## 2. Environments & deploy pipeline

| Env | Git branch | Cloud Run service | URL (asia-south1) | App `ENV` | `DEPLOY_ENV` | Max inst. |
|-----|-----------|-------------------|-------------------|-----------|--------------|-----------|
| Prod | `main` | `kalisoft-sales` | `https://kalisoft-sales-19782268668.asia-south1.run.app` | `production` | `prod` | 3 |
| Staging | `UAT` | `kalisoft-sales-uat` | `https://kalisoft-sales-uat-19782268668.asia-south1.run.app` | `staging` | `uat` | 2 |
| Dev | `DEV` | `kalisoft-sales-dev` | `https://kalisoft-sales-dev-19782268668.asia-south1.run.app` | `development` | `dev` | 1 |

| Pipeline | Trigger | What it does |
|----------|---------|--------------|
| CI | PRs to `main`/`UAT`/`DEV` + pushes | lint + tests + frontend build (gate only) |
| CD | push to `main`/`UAT`/`DEV` (or manual dispatch) | build image in Actions -> push to Artifact Registry -> `gcloud run deploy` -> smoke test `/api/health` |

Deploy hardening (enforced in `.github/workflows/cd.yml` + `config.py`):
- `CORS_ORIGINS` / `ALLOWED_HOSTS` must be **explicit** HTTPS origins / hostnames - wildcards are rejected both in CI and at app startup in production.
- `GOOGLE_CLIENT_ID` comes from a GitHub secret (not a placeholder); `GOOGLE_CLOUD_PROJECT` from a var.
- Secrets are bound via `--update-secrets` (`SECRET_KEY=SALES_SECRET_KEY:latest`, `DATABASE_URL=SALES_DATABASE_URL:latest`, plus optional `GEMINI_API_KEY`, `GOOGLE_CLIENT_SECRET`, `SMTP_PASSWORD` when present).
- Env vars use the `^@^` delimiter so URLs containing `,`/`:` are safe.

---

## 3. Data sources -> sync -> storage

| Source | Location | Sync | Cadence | Lands in |
|--------|----------|------|---------|----------|
| ERP report | `gs://kalika_enterprises/ERP-V1/Reports/kalika_report_*.xlsx` | `erp_dispatch_sync` | daily 06:00 | `erp_orders`, `erp_dispatch` |
| Tally registers | `gs://kalika_enterprises/kalika_sales2026/*.xls` | `tally_sales_sync` | daily 06:15 | `tally_sales` |
| Marketing list | `gs://kalika_enterprises/sales-contacts/RECENT_marketing_list_*.xlsx` | `sync_all_data` -> `_sync_marketing` | every 2h | `marketing_companies` |
| Contacts | `gs://kalisoftai-datahub/all-sales-contacts-data` | `sync_gcs_contacts` | every 6h | `contacts` |
| In-store mail | Gmail/IMAP mailbox | `instore_mail_sync` | daily 06:45 | `company_visits.mail_chat_details` + GCS insights JSON |
| Knowledge graph | derived from synced data | `knowledge_graph_sync` | weekly (7d), DEV/UAT only | GCS JSON (`KNOWLEDGE_GRAPH_GCS_PREFIX`) |
| Business KPI | derived | `kpi_snapshot` | nightly 23:00 | KPI snapshot tables |

`POST /api/sync/all` (admin) runs ERP + Tally + marketing + (DEV/UAT) graph in one
sweep; `GET /api/sync/status` reports the latest `SyncRun` per job. The scheduler
runs the same sweep every 2 hours (`sync_all_data`, cron `0 */2 * * *`).

### GCS layout (logical)

```text
gs://kalika_enterprises/          # source of truth (ERP, Tally, marketing, mail, docs)
gs://kalisoftai-datahub/          # normalized contacts + review JSON
  all-sales-contacts-data/        # contact CSVs
  sales-app/knowledge_graph/      # DEV/UAT graph snapshots + feedback (JSON)
  sales-app/instore_mails/        # mail insight JSON
```

---

## 4. AI / LLM (cost-first)

`ModelRouter` walks a per-task chain and stops at the first success; every call is
recorded in the usage ledger with a cost estimate.

| Model | Micro-USD per 1K tokens (in / out) | Role |
|-------|-----------------------------------|------|
| `ollama` (local) | 0 / 0 | free local fallback |
| `echo` | 0 / 0 | deterministic last resort |
| `gemma-4-27b-it` | 100 / 400 | primary SLM |
| `gemini-2.0-flash` | 100 / 400 | cloud fallback |
| `gemini-2.0-flash-lite` | 50 / 200 | cheapest cloud tier |
| `gemini-2.5-pro` | 1250 / 5000 | rare heavy tasks only |

Default chain: `gemma -> local_medium -> cloud_flash` (outreach + knowledge-graph chat);
small tasks: `local_small -> cloud_flash -> local_medium`. When `LLM_ENABLED=false`
or no key is present, the router degrades to `echo`/deterministic answers (never 500).

---

## 5. Human-in-the-loop

| Surface | Gate | Behaviour |
|---------|------|-----------|
| Approvals (`/api/approvals`) | admin decides | LLM/system proposes subtasks with confidence; human accepts/rejects; issues log shows only failures |
| Knowledge graph review (`/api/knowledge-graph/reviews`) | DEV/UAT only, human | ambiguous company edges are `pending` until a human accepts/rejects; accepted edges feed the optional assistant |
| Chat feedback (`/api/knowledge-graph/feedback`) | human review | corrections stored for review; never auto-train model weights |

Knowledge-graph review is **disabled in production** by design (env gate in
`routers/knowledge_graph.py` + `routers/system.py`), so shipping it to `main` is safe.

---

## 6. API surface (stats)

| Group | Routes | Group | Routes | Group | Routes |
|-------|-------:|-------|-------:|-------|-------:|
| auth | 9 | erp | 13 | events | 12 |
| social | 11 | ops | 10 | email | 10 |
| voice | 10 | catalog | 10 | knowledge-graph | 9 |
| visits | 9 | team | 8 | contacts | 8 |
| templates | 8 | campaigns | 7 | users | 7 |
| marketing-companies | 6 | category-campaigns | 6 | sales | 6 |
| instore | 6 | approvals | 5 | tally | 5 |
| journey | 5 | kpi | 5 | pipeline | 5 |
| governance | 5 | whatsapp | 4 | ai | 4 |
| scheduler | 4 | llm | 3 | sync | 2 |
| health/config/security/cron/integrations/feedback | 2-1 each | | | **Total** | **~220** |

---

## 7. Scheduler cadence (key jobs)

| Job | Cron (UTC) | Purpose |
|-----|-----------|---------|
| `sync_all_data` | `0 */2 * * *` | ERP + Tally + marketing refresh (+ weekly graph in DEV/UAT) |
| `erp_dispatch_sync` | `0 6 * * *` | ERP report -> dispatch/orders |
| `tally_sales_sync` | `15 6 * * *` | Tally registers -> sales |
| `instore_mail_sync` | `45 6 * * *` | mailbox -> linked insights |
| `voice_transcription_sync` | `30 3 * * *` | call recordings -> tone/lead analysis |
| `daily_guardrail_checks` | `30 14 * * *` | config/security/data/LLM preflight |
| `daily_uat_report` | `30 16 * * *` | UAT daily digest |
| `kpi_snapshot` | `0 23 * * *` | nightly KPI snapshot |

---

## 8. Security & secrets

- Transport: HTTPS only; TrustedHost + explicit CORS; security headers; request-size cap; rate limiting.
- Auth: JWT (HS256) via `SECRET_KEY`; password login + optional Google OAuth; admin role gate (`require_admin`).
- Secrets: values live in **GCP Secret Manager** (`SALES_SECRET_KEY`, `SALES_DATABASE_URL`, optional `GEMINI_API_KEY`, `GOOGLE_CLIENT_SECRET`, `SMTP_PASSWORD`) bound at deploy; CI uses Workload Identity Federation (no long-lived keys).
- Rotation: see [`docs/SECRETS_ROTATION.md`](SECRETS_ROTATION.md).
- Local `.env` is untracked and must never be committed or echoed.

---

## 9. Current vs future

### Current (shipped / in this release)
- Dashboard + Sales BI + Field Desk + Message Studio + Campaigns + Events.
- ERP/Tally/marketing/contacts/in-store-mail sync with `SyncRun` status + 2h sweep.
- Approvals console (human decision on proposed subtasks) + issues log.
- DEV/UAT knowledge-graph review (JSON in GCS, human-verified edges, optional Gemma chat).
- Gmail SMTP/IMAP fallback defaults (`GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD`).
- Marketing pipeline fields: `funnel_stage`, `sales_progress`, `next_action`, `follow_up_date`.
- Hardened CD (explicit CORS/hosts, real client id, Secret Manager bindings) + production config validation.

### Future (requested roadmap)
| Item | Intent | Suggested lightweight approach |
|------|--------|-------------------------------|
| Daily "datapoint" sync to GCS | persist normalized results with a `datapoint` tag daily | reuse `sync_all_data`; write one tagged JSON/parquet per run under `.../datapoints/YYYY-MM-DD.json`; add `datapoint` field to `SyncRun.detail` |
| Biweekly analytics report | scheduled report + upload notification | add a `biweekly_analytics_report` scheduler task; render markdown/JSON to GCS; notify via existing WhatsApp/email pipeline |
| Template verification | validate template body/variables before send | add `POST /api/templates/{id}/verify` (render with sample vars, check unresolved placeholders); surface status in Message Studio |
| Mail-chat checks | summarize/link in-store mail threads | extend `instore_mail` insights with thread grouping + `mail_chat_details` review flag |
| Human-expert-only review | no auto-actions without approval | route all new proposals through `/api/approvals` + KG review queues |
| Minimal Gemma model | cheapest viable model | prefer `gemma-4-27b-it` locally, `gemini-2.0-flash-lite` as cheap cloud tier; keep budget ledger |
| UI refinement | end-to-end polish | incremental component passes in `features.jsx` + `styles.css` |
| Cost-effective deploy | lowest spend | scale-to-zero, min-instances 0, Gemma-first, JSON-in-GCS (no graph DB) |

These future items are **not implemented in this release**; they are scoped here so
they can be built behind flags and validated in DEV/UAT before production.

---

## 10. Verification

```powershell
# backend
python -m pytest -q
python -m ruff check sales_fastapi tests migrations
# frontend
cd frontend; npm run build
# live (prod)
curl -fsS https://kalisoft-sales-19782268668.asia-south1.run.app/api/health
```
