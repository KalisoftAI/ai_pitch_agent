# Implementation Roadmap — Security, Governance, SLM Routing & CI/CD

Status: **Phases 1–6 implemented** on branch `sales-gcp-migration`.
- `123402c` — LLM guardrails, data governance, cost-optimised SLM router, Alembic migrations.
- `45eb45c` — CI/CD gates, lint config, migration checks, this roadmap.
- Current verification: **57 tests passing**, coverage **74%**, `ruff` clean, `bandit -ll` clean,
  `alembic check` reports no drift.

Voice (Sarvam), WhatsApp (Wechaty) and Agent-Reach remain documented backlog branches.

---

## 1. System flow (ASCII)

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                     KALISOFT SALES — SECURE REQUEST PATH                      │
│                                                                              │
│  Browser / React (frontend/) ─┐                                              │
│                               v                                              │
│                    ┌──────────────────────────┐                             │
│                    │  RequestGuardrails        │  413 size · 429 rate       │
│                    │  (guardrails.py)          │  CSP · HSTS · nosniff      │
│                    └────────────┬─────────────┘                             │
│                                 v                                            │
│                    ┌──────────────────────────┐                             │
│                    │  TrustedHostMiddleware    │  host allow-list           │
│                    └────────────┬─────────────┘                             │
│                                 v                                            │
│   Auth (Google ID token) ─► JWT ─► get_current_user                          │
│                                 │                                            │
│        ┌────────────────────────┼─────────────────────────┐                 │
│        v                        v                          v                 │
│  contacts router          governance router           llm router             │
│  (audited CRUD)           /policy /gcp /audit         /tasks /plan /run      │
│        │                  /usage /retention/purge         │                  │
│        │                        │                         v                  │
│        │                        │              ┌───────────────────────┐    │
│        │                        │              │  LLM Guardrails        │    │
│        │                        │              │  injection · PII ·     │    │
│        │                        │              │  output validation     │    │
│        │                        │              └───────────┬───────────┘    │
│        │                        │                          v                │
│        │                        │              ┌───────────────────────┐    │
│        │                        │              │  ModelRouter (cost)    │    │
│        │                        │              │  nano ▸ small ▸ medium │    │
│        │                        │              │  ▸ large ▸ echo        │    │
│        │                        │              └──────┬─────────┬──────┘    │
│        │                        │                     v         v           │
│        │                        │             Ollama local   Gemini cloud    │
│        │                        │             (SLM, $0)      (fallback)      │
│        v                        v                     │                     │
│  ┌───────────────────────────────────────────┐        │                     │
│  │ SQLAlchemy ORM                             │        │                     │
│  │  SQLite (local)  ◄──── Alembic ───►  Cloud SQL Postgres                  │
│  │  users · contacts · email · ...            │        │                     │
│  │  audit_logs (redacted) · model_usage (cost)│◄───────┘                     │
│  └───────────────────────────────────────────┘                              │
│                                                                              │
│  Governance: classification ▸ PII redaction ▸ audit ▸ retention ▸ GCP verify │
│  Secrets: Secret Manager (no values in code/logs). BigQuery = later phase.   │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Repository layout (relevant files)

