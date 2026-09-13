# Implementation Roadmap — Security, Governance, SLM Routing & CI/CD

Status: **Phase 1–6 implemented** on `sales-gcp-migration` (commit `123402c`). Voice,
WhatsApp and Agent-Reach remain as documented backlog branches.

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

## 2. Implemented phases

| Phase | Deliverable | Files |
|---|---|---|
| 1 | LLM/agent guardrails | `sales_fastapi/llm/guardrails.py`, `sales_fastapi/guardrails.py` |
| 2 | Data governance | `sales_fastapi/governance/{pii,classification,audit,retention,gcp_verify}.py` |
| 3 | Cost-optimised SLM router | `sales_fastapi/llm/{tasks,providers,router}.py` |
| 4 | DB migrations (SQLite/Cloud SQL) | `alembic.ini`, `migrations/**` |
| 5 | Wiring + endpoints | `sales_fastapi/routers/governance.py`, `main.py`, `models.py`, `config.py` |
| 6 | Tests + CI/CD + docs | `tests/test_{pii,governance,llm_guardrails,llm_router}.py`, `.github/workflows/*`, `cloudbuild.checks.yaml` |

## 3. Agent / task → model tier (cost optimisation)

| Task | Tier | Primary | Fallback | External? |
|---|---|---|---|---|
| `dedupe_match` | nano | local 0.5B | local 3B | no |
| `classify_intent` | small | local 3B | local 8B | no |
| `extract_entities` | small | local 3B | cloud flash | yes |
| `summarize_profile` | small | local 3B | cloud flash | yes |
| `translate_script` | small | local 3B | cloud flash | yes |
| `draft_outreach_email` | medium | local 8B | cloud flash | yes |
| `generate_pitch` | large | cloud pro | cloud flash | yes |
| `research_synthesis` | large | cloud pro | cloud flash | yes |

Every chain ends in the offline `echo` provider so the pipeline never hard-fails.
Switch local models via `LLM_LOCAL_*` env vars; the router adapts with no code change.

## 4. Cost model

Estimated micro-USD per 1K tokens (`estimate_cost_micros`):

| Model | Input | Output |
|---|---|---|
| local (Ollama) / echo | 0 | 0 |
| gemini-2.0-flash-lite | 50 | 200 |
| gemini-2.0-flash | 100 | 400 |
| gemini-2.5-pro | 1250 | 5000 |

Cost levers: route cheap tasks to local SLMs; cap `max_output_tokens` per task;
enforce `LLM_MONTHLY_TOKEN_BUDGET`; avoid sending PII externally; use the
`model_usage` ledger to review provider mix via `/api/governance/usage`.

## 5. Data governance controls

- **Classification** — every field mapped to public/internal/confidential/restricted.
- **PII** — email, phone, Aadhaar, PAN, GSTIN, card (Luhn-checked), IP detected and redacted.
- **Audit** — append-only `audit_logs`; details always PII-redacted; auth + contact
  mutations + LLM runs recorded.
- **Retention** — per-dataset windows; `POST /api/governance/retention/purge?dry_run=true`.
- **GCP verification** — `GET /api/governance/gcp` reports project/ADC/DB/GCS/Secrets
  status only, never values.
- **Secrets** — Secret Manager references in `cloudbuild.fastapi.yaml`; `.env` ignored.

## 6. Migration runbook (local SQLite → Cloud SQL)

```text
1. alembic upgrade head            # apply schema
2. alembic check                   # must print "No new upgrade operations detected"
3. export current SQLite data      # contacts/users (JSON dump)
4. load into Cloud SQL             # psql COPY / staging table + upsert on (user_id,email)
5. reconcile counts                # SELECT count(*) per table, per user
6. run app against Cloud SQL       # DATABASE_URL / CLOUD_SQL_CONNECTION_NAME
7. alembic downgrade base (staging only) to prove reversibility
8. cut over with feature flag; keep SQLite snapshot for rollback
```

Complete checks: schema parity (`alembic check`), row counts, unique constraint
`uq_contact_user_email`, audit trail continuity, and a smoke test of
`/api/health`, `/api/contacts/stats`, `/api/governance/gcp`.

## 7. CI/CD steps

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
`secrets.GCP_WORKLOAD_IDENTITY_PROVIDER`, `secrets.GCP_SERVICE_ACCOUNT`, and
`vars.GCP_PROJECT_ID`, `vars.GCP_REGION`, `vars.ARTIFACT_REPOSITORY`,
`vars.CLOUD_SQL_INSTANCE`, `vars.CORS_ORIGINS`, `vars.ALLOWED_HOSTS`, `vars.GCS_BUCKET`.

## 8. Backlog (documented feature branches)

- `feature/sarvam-voice` — TTS/STT voice notes.
- `feature/wechaty-whatsapp` — WhatsApp channel.
- `feature/agent-reach` — internet read/search for lead discovery.
- BigQuery event spine (`analytics.*`) after transactional Cloud SQL writes are stable.
