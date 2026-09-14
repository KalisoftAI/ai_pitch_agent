# Kalisoft AI Sales Pipeline — Roadmap & Implementation

A FastAPI sales pipeline that ingests contacts (GCS + manual), segregates them by
**domain / intent / context**, extracts email & LinkedIn signal via **IMAP + SMTP**,
prepares **WhatsApp → Reddit/LinkedIn** outreach, and is secured with **Google Sign-In**,
**Guardrails**, **Data Governance** and a **cost-optimised small-language-model router**.
Runs on **Cloud Run**, backed by **Postgres** (local SQLite → Cloud SQL) and **Redis**.

> Status: security/governance/SLM/outreach phases implemented and **live in production** —
> 71 backend tests green, coverage 74%, `ruff` clean, `bandit -ll` clean, `alembic check` no drift.
> Full exhaustive reference: [`docs/IMPLEMENTATION_ROADMAP.md`](docs/IMPLEMENTATION_ROADMAP.md).

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
| _next_ | Gemma personalisation, region co-location, Sarvam voice, Wechaty live, BigQuery, multi-tenant RLS |