```text
alembic.ini                       Alembic config (URL resolved at runtime)
pyproject.toml                    ruff + coverage config
requirements-sales.txt            FastAPI runtime + test/quality deps
cloudbuild.fastapi.yaml           Cloud Run deploy (Secret Manager, Artifact Registry)
cloudbuild.checks.yaml            Pre-merge gate (lint, SAST, tests, Trivy)
.github/workflows/ci.yml          GitHub Actions CI
.github/workflows/cd.yml          GitHub Actions CD (Workload Identity Federation)
scripts/verify_migrations.ps1     Local migration check (Windows)
scripts/verify_migrations.sh      Local migration check (bash)
docs/IMPLEMENTATION_ROADMAP.md    This document
migrations/
  env.py                          Loads settings + Base.metadata
  script.py.mako                  Revision template
  versions/0001_initial.py        Baseline schema (all 8 tables)
sales_fastapi/
  main.py                         App, middleware, router registration
  config.py                       Settings + security validator
  database.py                     Engine/session; SQLite → Cloud SQL resolution
  guardrails.py                   HTTP middleware (size, rate, headers)
  security.py                     Google ID token → JWT, Fernet secret encryption
  models.py                       ORM models (incl. AuditLog, ModelUsage)
  schemas.py                      Pydantic request/response models
  services.py                     GCS, IMAP, SMTP, LinkedIn, Reddit adapters
  governance/
    pii.py                        PII detection/masking/redaction
    classification.py             Data classification policy
    audit.py                      Append-only audit writer/reader
    retention.py                  Retention policy + purge
    gcp_verify.py                 Status-only GCP environment checks
  llm/
    tasks.py                      Task registry + tiers
    guardrails.py                 Prompt-injection, PII, output validation
    providers.py                  Ollama, Gemini, Echo adapters
    router.py                     Cost-optimised routing, budgets, ledger
    __init__.py                   Public exports
  routers/
    system.py  auth.py  contacts.py  email.py  social.py
    governance.py                 governance_router + llm_router
tests/                            pytest suite (57 tests)
```

---

## 3. Configuration reference

All settings are read by `sales_fastapi/config.py` (env vars override `.env`).

### Core / environment
| Variable | Default | Purpose |
|---|---|---|
| `ENV` | `development` | `production` enables strict validation + hides docs |
| `PROJECT_NAME` / `VERSION` | app metadata | shown in `/api/config` |
| `SECRET_KEY` | — | JWT signing + Fernet key; **≥32 chars, non-default** |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | 5–1440 |

### Database (resolution order)
| Variable | Purpose |
|---|---|
| `DATABASE_URL` | explicit URL (wins) |
| `CLOUD_SQL_CONNECTION_NAME` | Cloud SQL unix socket (`project:region:instance`) |
| `POSTGRES_HOST` / `POSTGRES_PORT` / `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | TCP Postgres |
| `SQLITE_PATH` | fallback local SQLite (`sales_pipeline.db`) |

### Google / GCS / secrets
| Variable | Purpose |
|---|---|
| `GOOGLE_CLOUD_PROJECT` | project id (required in production) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google Sign-In |
| `GOOGLE_ALLOWED_DOMAINS` | email domain allow-list |
| `GCS_BUCKET_CONTACTS` / `GCS_PATH_CONTACTS` | contact mirror + import namespace |
| `GEMINI_API_KEY` | cloud model key |
| `SMTP_*` / `IMAP_*` | mail connection defaults |
| `LINKEDIN_*` / `REDDIT_*` | social integrations |
| `WHATSAPP_API_KEY` / `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp Cloud API |
| `GEMMA_MODEL` | legacy model name |

### HTTP guardrails
| Variable | Default | Purpose |
|---|---|---|
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,testserver` | TrustedHost allow-list |
| `MAX_REQUEST_BYTES` | `1048576` | body cap → HTTP 413 |
| `RATE_LIMIT_ENABLED` | `false` | in-process limiter (Cloud Armor is primary) |
| `AUTH_RATE_LIMIT` | `10` / 300s | sign-in attempts per client |
| `API_RATE_LIMIT` | `120` / 60s | API requests per client |
| `CORS_ORIGINS` | localhost | explicit origins required in production |

### Data governance
| Variable | Default | Purpose |
|---|---|---|
| `GOVERNANCE_ENABLED` | `true` | master governance switch |
| `PII_REDACTION_ENABLED` | `true` | redact PII in logs/prompts; **must be true in prod** |
| `AUDIT_LOG_ENABLED` | `true` | write audit events; **must be true in prod** |
| `RETENTION_DAYS_AUDIT` | `365` | audit retention window |
| `RETENTION_DAYS_CONTACTS` | `730` | contact retention window |

### Cost-optimised SLM routing
| Variable | Default | Purpose |
|---|---|---|
| `LLM_ENABLED` | `false` | gate for model execution |
| `LLM_LOCAL_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `LLM_LOCAL_NANO_MODEL` | `qwen2.5:0.5b` | nano tier |
| `LLM_LOCAL_MODEL` | `qwen2.5:3b` | small tier |
| `LLM_LOCAL_MEDIUM_MODEL` | `llama3.1:8b` | medium tier |
| `LLM_CLOUD_FLASH_MODEL` | `gemini-2.0-flash` | cheap cloud fallback |
| `LLM_CLOUD_MODEL` | `gemini-2.5-pro` | large tier |
| `LLM_MONTHLY_TOKEN_BUDGET` | `5000000` | hard budget (tokens) |
| `LLM_ENFORCE_BUDGET` | `true` | block calls over budget |
| `LLM_TIMEOUT_SECONDS` | `60` | provider HTTP timeout |
| `LLM_MAX_INPUT_CHARS` | `20000` | prompt size cap |
| `LLM_MAX_OUTPUT_CHARS` | `40000` | output size cap |

