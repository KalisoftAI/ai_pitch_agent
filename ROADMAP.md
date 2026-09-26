# Kalisoft AI Sales Pipeline — Roadmap & Implementation

A FastAPI sales pipeline that ingests contacts (GCS + manual), segregates them by
**domain / intent / context**, extracts email & LinkedIn signal via **IMAP + SMTP**,
prepares **WhatsApp → Reddit/LinkedIn/YouTube** outreach, and is secured with
**Google Sign-In (ADC)**, **Guardrails**, **Data Governance** and a
**cost-optimised small-language-model router (Gemma 4)**.
Runs on **Cloud Run**, backed by **Postgres** (local SQLite → Cloud SQL) and **Redis**.

> Status: security/governance/SLM/outreach phases implemented and **live in production** —
> 71 backend tests green, coverage 74%, `ruff` clean, `bandit -ll` clean, `alembic check` no drift.
> **ADC (Application Default Credentials) update: DONE** — Google-secured APIs (GCS, YouTube
> Data API v3, future Gmail OAuth) authenticate via ADC on Cloud Run and via
> `GOOGLE_APPLICATION_CREDENTIALS` locally. Working UI with basic features is live.
> Full exhaustive reference: [`docs/IMPLEMENTATION_ROADMAP.md`](docs/IMPLEMENTATION_ROADMAP.md).

---

## GCP Context

| GCP Service | Role in this pipeline | Status |
|---|---|---|
| **Cloud Run** | Hosts the FastAPI backend (`sales-api`) and serves the built React static bundle | ✅ Live in prod |
| **Cloud SQL (Postgres)** | Primary relational store (users, contacts, campaigns, audit, model usage) | ✅ Migrated from SQLite |
| **Cloud Storage (GCS)** | `kalisoftai-datahub` bucket — contact files (`all-sales-contacts-data/`), GCS mirror per user | ✅ Live |
| **Secret Manager** | All secrets (DB password, OAuth client secret, API keys) — never in code | ✅ Live |
| **Artifact Registry** | Docker images with cleanup policy | ✅ Live |
| **Cloud Scheduler** | Cron → `POST /api/scheduler/run` (task queue) | 🔶 Configured, Redis worker pending |
| **Workload Identity Federation** | GitHub Actions → Cloud Build → Cloud Run deploys (keyless) | ✅ Live |
| **ADC** | Application Default Credentials for all Google API calls | ✅ **Updated & working** |
| **YouTube Data API v3** | Company/tech video signal scan (Google-secured API) | 🔶 Stub ready, key pending |
| **BigQuery** | `analytics.*` event spine for KPI warehouse | ⬜ Future scope |
| **Knowledge catalog + Graph DB** | Entity graph of contacts ⇄ companies ⇄ signals (see §10) | ⬜ Future scope |

---

## 1. ASCII Flow Diagram — secure request path

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                     KALISOFT SALES — SECURE REQUEST PATH                      │
│                                                                              │
│  Browser / React (frontend/) ─┐                                              │
│                               v                                              │
│                    ┌──────────────────────────┐  413 size · 429 rate         │
│                    │  RequestGuardrails        │  CSP · HSTS · nosniff       │
│                    └────────────┬─────────────┘                             │
│                                 v                                            │
│                    ┌──────────────────────────┐  host allow-list            │
│                    │  TrustedHostMiddleware    │                             │
│                    └────────────┬─────────────┘                             │
│                                 v                                            │
│   Auth (Google ID token) ─► JWT ─► get_current_user                          │
│        │                                                                     │
│        ├── contacts  (audited CRUD, user-scoped, GCS mirror)                 │
│        ├── governance (/policy /gcp /audit /usage /retention/purge)          │
│        └── llm        (/tasks /plan/{task} /run)                             │
│                                 │                                            │
│                                 v                                            │
│              LLM Guardrails (injection · PII · output validation)            │
│                                 │                                            │
│                                 v                                            │
│              ModelRouter (cost): nano ▸ small ▸ medium ▸ large ▸ echo        │
│                        │                    │            │                   │
│                        v                    v            v                   │
│              Ollama local SLM ($0)   Gemini cloud    offline echo            │
│                                 │                                            │
│                                 v                                            │
│   SQLAlchemy ORM ─► SQLite (local) ◄─Alembic─► Cloud SQL Postgres            │
│     users · contacts · email_connections · linkedin_profiles · reddit_posts   │
│     whatsapp_messages · audit_logs (redacted) · model_usage (cost)           │
│                                                                              │
│   Governance: classification ▸ PII redaction ▸ audit ▸ retention ▸ GCP verify │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Data sources → outreach (original pipeline)

```
GCS bucket kalisoftai-datahub/ ──ADC──► /api/contacts/import/gcs ─► SEGREGATION ENGINE
   (all-sales-contacts-data: *.xlsx,*.csv,*.vcf,*.json)              infer_domain()
                                                                     infer_intent()
                                                                     classify_contact()
        ┌────────────┬───────────────┬───────────────┬──────────────┐
        v            v               v               v              v
  IMAP extractor  LinkedIn       Reddit posts    SMTP sender    GCS mirror
  (inbox,intent)  hiring alerts  hiring alerts   (outreach)     users/{id}/{cid}.json
        └────────────┴───────────────┴───────────────┴──────────────┘
                                     │
                        FastAPI /api  (auth, contacts, email, social, governance, llm)
                                     │
                    Static frontend + Cloud Scheduler ─► /cron/run ─► Redis sales:cron
                                     │
                    WhatsApp Cloud API · Reddit/LinkedIn · Gemma/Sarvam voice
```

### Request lifecycle (Google Sign-In)

```
 Browser                FastAPI                      Google                 Postgres
   │  click Sign-in        │                            │                       │
   ├───────────────────────┼───────────────────────────►│                       │
   │◄──── ID token (JWT) ───┼────────────────────────────┤                       │
   ├── POST /auth/google ─►│ verify_oauth2_token()      │                       │
   │                       ├───────────────────────────►│                       │
   │                       │◄──── claims (sub,email) ───┤                       │
   │                       ├── upsert user + audit ─────┼──────────────────────►│
   │◄── our JWT (1h) ──────┤                            │                       │
   ├── GET /contacts  ────►│ get_current_user()         │                       │
   │   Authorization:      ├── decode JWT + scope user ─┼──────────────────────►│
   │   Bearer <jwt>        │◄── rows ───────────────────┼───────────────────────┤
   │◄── JSON contacts ─────┤                            │                       │
```

---

## 2. Roadmap

### Phase 0 — Prototype (DONE)
- [x] FastAPI app, SQLite/Postgres, GCS import, manual contacts
- [x] Segregation: domain / intent / context
- [x] IMAP/SMTP connection registry + test + inbox + send
- [x] LinkedIn/Reddit hiring-alert stubs persisted to DB
- [x] Google Sign-In (ID token → app JWT), dev mode
- [x] pytest suite, Dockerfile, Cloud Run / Cloud Build files

### Phase 1 — Email intelligence (next)
- [ ] Gmail/Outlook OAuth (XOAUTH2) instead of app passwords
- [ ] IMAP thread parsing → auto-create contacts from signatures
- [ ] SLM summarisation → intent + context enrichment
- [ ] Bounce/unsubscribe handling, send throttling

### Phase 2 — Social signal (next scope)
- [ ] LinkedIn official API + hiring-post alerts → profile enrichment
- [ ] Reddit via PRAW → hiring threads → candidate/company extraction
- [x] Daily cron: keyword sets per region (Cloud Scheduler → `/cron/run`)
- [ ] Agent-Reach capability layer for web/YT/GitHub/Reddit/LinkedIn/X (`feature/agent-reach`)

### Phase 3 — Outreach & voice
- [x] WhatsApp message queue (Cloud API ready)
- [ ] WhatsApp delivery webhooks + templates
- [ ] SarvamAI TTS/STT voice notes (`feature/sarvam-voice`)
- [ ] Wechaty WhatsApp channel (`feature/wechaty-whatsapp`)

### Phase 4 — Platform (DONE)
- [x] HTTP guardrails: size cap, rate limits, CSP/HSTS, TrustedHost
- [x] Configuration security validator (production hardening)
- [x] Cloud SQL + Cloud Run + Secret Manager
- [x] Multi-user data scoping (single-tenant) + audit log
- [x] Alembic migrations for SQLite and Cloud SQL

### Phase 5 — Security, Governance & Cost-Optimised SLM (DONE)
- [x] LLM/agent guardrails: prompt injection, PII, output validation, budgets
- [x] Data governance: classification, PII masking, audit, retention, GCP verification
- [x] Model router: task tiers (nano/small/medium/large), local SLM + cloud fallback
- [x] `model_usage` cost ledger + `/api/governance/usage`
- [x] CI/CD: GitHub Actions + Cloud Build gates + Trivy
- [ ] BigQuery event spine (`analytics.*`)
- [ ] Multi-tenant `tenant_id` + PostgreSQL row-level security

### Phase 6 — Mobile (future scope)
- [ ] React Native / Flutter client against `/api/*`
- [ ] Google Sign-In native + secure token storage
- [ ] Push notifications for hot intent leads
- [ ] Offline voice notes → sync to GCS

---

## 3. Security, governance & SLM details

### HTTP security
`TrustedHostMiddleware`, request-size cap → 413, per-client auth/API rate limits → 429,
`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`,
`Permissions-Policy`, strict CSP, HSTS in production, docs disabled in production.