Production validator enforces: non-default `SECRET_KEY`, `AUTH_DEV_MODE=false`,
non-empty `GOOGLE_CLIENT_ID`/`GOOGLE_ALLOWED_DOMAINS`/`GOOGLE_CLOUD_PROJECT`,
no wildcard CORS/hosts, and PII redaction + audit enabled.

---

## 4. Security controls

### HTTP layer (`sales_fastapi/guardrails.py`, `main.py`)
- `TrustedHostMiddleware` rejects unknown `Host` (HTTP 400).
- Request-size cap → 413; per-client auth/API rate limits → 429.
- Response headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: same-origin`, `Permissions-Policy`, strict `Content-Security-Policy`.
- `Strict-Transport-Security` added when `ENV=production`.
- Interactive docs/OpenAPI disabled in production.
- CORS restricted to explicit methods/headers.

### Authentication (`security.py`)
- Google ID token verified server-side (audience, signature, `email_verified`,
  domain allow-list).
- Short-lived HS256 JWT session; `sub` parsed safely; inactive/missing users rejected.
- IMAP/SMTP app passwords encrypted with Fernet (key derived from `SECRET_KEY`),
  never returned by the API.

### LLM/agent guardrails (`llm/guardrails.py`)
| Control | Detects |
|---|---|
| `override_instructions` | "ignore previous instructions" |
| `reveal_system_prompt` | "print/reveal your system prompt" |
| `role_hijack` | "you are now…", "DAN mode", "developer mode" |
| `secret_exfiltration` | "print the api key/token/password" |
| `tool_abuse` | "run shell/python/os.system" |
| `delimiter_escape` | `<\|im_start\|>`, `[INST]` style tokens |
| size / empty / JSON | prompt too large, empty or invalid JSON output |

Rejected prompts raise `PromptRejected` (HTTP 400) and are audited.

---

## 5. Data governance

- **Classification** (`classification.py`): every field → `public | internal |
  confidential | restricted`. Sensitive names (password/token/api_key) auto-escalate
  to `restricted`. `may_leave_environment()` blocks restricted fields from external
  providers.
- **PII** (`pii.py`): email, phone (IN + intl), Aadhaar, PAN, GSTIN, credit card
  (Luhn-validated), IPv4. `redact()` → `[KIND]` tokens; `mask()` keeps shape;
  `redact_structured()` recurses through dict/list for logs.
- **Audit** (`audit.py`, `audit_logs` table): actor, action, resource, tenant,
  status, IP, redacted detail. Recorded on `auth.login`, `contact.create/update/delete`,
  every `llm.run`, and governance actions.
- **Retention** (`retention.py`): per-dataset windows; `purge(db, dry_run=True)`
  never touches `users`. Exposed at `POST /api/governance/retention/purge`.
- **GCP verification** (`gcp_verify.py`): project, ADC, database binding, GCS bucket,
  Secret Manager reachability — **status only, never values**. Shallow mode for health
  checks; `?deep=true` performs real client initialization.

---

## 6. Cost-optimised SLM routing

### Task → tier
| Task | Tier | Primary | Fallback | External allowed | JSON |
|---|---|---|---|---|---|
| `dedupe_match` | nano | local 0.5B | local 3B | no | yes |
| `classify_intent` | small | local 3B | local 8B | no | yes |
| `extract_entities` | small | local 3B | cloud flash | yes | yes |
| `summarize_profile` | small | local 3B | cloud flash | yes | no |
| `translate_script` | small | local 3B | cloud flash | yes | no |
| `draft_outreach_email` | medium | local 8B | cloud flash | yes | no |
| `generate_pitch` | large | cloud pro | cloud flash | yes | no |
| `research_synthesis` | large | cloud pro | cloud flash | yes | no |

Every chain ends in the offline `echo` provider, so the pipeline never hard-fails.

### Cost model (`estimate_cost_micros`, micro-USD per 1K tokens)
| Model | Input | Output |
|---|---|---|
| local (Ollama) / echo | 0 | 0 |
| gemini-2.0-flash-lite | 50 | 200 |
| gemini-2.0-flash | 100 | 400 |
| gemini-2.5-pro | 1250 | 5000 |

Levers: local SLM for cheap tasks, per-task `max_output_tokens`, monthly token
budget, PII containment, and the `model_usage` ledger reviewed via
`GET /api/governance/usage`.

---

## 7. Data model

| Table | Purpose | Key columns |
|---|---|---|
| `users` | identities | `google_sub`, `email`, `domain`, `is_active` |
| `contacts` | sales contacts (user-scoped) | unique `(user_id, email)`, `domain`, `intent`, `source`, `gcs_path` |
| `email_connections` | IMAP/SMTP per user | `secret_encrypted` (Fernet), `is_connected` |
| `linkedin_profiles` | scraped hiring profiles | `profile_url`, `source_keyword` |
| `reddit_posts` | hiring alerts | `post_url`, `subreddit` |
| `whatsapp_messages` | outbound queue | `phone_number`, `status` |
| `audit_logs` | append-only audit | `actor_user_id`, `action`, `status`, `detail` (redacted JSON) |
| `model_usage` | LLM cost ledger | `task`, `tier`, `provider`, `cost_micros`, `fallback_used` |

---

## 8. API reference

Base prefix `/api`. All endpoints except `/config` and `/health` require a bearer JWT.

### System
| Method | Path | Notes |
|---|---|---|
| GET | `/config` | public client config (no secrets) |
| GET | `/health` | DB / Redis / GCS / sign-in status |
| GET | `/integrations` | integration availability |
| POST | `/cron/run` | enqueue scheduled tasks to Redis |

### Auth
| Method | Path | Notes |
|---|---|---|
| POST | `/auth/google` | Google ID token → JWT; audited |
| GET | `/auth/me` | current user |

### Contacts
| Method | Path | Notes |
|---|---|---|
| GET | `/contacts` | filter by domain/intent/source/q |
| POST | `/contacts` | create + auto-classify; audited; best-effort GCS mirror |
| GET | `/contacts/stats` | totals by domain/intent/source |
| GET | `/contacts/{id}` | user-scoped |
| PATCH | `/contacts/{id}` | audited |
| DELETE | `/contacts/{id}` | audited |
| POST | `/contacts/import/gcs` | namespace-constrained import |

### Email
| Method | Path | Notes |
|---|---|---|
| GET | `/email/connections` | list |
| POST | `/email/connections` | store encrypted app password |
| POST | `/email/connections/{id}/test` | IMAP + SMTP check |
| GET | `/email/connections/{id}/inbox` | fetch messages |
| POST | `/email/send?connection_id=` | send mail |

### Social
| Method | Path |
|---|---|
| GET | `/social/linkedin/profiles` |
| POST | `/social/linkedin/search` |
| GET | `/social/reddit/posts` |
| POST | `/social/reddit/search` |
| POST | `/social/whatsapp/messages` |
| GET | `/social/whatsapp/messages` |

### Governance
| Method | Path | Notes |
|---|---|---|
| GET | `/governance/policy` | classification + retention + flags |
| GET | `/governance/gcp?deep=` | status-only GCP verification |
| GET | `/governance/audit` | current user's audit events |
| POST | `/governance/retention/purge?dry_run=` | retention purge |
| GET | `/governance/usage` | LLM calls/tokens/cost by provider |

### LLM
| Method | Path | Notes |
|---|---|---|
| GET | `/llm/tasks` | task registry + tiers |
| GET | `/llm/plan/{task}` | routing chain (no execution) |
| POST | `/llm/run` | guarded, budgeted, audited execution |

---

## 9. Migration runbook (local SQLite → Cloud SQL)

```text
1. alembic upgrade head            # apply schema
2. alembic check                   # must print "No new upgrade operations detected"
3. export current SQLite data      # contacts/users (JSON dump)
4. load into Cloud SQL             # psql COPY / staging + upsert on (user_id,email)
5. reconcile counts                # SELECT count(*) per table, per user
6. run app against Cloud SQL       # DATABASE_URL / CLOUD_SQL_CONNECTION_NAME
7. alembic downgrade base (staging only) to prove reversibility
8. cut over with feature flag; keep SQLite snapshot for rollback
```

Complete checks: schema parity (`alembic check`), row counts, `uq_contact_user_email`
integrity, audit-trail continuity, and a smoke test of `/api/health`,
`/api/contacts/stats`, `/api/governance/gcp`.

Local helper: `scripts/verify_migrations.ps1` (Windows) or `scripts/verify_migrations.sh`.

---

## 10. Testing

**57 tests**, coverage **74%** (gate 70%), run locally with `python -m pytest`.

| File | Focus |
|---|---|
| `test_auth.py` (4) | dev login, `/me`, missing/bad token |
| `test_system.py` (5) | public config, health, index, integrations auth/shape |
| `test_contacts.py` (8) | create/auto-segregate, duplicate, filters, stats, update/delete, user scoping, auth, GCS namespace |
| `test_services.py` (4) | domain/intent classification |
| `test_social.py` (4) | LinkedIn, Reddit, WhatsApp queue, cron |
| `test_security_guardrails.py` (4) | headers, oversized body, prod config validation, untrusted host |
| `test_pii.py` (6) | detection, redaction, Luhn, structured, masking |
| `test_governance.py` (6) | classification, audit redaction, retention, GCP shape |
| `test_llm_guardrails.py` (7) | injection, PII, size, JSON/output validation |
| `test_llm_router.py` (9) | local-first routing, fallback, injection reject, budget, cost, total failure |

---

## 11. CI/CD

```text
Pull request
  └─ .github/workflows/ci.yml
       quality      → ruff lint
       secrets      → gitleaks
       test         → pytest + coverage gate 70% (py3.11, py3.12)
       migration    → alembic upgrade head ▸ check ▸ downgrade base
       audit        → pip-audit
       docker       → image build