### LLM guardrails (`sales_fastapi/llm/guardrails.py`)
| Control | Example trigger |
|---|---|
| `override_instructions` | "ignore all previous instructions" |
| `reveal_system_prompt` | "print/reveal your system prompt" |
| `role_hijack` | "you are now…", "DAN mode" |
| `secret_exfiltration` | "print the api key/token/password" |
| `tool_abuse` | "run shell/python/os.system" |
| `delimiter_escape` | `<\|im_start\|>`, `[INST]` |

### Data governance (`sales_fastapi/governance/*`)
- Classification: public / internal / confidential / restricted.
- PII: email, phone, Aadhaar, PAN, GSTIN, credit card (Luhn), IPv4 → redact/mask.
- Audit: append-only `audit_logs`, redacted details, recorded on auth/contact/LLM actions.
- Retention: per-dataset windows, dry-run purge.
- GCP verify: status-only checks (never secret values).

### Cost-optimised SLM routing (`sales_fastapi/llm/*`)
| Task | Tier | Primary | Fallback | External | JSON |
|---|---|---|---|---|---|
| `dedupe_match` | nano | local 0.5B | local 3B | no | yes |
| `classify_intent` | small | local 3B | local 8B | no | yes |
| `extract_entities` | small | local 3B | cloud flash | yes | yes |
| `summarize_profile` | small | local 3B | cloud flash | yes | no |
| `translate_script` | small | local 3B | cloud flash | yes | no |
| `draft_outreach_email` | medium | local 8B | cloud flash | yes | no |
| `generate_pitch` | large | cloud pro | cloud flash | yes | no |
| `research_synthesis` | large | cloud pro | cloud flash | yes | no |

Cost estimate (micro-USD / 1K tokens): local & echo `0/0`, flash-lite `50/200`,
flash `100/400`, pro `1250/5000`. Every chain ends in the offline `echo` provider so
the pipeline never hard-fails. Configured via `LLM_LOCAL_*`, `LLM_CLOUD_*`,
`LLM_MONTHLY_TOKEN_BUDGET`, `LLM_ENFORCE_BUDGET`.

---

## 4. Data model

| Table | Purpose | Key columns |
|---|---|---|
| `users` | identities | `google_sub`, `email`, `domain`, `is_active` |
| `contacts` | sales contacts (user-scoped) | unique `(user_id, email)`, `source`, `gcs_path` |
| `email_connections` | IMAP/SMTP per user | `secret_encrypted` (Fernet), `is_connected` |
| `linkedin_profiles` / `reddit_posts` | scraped hiring signal | `profile_url` / `post_url` |
| `whatsapp_messages` | outbound queue | `phone_number`, `status` |
| `audit_logs` | append-only audit | `actor_user_id`, `action`, `status`, `detail` |
| `model_usage` | LLM cost ledger | `task`, `tier`, `provider`, `cost_micros` |

---

## 5. How to run (local)

```powershell
pip install -r requirements-sales.txt
Copy-Item .env.example .env      # then edit
python run.py --seed             # http://localhost:8000
python -m pytest -q              # 57 tests
python -m ruff check sales_fastapi tests migrations
python -m bandit -r sales_fastapi -x sales_fastapi/static -ll
```

- **Doctor**: `GET /api/health` → DB / Redis / GCS / Google Sign-In status.
- **Docs**: `GET /docs` (Swagger UI; disabled in production).
- Dev sign-in: `AUTH_DEV_MODE=true`, send `dev:you@kalisoftai.com` as the ID token.
- DB resolution: `DATABASE_URL` > `CLOUD_SQL_CONNECTION_NAME` > `POSTGRES_HOST` > SQLite.
- Migrations: `alembic upgrade head && alembic check`.
- Local model: run Ollama (`ollama pull qwen2.5:3b`) for $0 local inference.

### Deploy (Cloud Run)

```powershell
./deploy_sales.ps1 -ProjectId <proj> -CloudSqlInstance <proj>:asia-south1:<db>
# or
bash deploy_sales.sh
```

`cloudbuild.fastapi.yaml` (Artifact Registry + Secret Manager) is the deploy config;
`cloudbuild.checks.yaml` is the release gate. CI/CD is automated via
`.github/workflows/ci.yml` and `.github/workflows/cd.yml`.

---

## 6. API quick reference

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/config` | public config (no secrets) |
| GET | `/api/health` | DB / Redis / GCS / sign-in status |
| GET | `/api/integrations` | integration availability |
| POST | `/api/cron/run` | enqueue scheduled tasks to Redis |
| POST | `/api/auth/google` | Google ID token → JWT (audited) |
| GET | `/api/auth/me` | current user |
| GET/POST | `/api/contacts` | list / create (audited) |
| GET | `/api/contacts/stats` | totals by domain/intent/source |
| GET/PATCH/DELETE | `/api/contacts/{id}` | read / update / delete (audited) |
| POST | `/api/contacts/import/gcs` | import from `all-sales-contacts-data` |
| GET/POST | `/api/email/connections` | list / register IMAP+SMTP |
| POST | `/api/email/connections/{id}/test` | test IMAP + SMTP |
| GET | `/api/email/connections/{id}/inbox` | fetch + intent-tag mail |
| POST | `/api/email/send` | send via SMTP |
| POST/GET | `/api/social/linkedin/*`, `/api/social/reddit/*`, `/api/social/whatsapp/*` | social + WhatsApp queue |
| POST | `/api/social/youtube/search` | YouTube signal scan (Google-secured, ADC) |
| POST | `/api/scheduler/run` | Enqueue standard cron tasks (user-scoped) |
| GET | `/api/scheduler/status` | Scheduler health + queued tasks |
| GET | `/api/scheduler/tasks` | Registered recurring task definitions + cron |
| POST | `/api/scheduler/clear` | Clear this user's queued tasks |
| GET | `/api/kpi/overview` | Headline business KPIs |
| GET | `/api/kpi/pipeline` | Contact funnel: intent/source mix, 7-day growth |
| GET | `/api/kpi/outreach` | Campaign funnel + delivery rate |
| GET | `/api/kpi/costs` | LLM usage & cost summary |
| GET | `/api/governance/policy` | classification + retention + flags |
| GET | `/api/governance/gcp` | status-only GCP verification |
| GET | `/api/governance/audit` | current user's audit events |
| POST | `/api/governance/retention/purge` | retention purge |
| GET | `/api/governance/usage` | LLM calls/tokens/cost |
| GET | `/api/llm/tasks` | task registry + tiers |
| GET | `/api/llm/plan/{task}` | routing chain |
| POST | `/api/llm/run` | guarded, budgeted, audited execution |

### Example seed contact (Ahmednagar)

```
Company : Mahindra Accelo Ltd. (Mahindra & Mahindra group) – Supa, Ahmednagar
Email   : info@mahindraaccelo.com
Phone   : 22 2493 5185 / 5186
SCM     : Smaranika Mohapatra – Assistant Manager (Procurement & SCM)
LinkedIn: Tushar Ithape, Vishal Karad, Ganesh Pagire
Address : F-221, Gat No. 167 K/2, Supa MIDC, Ahmednagar, MH 414301
Intent  : procurement   Domain: mahindraaccelo.com
```

---

## 7. Testing & CI/CD

**Tests — 57, coverage 74% (gate 70%)**

| File | Focus |
|---|---|
| `test_auth.py` | dev login, `/me`, missing/bad token |
| `test_system.py` | config, health, index, integrations |
| `test_contacts.py` | CRUD, auto-segregation, scoping, GCS namespace |
| `test_services.py` | domain/intent classification |
| `test_social.py` | LinkedIn, Reddit, WhatsApp, cron |
| `test_security_guardrails.py` | headers, size cap, prod config, untrusted host |
| `test_pii.py` | detection, redaction, Luhn, structured, masking |
| `test_governance.py` | classification, audit redaction, retention, GCP shape |
| `test_llm_guardrails.py` | injection, PII, size, JSON validation |
| `test_llm_router.py` | routing, fallback, injection reject, budget, cost |

```text
PR      → ci.yml       ruff · gitleaks · pytest+cov(70%) · alembic parity · pip-audit · docker
Merge   → cd.yml       WIF → Cloud Build → Cloud Run + /api/health smoke test
Release → cloudbuild.checks.yaml   lint · SAST · tests · migrations · Trivy HIGH/CRITICAL
```

---

## 8. NotebookLM — test scenarios

Upload the repo docs + this `ROADMAP.md`, then run these prompts/scenarios:

1. **Onboarding** — "Explain the contact lifecycle from GCS import to WhatsApp queue."
   Expected: names segregation, dedupe, GCS mirror.
2. **Security** — "List the guardrails on an inbound request and on an LLM prompt."
   Expected: HTTP guardrails table + LLM guardrail rules.
3. **Governance** — "How is PII protected in logs and prompts, and where is it audited?"
   Expected: PII redaction, `audit_logs`, retention, classification.
4. **Cost** — "How does the router minimise model spend?" Expected: tier table, local
   SLM first, cloud fallback, token budget, `model_usage` ledger.
5. **Multi-user** — "Show that two users cannot see each other's contacts." Expected:
   user-scoped queries (`test_contacts_are_user_scoped`).
6. **Failure modes** — "What happens if GCS/Redis/Ollama are unavailable?" Expected:
   graceful degradation, `available=false`, `echo` fallback, HTTP 503 on hard GCS import.
7. **Migration** — "Compare local SQLite vs Cloud SQL and the migration checks."
   Expected: resolution order, `alembic upgrade/check/downgrade`.

---

## 9. Changelog

| Date | Change |
|---|---|
| 2026-09-12 | FastAPI prototype: contacts + segregation, IMAP/SMTP, LinkedIn/Reddit, WhatsApp queue |
| 2026-09-12 | Google Sign-In (ID token → JWT), dev mode, user-scoped data |
| 2026-09-12 | Cloud Run: Dockerfile.sales, cloudbuild.sales.yaml, deploy_sales.sh/.ps1 |
| 2026-09-13 | HTTP guardrails, config security validator, TrustedHost/CSP |
| 2026-09-13 | LLM guardrails, data governance (PII/audit/retention/GCP verify) |
| 2026-09-13 | Cost-optimised SLM router + `model_usage` cost ledger |
| 2026-09-13 | Alembic migrations (SQLite/Cloud SQL), 57 tests, CI/CD gates |
| 2026-09-13 | Docs: `docs/IMPLEMENTATION_ROADMAP.md`, README + ROADMAP detail |
| 2026-09-14 | Wechaty gateway (mock + live) + FastAPI WhatsApp/WeChat integration |
| 2026-09-14 | Templates, bulk campaigns (human-in-the-loop), Gemma routing |
| 2026-09-14 | Docker image + GitHub Actions CI/CD; Artifact Registry with cleanup policy |
| 2026-09-14 | **Production Cloud Run deploy** + SQLite→Cloud SQL migration (reconcile PASS) |
| 2026-09-14 | Sign-in page with plans (Free 2 AI users → Scale) + WhatsApp cost transparency (Meta India rate card) |
| 2026-09-14 | Auth: Google placeholder detected; restricted production login for `ai.solutions@kalisoftai.in` (403 for others) |
| 2026-09-25 | ADC update (Google-secured APIs), YouTube Data API stub, customized scheduler + business-KPI endpoints, UAT/Prod env strategy |
| 2026-09-25 | Feedback + Gmail mail notification, security guardrails trust panel, guided walkthrough tour + "How it works" strip; importer: blank-first-row xlsx headers + turnover/sector/exporter/requirements mapping (verified against real `kalisoftai-datahub` exports) |
| 2026-09-25 | Docs: Cloud Functions multi-bucket scheduler, prompts-as-config (`kalisoftai-datahub/prompts`), intent/graph JSON with confidence + human review, connectors/MCP pricing decorators, Reddit format spec |
| 2026-09-25 | GA4 website KPI snapshot, KalisoftAI brand asset, and account catalog → quote → invoice future-scope design |
| _next_ | Gemma 4 personalisation, region co-location, Sarvam voice, Wechaty live, BigQuery, multi-tenant RLS, knowledge catalog graph DB, Account template + quotes/catalog/invoice (matrices.xlsx) |

---

## 10. Future scope — knowledge catalog with graph database (Gemma 4)

> Documented backlog; **not yet implemented**. Tracked behind feature flags.

### Vision
A **knowledge catalog** that turns today's flat contact rows into a connected
**entity graph**: `Contact ⇄ Company ⇄ Signal ⇄ Campaign ⇄ Outcome`. Sales users
query relationships ("which procurement contacts at M&M-group companies engaged
with our last 3 campaigns?") instead of scanning lists.

### Candidate architecture

```text
  Postgres (system of record)
        │  CDC / nightly ETL
        v
  ┌────────────────────────────┐        ┌─────────────────────────┐
  │ Graph store (one of):       │        │ Gemma 4 (gemma-4-27b-it)│
  │  • Neo4j AuraDB (managed)   │◄──────►│  entity extraction &     │
  │  • Neo4j on GCE (self-host) │ Cypher │  relationship inference  │
  │  • Postgres + Apache AGE    │        │  (cost-routed via        │
  │  • BigQuery + Spanner Graph │        │   ModelRouter, large tier)│
  └────────────────────────────┘        └─────────────────────────┘
        │                                        │
        v                                        v
  /api/graph/query (natural language → Cypher, guardrailed)
```

### Decision criteria (choose ONE, keep it stupidly simple)
1. **Postgres + Apache AGE** — zero new infra, lowest cost; start here.
2. **Neo4j AuraDB** — best query ergonomics; add when relationship queries
   outgrow AGE.
3. **Spanner Graph** — only if multi-region global scale is required.

### Phased plan
- [ ] **G1** — Schema: `entities`, `relationships` tables (AGE-compatible)
- [ ] **G2** — Gemma 4 entity/relationship extraction job (nightly, cost-routed)
- [ ] **G3** — `/api/graph/query` natural-language → Cypher with LLM guardrails
- [ ] **G4** — Frontend graph explorer (React Flow / Cytoscape.js)
- [ ] **G5** — KPI layer on graph: influence score, relationship depth, churn risk

---

## 11. UAT / Production environment strategy

| Concern | UAT | Production |
|---|---|---|
| `ENV` | `staging` | `production` |
| API docs (`/docs`) | enabled | disabled |
| `AUTH_DEV_MODE` | `true` (restricted via `AUTH_DEV_ALLOWED_EMAILS`) | `false` |
| Database | Cloud SQL (UAT instance) | Cloud SQL (prod instance) |
| Redis | Memorystore (basic) | Memorystore (standard HA) |
| Scheduler backend | in-memory acceptable | Redis queue + Cloud Scheduler |
| Rate limits | relaxed | enforced (`RATE_LIMIT_ENABLED=true`) |
| Sign-in | Google OAuth + dev fallback | Google OAuth only (`GOOGLE_ALLOWED_DOMAINS=kalisoftai.com`) |
| Deploy trigger | PR merge → `staging` branch | tag / release → `main` |
| Smoke test | `/api/health` after deploy | `/api/health` + SLO alert |

**UI environment indicator:** the frontend reads `GET /api/health.env` and shows a
colored badge — **green** = production, **amber** = staging/UAT, **blue** = local dev —
so testers always know which environment they are using.

---

## 12. Cloud Functions — customized multi-bucket scheduler (design)

> **Design only — not yet implemented.** Goal: let each user schedule harvests from
> *any* GCS bucket (not just `all-sales-contacts-data/`), classify intent on the way
> in, pick the model per job, and land a data dump in the folder they choose —
> synced back to the UI. Built to be **cost-effective by default**.

### System design

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                    CUSTOMIZED SCHEDULER — CLOUD FUNCTIONS                     │
│                                                                              │
│  UI: "New harvest job"                                                       │
│   ├─ source bucket(s)   [kalisoftai-datahub/Clients_data/ ▾] [+ add bucket]  │
│   ├─ intent filter      [procurement ▾]  (hiring|procurement|sales|any)      │
│   ├─ model              (•) Gemini Flash — fast, cheap                       │
│   │                     ( ) Gemma 4 27B — deep, per-call cost                │
│   │                     [x] echo fallback if budget exceeded                 │
│   ├─ dump to folder     [users/{uid}/dumps/procurement-sep/]                 │
│   └─ schedule           [0 6 * * *]  ← user-editable cron                    │
│                                                                              │
│        │ saves job config to Postgres (harvest_jobs)                         │
│        v                                                                     │
│  ┌───────────────────┐   cron fires    ┌──────────────────────────────────┐  │
│  │ Cloud Scheduler    │───────────────► │ Cloud Function (2nd gen)          │  │
│  │  job per user cron │  OIDC-authed    │  kalisoft-bucket-harvester        │  │
│  └───────────────────┘                 │                                  │  │
│                                        │  1. load job config               │  │
│                                        │  2. list source bucket objects    │  │
│                                        │  3. pull prompt pack from ────────┼──┼──► gs://kalisoftai-datahub/prompts/
│                                        │  4. classify intent per record    │  │     intent-classify.json
│                                        │     (model selected in UI)        │  │     entity-extract.json
│                                        │  5. keep only matching intent     │  │     graph-small.json
│                                        │  6. write dump (JSONL + manifest) │  │     graph-large.json
│                                        └──────────────┬───────────────────┘  │
│                                                       │                       │
│                           gs://<user-chosen folder>/  │  dump.jsonl + manifest.json
│                                                       v                       │
│                                        ┌──────────────────────────────────┐  │
│                                        │ FastAPI  /api/connectors/sync     │  │
│                                        │  • validates manifest             │  │
│                                        │  • dedupe-inserts contacts        │  │
│                                        │  • writes KPI snapshot            │  │
│                                        └──────────────┬───────────────────┘  │
│                                                       │ push / poll           │
│                                                       v                       │
│                                        UI refresh — rich decorators:          │
│                                        toast "24 new procurement contacts",   │
│                                        KPI cards tick up, badge on Contacts   │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Why Cloud Functions (not another Cloud Run service)
- **Pay-per-invocation** — a 6 AM harvest that runs 40 s/day costs ~$0 on the free
  tier; no idle container. Cloud Run min-instances=0 already helps, but Functions
  are the cheapest fit for short bursty jobs.
- **Eventarc native** — the same function can later trigger on
  `google.storage.object.finalize` (drop a file → harvest immediately) with zero
  code forks.
- **Isolated retries/timeout** — per-job 9-min cap, independent of the API's SLO.

### Cost guardrails
| Control | Default | Purpose |
|---|---|---|
| Model per job | Gemini Flash | Flash for classify; Gemma 4 only when user opts in |
| Max objects/job | 500 | caps runaway buckets |
| Token budget check | `LLM_MONTHLY_TOKEN_BUDGET` | job degrades to `echo` (skip AI) when exhausted |
| Dump format | JSONL + manifest | stream-parse, no big-memory reads |
| Schedule jitter | +0–10 min | avoids thundering-herd at :00 |

---

## 13. Prompts-as-config — `gs://kalisoftai-datahub/prompts/`

> Prompts live in GCS, **versioned as JSON**, not hard-coded. The app fetches the
> prompt pack at job start (cached 5 min), so prompt tweaks ship without a deploy.
> Every prompt declares its model hint, output schema and confidence policy.

```text
kalisoftai-datahub/prompts/
├── intent-classify.json      # small graph: record → intent + confidence
├── entity-extract.json       # contact/company/person extraction
├── graph-small.json          # per-record mini-graph (nodes+edges, inline)
├── graph-large.json          # nightly cross-record graph job (Gemma 4)
├── outreach-personalise.json # Gemma 4 campaign personalisation
└── manifest.json             # {name: {version, sha256, updated_at}}
```

### Prompt pack format (example: `intent-classify.json`)

```json
{
  "id": "intent-classify",
  "version": 3,
  "model_hint": "gemini-2.0-flash",
  "fallback_model": "gemma-4-27b-it",
  "system": "You classify B2B sales records into exactly one intent.",
  "output_schema": {
    "type": "object",
    "properties": {
      "intent": {"enum": ["hiring", "procurement", "sales", "partnership", "support", "general"]},
      "confidence": {"type": "number", "minimum": 0, "maximum": 1},
      "rationale": {"type": "string", "maxLength": 280}
    },
    "required": ["intent", "confidence"]
  },
  "confidence_threshold": 0.65,
  "human_review_below": 0.65
}
```

### Intent → context JSON contract (what the UI renders)

Every classified record carries a **small graph** (per-record) inline:

```json
{
  "record_id": "gcs://.../Contacts ( Pune, Chennai nd others ).xlsx#row3",
  "intent": "procurement",
  "confidence": 0.87,
  "graph": {
    "nodes": [
      {"id": "c1", "type": "company",  "label": "Animets Engg. Pvt. Ltd."},
      {"id": "p1", "type": "person",   "label": "Jaydeep Muley", "role": "CEO"},
      {"id": "i1", "type": "intent",   "label": "procurement"},
      {"id": "s1", "type": "sector",   "label": "Machinery / Machine Tools"}
    ],
    "edges": [
      {"from": "p1", "to": "c1", "rel": "works_at",    "confidence": 0.98},
      {"from": "c1", "to": "i1", "rel": "has_intent",  "confidence": 0.87},
      {"from": "c1", "to": "s1", "rel": "in_sector",   "confidence": 0.95}
    ]
  },
  "human_review": false
}
```

| Graph size | Model | When | Output |
|---|---|---|---|
| **small** (per record) | Gemini Flash | on ingest / upload | intent + 3–6 node mini-graph + confidence |
| **large** (cross-record) | Gemma 4 27B | nightly batch | company⇄person⇄signal⇄campaign edges merged into catalog |

**Confidence → human review:** any node/edge below the prompt pack's
`confidence_threshold` is flagged `human_review: true`; the UI renders those
amber in the graph explorer and queues them on the review screen. Approving or
correcting an edge writes back to the catalog (audit-logged) and feeds the
weekly prompt-eval — a self-improving loop.

---

## 14. Connectors, MCP tools & pricing decorators (design)

> **Design only.** One connector interface behind the API; each connector can be
> exposed as an **MCP tool** (for agentic flows) and renders in the UI with a
> **rich decorator** (status pill, price hint, last-run).

```text
┌─────────────────────────────────────────────────────────────────────┐
│ CONNECTOR LAYER (FastAPI)            every connector exposes:        │
│                                       • run(config) → records        │
│  ┌─────────────┐ ┌─────────────┐     • price_estimate(config) → ₹    │
│  │ GCS buckets │ │ Gmail/IMAP  │     • mcp_tool schema (name/args)   │
│  └─────────────┘ └─────────────┘     • ui decorator (icon/pill/hint) │
│  ┌─────────────┐ ┌─────────────┐                                     │
│  │ Reddit      │ │ YouTube     │     UI "Connectors" gallery:         │
│  │ (PRAW+fmt)  │ │ (Data v3)   │     ┌─────────────────────────────┐  │
│  └─────────────┘ └─────────────┘     │ [GCS] connected · ₹0.00/run │  │
│  ┌─────────────┐ ┌─────────────┐     │ [Reddit] needs key · ₹0.04/ │  │
│  │ LinkedIn    │ │ GA4         │     │   1k posts · last run 6h ago│  │
│  └─────────────┘ └─────────────┘     │ [YouTube] API key · ₹0.05/  │  │
│                                      │   100 searches              │  │
│  MCP bridge: /mcp/tools lists all ──►└─────────────────────────────┘  │
│  connectors as tools for agents      (price shown BEFORE you run)     │
└─────────────────────────────────────────────────────────────────────┘
```

**Price transparency rule:** every connector and model choice shows its estimated
unit price in the UI *before* the user clicks run — same pattern as the WhatsApp
cost calculator already on the sign-in page.

### Model selection = cost control (per user requirement)

| User picks | Model | Best for | Approx cost* |
|---|---|---|---|
| "Fast & cheap" (default) | **Gemini 2.0 Flash** | intent classify, small graphs | ~₹0.03 / 1k records |
| "Deep analysis" | **Gemma 4 27B** | nightly large graph, personalisation | Vertex pricing, budget-capped |
| "Offline / $0" | **echo** provider | tests, budget-exhausted fallback | ₹0 |

\*Indicative only — real figures come from the `model_usage` ledger
(`/api/kpi/costs`); the ledger is the source of truth for invoice-grade numbers.

---

## 15. Reddit formatted posts + checkers (future scope)

> **Future scope.** Structured Reddit intake so posts arrive pre-formatted and
> pre-checked instead of raw stubs.

```text
PRAW stream (subreddits: jobs, recruiting, forhire, procurement)
        │
        v
┌─────────────────────────────┐
│ format checker               │  must match hiring-post pattern:
│  • title  [Hiring]/[ForHire] │  [Hiring][Location][Role] ...
│  • flair / salary / remote   │  else → quarantine queue
└──────────────┬──────────────┘
               v
┌─────────────────────────────┐
│ content checkers             │
│  • PII guardrail (drop)      │
│  • spam score (Flash, small) │
│  • intent + confidence (JSON)│
└──────────────┬──────────────┘
               v
     reddit_posts (formatted)  →  UI card: title · role · budget · confidence pill
```

- [ ] **R1** — PRAW credentials + subreddit config per workspace
- [ ] **R2** — format checker (title pattern, flair, salary/remote extraction)
- [ ] **R3** — spam/PII checkers wired to existing guardrails
- [ ] **R4** — intent JSON (small graph) per post, human-review queue < 0.65
- [ ] **R5** — UI card renderer for formatted posts

---

## 16. Dynamic nodes & edges (future scope, extends §10)

> The graph starts **static** (nightly large-graph job) and becomes **dynamic**:
> the UI lets users add a node ("this person moved to a new company") or draw an
> edge ("these two companies are partners") directly in the explorer. Each manual
> edit is stored as a `confidence: 1.0, source: "human"` edge — human truth always
> outranks model inference, and every edit is audit-logged.

```text
   user drags edge in UI ──► POST /api/graph/edge {from,to,rel}
                                  │
                                  v
                    stored confidence=1.0 source=human
                                  │
              nightly Gemma 4 large-graph job merges:
              model edges (confidence<1) yield to human edges on conflict
```

- [ ] **D1** — `POST /api/graph/node|edge` (human-authored, confidence 1.0)
- [ ] **D2** — conflict rule: human edge > model edge; model re-derives around it
- [ ] **D3** — explorer canvas (React Flow) with drag-to-connect
- [ ] **D4** — prompt-eval loop: accepted/rejected model edges tune the prompt pack

---

## 17. Account catalog, quotes & invoices (future scope)

> **Design only — not yet implemented.** The approved service catalog, account model,
> quote workflow, and invoice workflow are specified in
> [`docs/ACCOUNT_TEMPLATES.md`](docs/ACCOUNT_TEMPLATES.md). The initial catalog is
> derived from the local `data/All-project-matrices.xlsx` workbook; the workbook stays
> ignored by Git until an approved import path is ready.

### Workflow

```text
Approved workbook export
        │ validate, normalize, version
        v
Service catalog ──► account requirements ──► Gemma 4 recommendation
                                             │ human selects plan
                                             v
                                  quote draft + server totals
                                             │ human approval
                                             v
                                  invoice draft + tax checks
                                             │ human approval
                                             v
                                    immutable invoice delivery
```

### Routing boundary

Gemma 4 is planned for catalog extraction, account matching, quote summaries, and
invoice explanations. The application remains authoritative for price ranges, tax,
discounts, totals, invoice numbers, permissions, and status transitions. All generated
commercial documents require human approval.

### Phased delivery
- [ ] **A1** — Confirm service IDs, tax fields, numbering, and approval roles.
- [ ] **A2** — Add reviewed workbook import and catalog version history.
- [ ] **A3** — Add user-scoped account, quote, and invoice data models.
- [ ] **A4** — Implement deterministic totals, audit events, and idempotency.
- [ ] **A5** — Add Gemma 4 tasks behind a feature flag.
- [ ] **A6** — Add review/approval UI and PDF delivery.
- [ ] **A7** — Complete tax-compliance review before production enablement.