Merge to DEV/UAT/main
  └─ .github/workflows/cd.yml
       Workload Identity Federation (no JSON keys)
       gcloud builds submit --config cloudbuild.fastapi.yaml
       Cloud Run deploy + /api/health smoke test

Release gate (optional, GCP)
  └─ cloudbuild.checks.yaml
       lint ▸ SAST ▸ tests ▸ migrations ▸ image build ▸ Trivy HIGH/CRITICAL
```

Required GitHub configuration for CD:
- Secrets: `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT`
- Variables: `GCP_PROJECT_ID`, `GCP_REGION`, `ARTIFACT_REPOSITORY`,
  `CLOUD_SQL_INSTANCE`, `CORS_ORIGINS`, `ALLOWED_HOSTS`, `GCS_BUCKET`

Deploy secrets (Secret Manager, referenced by `cloudbuild.fastapi.yaml`):
`SALES_SECRET_KEY`, `SALES_DATABASE_URL`, `GOOGLE_CLIENT_ID`,
`GOOGLE_CLIENT_SECRET`, `GEMINI_API_KEY`.

---

## 12. Operations & troubleshooting

| Symptom | Check |
|---|---|
| Startup fails with `SECRET_KEY` error | set a ≥32-char non-default `SECRET_KEY` |
| `alembic check` reports drift | regenerate a revision (`alembic revision --autogenerate`) |
| LLM calls all return `echo` | Ollama not running and `GEMINI_API_KEY` unset — expected offline fallback |
| HTTP 429 during tests | `RATE_LIMIT_ENABLED=true` with a low limit; disable in tests |
| HTTP 400 untrusted host | add the host to `ALLOWED_HOSTS` |
| `/api/governance/gcp` not ok | run `gcloud auth application-default login` or fix service account |
| `python-dotenv could not parse statement` | malformed line in local `.env` (not committed) |

Health endpoints: `/api/health` (liveness/readiness summary),
`/api/governance/gcp` (integration status).

---

## 13. Future scope

Everything below is intentionally deferred. Each item lists what it needs and why
it is not in the current production revision.

### 13.1 Gemma personalisation (next phase)
- Add `GEMINI_API_KEY` to Secret Manager and `gcloud run services update --update-secrets`.
- Set `LLM_ENABLED=true`; router task `generate_outreach_message` then calls
  **Gemma → local SLM → cloud flash → echo**.
- Per-campaign `ai_model` already records which model produced each message.
- Add prompt templates per strategy, A/B variants, and a quality score before send.
- Cost guard: `LLM_MONTHLY_TOKEN_BUDGET`, per-task caps, usage ledger
  (`GET /api/governance/usage`).

### 13.2 Region co-location (cost + latency)
- Cloud SQL is `us-central1`; Cloud Run is `asia-south1` (cross-region socket).
- Migrate by creating a same-region instance, `pg_dump`/restore via the connector,
  flip `CLOUD_SQL_CONNECTION_NAME`, then decommission the old instance.
- Expected: lower query latency, lower network egress, simpler cost model.

### 13.3 Async work & scheduling
- Replace inline sends with **Cloud Tasks / Pub-Sub** (or Celery + Redis) for bulk
  campaigns, retries, rate limiting and provider backoff.
- **Cloud Scheduler** for daily scraping and campaign sweeps.
- Outbox pattern so a committed DB write never loses its event.

### 13.4 Channels
- **SarvamAI voice** (`feature/sarvam-voice`): TTS/STT voice notes (bulbul/saaras).
- **Wechaty live mode** (`feature/wechaty-whatsapp`): real account via
  `wechaty-puppet-wechat4u` / `wechaty-puppet-service`; QR login and inbound webhooks
  already supported.
- **Agent-Reach** (`feature/agent-reach`): internet read/search for lead discovery.

### 13.5 Analytics & governance
- **BigQuery** event spine (`analytics.*`) partitioned by day, clustered by tenant.
- **Multi-tenant** `tenant_id` + PostgreSQL row-level security.
- Retention/DPDP compliance surfaces, data-subject export/delete endpoints.
- Secret rotation + audit export.

### 13.6 Platform & observability
- **Google OAuth client**: create the Web client (origins: Cloud Run URL +
  `kalisoftai.in` + localhost), set the real `GOOGLE_CLIENT_ID`, then set
  `AUTH_DEV_MODE=false` to retire the restricted `ai.solutions@kalisoftai.in`
  dev-login (see `docs/DEPLOYMENT.md` §10).
- Cloud Logging/Trace with `request_id`, Cloud Monitoring uptime checks.
- **Budget alerts** and SLOs; per-tenant error-rate dashboard.
- Branch protection + required checks on `main`; manual approval only for schema
  migrations if desired.
- Frontend: componentisation, i18n, deeper accessibility (focus traps, live regions).

### 13.7 Account catalog, quote & invoice service
- The design and workbook mapping are tracked in [`ACCOUNT_TEMPLATES.md`](ACCOUNT_TEMPLATES.md).
- Start with a reviewed `data/All-project-matrices.xlsx` import and a versioned service
  catalog; the workbook remains ignored by Git until the controlled import path exists.
- Add user-scoped account, quote, and invoice models only after service IDs, tax fields,
  numbering, and approval roles are confirmed.
- Route catalog extraction, account matching, and customer-facing summaries through
  Gemma 4 behind a feature flag. Keep prices, tax, discounts, totals, invoice numbers,
  and status transitions deterministic and server-owned.
- Require human approval before sending a quote or finalizing an invoice; do not treat
  model output as a financial authority.

