# Kalisoft AI Sales Pipeline - Current State and Future Scope

Last updated: 2026-11-04

This document is the single-page reference for the current production application,
the environment contract, Google OAuth setup, and the next product scope. It is
derived from the live `.env` / `.env.example`, the FastAPI workspace, the Cloud Run
deployment configuration, and the Reddit content platform at
`D:\KaliSoftAI\Reddit-Post-Topic-Finder-main\backend`.

---

## 1. Current production snapshot

| Item | Value |
|---|---|
| GCP project | `gen-lang-client-0132243782` |
| GCP project number | `19782268668` |
| Region | `asia-south1` |
| Cloud Run service | `kalisoft-sales` |
| Production URL | `https://kalisoft-sales-19782268668.asia-south1.run.app` |
| Container image | `asia-south1-docker.pkg.dev/gen-lang-client-0132243782/sales-pipeline/kalisoft-sales` |
| Cloud SQL instance | `gen-lang-client-0132243782:us-central1:kalisoft-sales-data` |
| Runtime / CI service account | `kalisoft-sales-run@gen-lang-client-0132243782.iam.gserviceaccount.com` |
| Workload Identity provider | `projects/19782268668/locations/global/workloadIdentityPools/github/providers/github-provider` |
| GitHub repository | `KalisoftAI/ai_pitch_agent` |
| Active product | FastAPI + React sales workspace (`sales_fastapi/`, `frontend/`) |
| Legacy product | Django supplier extractor / pitch generator (retained in the repository) |
| Primary data store | Cloud SQL PostgreSQL in production; SQLite for local development |
| Object storage | Google Cloud Storage buckets `kalisoftai-datahub` and `kalika_enterprises` |

### Runtime architecture

```text
                         +--------------------------------------+
                         |  Browser / React SPA                 |
                         |  Cloud Run static build at /static   |
                         +------------------+-------------------+
                                            |
                         HTTPS / Bearer JWT  |  Google Identity Services
                                            v
+------------------------------+   +------------------------------+
|  Cloud Run: kalisoft-sales    |   |  Google OAuth / Gmail API    |
|  FastAPI + Uvicorn            |<->|  ID token + read-only Gmail  |
|                              |   +------------------------------+
|  Auth / RBAC / audit         |
|  Contacts / campaigns        |   +------------------------------+
|  Tally + ERP + in-store mail |<->|  Google Cloud Storage        |
|  Social signal desk          |   |  contacts, visits, Tally,    |
|  Prompt review / governance  |   |  mail snapshots              |
+---------------+--------------+   +------------------------------+
                |
                | Cloud SQL socket
                v
+------------------------------+
|  Cloud SQL PostgreSQL        |
|  users, contacts, mailboxes  |
|  visits, Tally, audit logs   |
+------------------------------+

External signals: LinkedIn API, Reddit API, YouTube Data API v3
AI routing: Gemma / Gemini through the LLM router; Ollama locally when enabled
```

### Current capabilities

| Area | What is live |
|---|---|
| Authentication | Google Identity Services ID-token sign-in; username/password fallback; allowlisted emails; JWT sessions; role checks |
| User isolation | Per-user contacts, mailboxes, visits, tasks and audit records |
| Contacts | CRUD, intent classification, CSV/GCS mirror, contact statistics |
| Outreach | Email templates, campaigns, IMAP/SMTP mailbox tests, Gmail OAuth mailbox connect |
| Sales BI | Tally Sales Register sync, dashboard summary, sales overview, KPI endpoints |
| Field operations | Company visits, map links, meeting notes, voice transcription hooks |
| In-store mail desk | Mail snapshots, extraction, client working names, follow-up actions |
| Market intelligence | LinkedIn, Reddit and YouTube signal endpoints |
| Governance | Audit trail, PII redaction, Fernet-encrypted secrets, retention settings, prompt review |
| Operations | Health, UAT status, preflight checks, model list, logs, scheduler tasks |
| Deployment | GitHub Actions CI/CD, Cloud Run, Artifact Registry, Cloud SQL, Secret Manager |

### Current production OAuth state

Google sign-in is enabled by the same OAuth web client used for Gmail read-only
access. The production deployment must provide these values:

```text
GOOGLE_CLIENT_ID=<web client id>.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=<web client secret>
GOOGLE_ALLOWED_EMAILS=ai.solutions@kalisoftai.in,kalikaenterprises@gmail.com
GOOGLE_REDIRECT_URI=https://kalisoft-sales-19782268668.asia-south1.run.app
GMAIL_OAUTH_ENABLED=true
GOOGLE_OAUTH_REDIRECT_URI=https://kalisoft-sales-19782268668.asia-south1.run.app//api/email/google/callback
FRONTEND_URL=https://kalisoft-sales-19782268668.asia-south1.run.app
AUTH_DEV_MODE=false
```

Google Cloud Console must contain these authorized origins and redirect URIs:

```text
Authorized JavaScript origins
  https://kalisoft-sales-19782268668.asia-south1.run.app
  https://kalisoftai.in
  https://www.kalisoftai.in
  http://localhost:5173
  http://localhost:8000

Authorized redirect URIs
  https://kalisoft-sales-19782268668.asia-south1.run.app//api/email/google/callback
  http://localhost:8000//api/email/google/callback
```

The existing OAuth client currently has the double-slash Gmail callback
registered. The app includes a bridge route at
`//api/email/google/callback` that redirects to the canonical
`/api/email/google/callback` while preserving `code` and `state`. When the
single-slash URI is added in Google Cloud Console, update
`GOOGLE_OAUTH_REDIRECT_URI` and remove the bridge if desired.

The production values are injected by `.github/workflows/cd.yml` from GitHub
Actions secrets and variables. The OAuth client secret is never committed.

Verification:

```powershell
curl https://kalisoft-sales-19782268668.asia-south1.run.app/api/config
# google_client_id must be non-empty
# google_gmail_oauth_configured must be true

curl https://kalisoft-sales-19782268668.asia-south1.run.app/api/health
# google_signin_configured must be true
# dev_mode must be false
```

---

## 2. Environment contract

The application reads `.env` locally and Cloud Run environment variables in
production. Secrets are supplied through Secret Manager or GitHub Actions secrets.
The table below lists the keys, not their values.

### Core runtime

| Variable | Purpose |
|---|---|
| `ENV` | `development`, `staging`, `uat` or `production` |
| `SECRET_KEY` | JWT signing and Fernet key derivation; at least 32 characters |
| `AUTH_DEV_MODE` | Local-only synthetic sign-in; must be `false` in production |
| `AUTH_DEV_ALLOWED_EMAILS` | Optional allowlist when dev mode is enabled |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Session lifetime, 5-1440 minutes |
| `DATABASE_URL` | Full SQLAlchemy URL; wins over individual Postgres fields |
| `CLOUD_SQL_CONNECTION_NAME` | Cloud SQL unix-socket connection name |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Postgres fallback fields |
| `SQLITE_PATH` | Local SQLite fallback path |
| `ALLOWED_HOSTS` | Trusted host middleware list |
| `CORS_ORIGINS` | Comma-separated browser origins |
| `MAX_REQUEST_BYTES` | Request body guardrail |
| `RATE_LIMIT_ENABLED`, `AUTH_RATE_LIMIT`, `API_RATE_LIMIT` | Rate-limit controls |

### Google, Gmail and AI

| Variable | Purpose |
|---|---|
| `GOOGLE_CLOUD_PROJECT` | GCP project for ADC and storage |
| `GOOGLE_CLIENT_ID` | OAuth web client ID for Google Sign-In and Gmail |
| `GOOGLE_CLIENT_SECRET` | OAuth web client secret; server-side only |
| `GOOGLE_ALLOWED_DOMAINS` | Optional domain allowlist |
| `GOOGLE_ALLOWED_EMAILS` | Strict per-email sign-in allowlist; takes precedence |
| `GOOGLE_REDIRECT_URI` | Authorized sign-in redirect URI for documentation and GIS |
| `GMAIL_OAUTH_ENABLED` | Enables Gmail read-only OAuth connection |
| `GOOGLE_OAUTH_REDIRECT_URI` | Gmail callback; must exactly match Google Cloud Console (currently the registered double-slash URI) |
| `FRONTEND_URL` | Post-OAuth browser redirect target |
| `GEMINI_API_KEY` | Optional Gemini key; empty means no cloud LLM |
| `GEMMA_MODEL` | Primary Gemma model name, default `gemma-4-27b-it` |
| `LLM_GEMMA_MODEL` | Gemma model used by the LLM router |
| `LLM_ENABLED` | Master switch for LLM calls; defaults to `false` |
| `LLM_LOCAL_*` | Ollama model names and local base URL |
| `LLM_CLOUD_*` | Gemini fallback model names |

### Storage, mail and signals

| Variable | Purpose |
|---|---|
| `GCS_BUCKET_CONTACTS`, `GCS_PATH_CONTACTS` | Contact mirror |
| `GCS_BUCKET_MEDIA`, `GCS_PATH_VISITS` | Visit media |
| `GCS_BUCKET_MAIL`, `GCS_PATH_INSTORE_MAILS` | In-store mail snapshots |
| `TALLY_BUCKET`, `TALLY_SALES_PREFIX` | Tally Sales Register source |
| `ERP_REPORT_PREFIX`, `ERP_CACHE_PATH` | ERP report sync |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` | Outbound mail |
| `IMAP_HOST`, `IMAP_PORT`, `IMAP_USER` | Mailbox reading |
| `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_ACCESS_TOKEN` | LinkedIn integration |
| `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` | Reddit integration |
| `YOUTUBE_API_KEY`, `YOUTUBE_CHANNEL_ID` | YouTube Data API v3 |
| `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_ACCOUNT_ID` | Instagram insights |
| `WHATSAPP_API_KEY`, `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp Cloud API |
| `WECHATY_*` | Wechaty gateway for WhatsApp/WeChat |
| `REDIS_URL` | Scheduler queue and cache |

### Governance

| Variable | Purpose |
|---|---|
| `GOVERNANCE_ENABLED` | Audit and governance checks |
| `PII_REDACTION_ENABLED` | Redact personal data in logs and prompts |
| `AUDIT_LOG_ENABLED` | Append-only audit trail |
| `RETENTION_DAYS_AUDIT`, `RETENTION_DAYS_CONTACTS` | Retention windows |
| `HUMAN_REVIEW_REQUIRED` | Prompt/output review gate |

---

## 3. Future scope from the Reddit content platform

Source reviewed: `D:\KaliSoftAI\Reddit-Post-Topic-Finder-main\backend`

The Reddit project is an AI thought-leadership content engine. It is not a news
aggregator; it finds recurring concepts and durable strategic themes.

### Existing Reddit pipeline

```text
Reddit (8 subreddits)  +  Medium (7 tags)
             |
             v
      Topic collection
             |
             v
      AI topic analysis
             |
             v
      Concept extraction
             |
             v
      Trend clustering
             |
             v
      Topic ranking (0-100)
             |
             v
      Research collection
             |
             v
      Article generation
             |
             v
      LinkedIn post + graphic prompt
```

Current source list:

```text
Reddit:  r/artificial, r/machinelearning, r/LocalLLaMA, r/OpenAI,
         r/ClaudeAI, r/entrepreneur, r/startups, r/programming

Medium:  artificial-intelligence, machine-learning, startups,
         programming, saas, product-management
```

Current data model:

| Table | Fields |
|---|---|
| `topics` | `id`, `title`, `score`, `reason`, `status`, `created_at` |
| `articles` | `id`, `topic_id`, `title`, `content`, `linkedin_post`, `graphic_prompt`, `status`, `created_at` |
| `reddit_posts` | `external_id`, `title`, `score`, `url`, `subreddit`, `comments` |
| `medium_articles` | `title`, `author`, `url`, `published_date` |

Current API shape:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/discover-topics` | Collect Reddit/Medium signals and rank topics |
| `GET` | `/api/topics` | List ranked topics |
| `POST` | `/api/generate-article` | Research, write article, LinkedIn post and graphic prompt |
| `GET` | `/api/articles` | List generated articles |
| `GET` | `/api/articles/{id}` | Read one article |

Ranking rules to preserve:

- High score: prompt security, AI governance, AI ethics, AI safety, agent
  architectures, agent loops, context engineering, enterprise adoption, AI
  evaluation, workflow automation, multi-agent systems, agent memory, ecommerce AI,
  conversational commerce, AI infrastructure.
- Low score: funding news, acquisitions, layoffs, product launches, version
  releases, company announcements.
- Exception: a news event is allowed only when it reveals a durable trend.

### Integration proposal for the sales pipeline

Add a **Market Intelligence** workspace that turns external signals into
company-specific conversations:

```text
Reddit + Medium + LinkedIn + YouTube
                  |
                  v
        Signal collector / normalizer
                  |
                  v
        Company + contact resolver
                  |
                  v
        Topic and intent classifier
                  |
                  v
        Recommendation engine
                  |
                  v
        Human review -> outreach / task queue
```

New backend modules:

```text
sales_fastapi/signals/
  collector.py       # Reddit, Medium, LinkedIn, YouTube adapters
  normalizer.py      # canonical URL, title, author, timestamp, language
  company_resolver.py# domain/company matching against CRM
  ranking.py         # durable-trend scoring and deduplication
  recommendations.py # next-best-action generation

sales_fastapi/agents/
  planner.py         # Gemma task decomposition
  router.py          # assign subtasks to specialist agents
  workers.py         # research, enrichment, drafting, QA
  guardrails.py      # approval gates and prompt-injection checks
```

Suggested tables:

| Table | Purpose |
|---|---|
| `signal_sources` | Source configuration and health |
| `signal_items` | Normalized Reddit/Medium/LinkedIn/YouTube records |
| `signal_topics` | Clustered concepts and scores |
| `company_signals` | Company-to-signal matches with evidence |
| `recommendations` | Ranked next-best actions and rationale |
| `agent_tasks` | Parent task, subtask, assignee agent, status, priority |
| `agent_runs` | Model, prompt version, tokens, latency, outcome |
| `contact_enrichment` | Company, role, domain, confidence, provenance |

Suggested API surface:

```text
POST /api/signals/discover
GET  /api/signals/topics
GET  /api/signals/companies/{domain}
POST /api/recommendations/generate
GET  /api/recommendations
POST /api/agent/tasks/plan
POST /api/agent/tasks/{id}/assign
GET  /api/agent/tasks
```

---

## 4. LinkedIn, Reddit and YouTube expansion

### LinkedIn

Use the official LinkedIn API and OAuth. Do not scrape logged-in pages.

Features:

- Company page and employee signal monitoring.
- Hiring-signal detection from job posts and company updates.
- Contact and account enrichment with role, seniority and department.
- Thought-leadership post generation from approved articles.
- Engagement analytics: impressions, reactions, comments and click-through.
- Lead scoring based on company fit, hiring activity and content engagement.
- Human approval before any outbound post or message.

Existing hooks: `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`,
`LINKEDIN_ACCESS_TOKEN`, `/api/social/linkedin/search`, `/api/social/overview`.

### Reddit

Use PRAW with a registered script app. Respect rate limits and subreddit rules.

Features:

- Topic discovery and trend clustering across the eight AI/startup subreddits.
- Comment-level pain-point extraction and sentiment.
- Company/product mention detection.
- Hiring, procurement and supply-chain intent signals.
- Lead-magnet and article idea generation.
- Weekly digest of durable themes, not breaking-news summaries.

Existing hooks: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`,
`/api/social/reddit/search`, `/api/social/overview`.

### YouTube

Use YouTube Data API v3 for search and metadata; use OAuth for private analytics.

Features:

- Search videos by company, product, hiring or supply-chain topic.
- Channel statistics and upload cadence.
- Transcript retrieval and summarization.
- Comment mining for objections, competitors and customer language.
- Video-to-article and video-to-LinkedIn-post generation.
- Competitor content and keyword gap analysis.
- Watch-time and traffic-source analytics with OAuth.

Existing hooks: `YOUTUBE_API_KEY`, `YOUTUBE_CHANNEL_ID`,
`/api/social/youtube/search`, `/api/social/overview`.

---

## 5. Gmail contacts, company intelligence and agent subtasks

### Goal

Turn the sales mailbox into a structured, company-aware contact graph, then use
Gemma to recommend the next best action and split it into assignable subtasks.

### Pipeline

```text
Gmail OAuth (read-only)
        |
        v
Contact + signature extraction
        |
        v
Company / domain resolver
        |
        v
Company profile enrichment
  - website, industry, size, location
  - products, brands, markets
  - recent signals from LinkedIn/Reddit/YouTube
        |
        v
Recommendation engine
  - fit score
  - intent score
  - next best action
  - evidence and confidence
        |
        v
Gemma task planner
  - decompose action into subtasks
  - assign to specialist agents
  - set priority, due date and approval gate
        |
        v
Human review -> CRM task queue -> outreach
```

### Contact extraction

Extract from Gmail messages and signatures:

```text
name, email, phone, role, company, domain, location,
last_contact_at, thread_count, topics, sentiment,
source_message_ids, confidence
```

Rules:

- Read-only Gmail scope only.
- Never store raw message bodies longer than necessary.
- Store provenance and confidence for every extracted field.
- Deduplicate by normalized email and company domain.
- Require human confirmation for low-confidence contacts.

### Company recommendations

For each company, produce:

```text
company_fit_score      0-100
intent_score           0-100
relationship_strength  0-100
recommended_action     e.g. "follow up on Tally sync issue"
rationale              evidence-linked explanation
suggested_owner        sales / field / support agent
suggested_due_date     based on urgency and last contact
```

### Gemma task decomposition

Use Gemma for structured, low-cost planning. Use Gemini only when the context is
large or the task needs deeper reasoning.

```text
Parent recommendation
        |
        v
Gemma planner
  input:  recommendation, company profile, contact history, policy
  output: JSON array of subtasks
        |
        +--> research_agent    : gather company and signal evidence
        +--> enrichment_agent  : fill missing contact/company fields
        +--> outreach_agent    : draft email or LinkedIn message
        +--> followup_agent    : schedule reminder and next touch
        +--> qa_agent          : check facts, tone, consent and policy
        |
        v
Human approval gate
        |
        v
Execute / queue / assign
```

Example planner output:

```json
{
  "recommendation_id": 42,
  "model": "gemma-4-27b-it",
  "subtasks": [
    {
      "agent": "research_agent",
      "title": "Collect recent company signals",
      "priority": "high",
      "depends_on": []
    },
    {
      "agent": "outreach_agent",
      "title": "Draft follow-up on Tally reconciliation",
      "priority": "high",
      "depends_on": ["research_agent"]
    },
    {
      "agent": "qa_agent",
      "title": "Check claims and approval policy",
      "priority": "medium",
      "depends_on": ["outreach_agent"]
    }
  ]
}
```

### Model routing

| Tier | Model | Use |
|---|---|---|
| Nano | local `qwen2.5:0.5b` | classification, dedupe, simple extraction |
| Small | local `gemma3:4b` | drafting, summaries, task decomposition |
| Medium | local `llama3.1:8b` or Gemma 4 27B | company research, recommendations |
| Cloud | `gemini-2.5-flash` / `gemini-2.5-pro` | long context, complex reasoning |
| Gemma | `gemma-4-27b-it` | structured planning and personalization |

Guardrails:

- Prompt-injection detection on all external text.
- PII redaction before LLM calls.
- Token budget and per-user cost ledger.
- Human approval for outbound messages.
- Full audit of model, prompt version, input hash and output.

---

## 6. Phased roadmap

### Phase 1 - OAuth and production hardening (now)

- Enable Google Sign-In and Gmail OAuth in production.
- Move OAuth client credentials into GitHub Actions secrets and Cloud Run env.
- Verify `/api/config` and `/api/health`.
- Add OAuth smoke tests and redirect-URI checks to CI.
- Rotate the Gmail app password and retire SMTP password fallback where possible.

Acceptance:

```text
Google button visible on production sign-in
Allowlisted Google account can sign in
Non-allowlisted account receives 403
Gmail OAuth connect returns to FRONTEND_URL with gmail=connected
No secret is present in git history or build logs
```

### Phase 2 - Content intelligence

- Port Reddit/Medium collectors and topic ranking.
- Add signal normalization and deduplication.
- Add company matching against CRM contacts.
- Add a Market Intelligence UI tab.
- Add weekly digest and article/LinkedIn draft generation.

### Phase 3 - Gmail contact intelligence

- Add contact and signature extraction.
- Add company/domain resolution and enrichment.
- Add recommendation scoring and evidence.
- Add human review queue.

### Phase 4 - Agent orchestration with Gemma

- Add task planner and specialist agents.
- Add dependency-aware subtask assignment.
- Add approval gates and execution logs.
- Add cost, latency and quality dashboards.

### Phase 5 - LinkedIn, YouTube and analytics

- LinkedIn company and hiring signals.
- YouTube search, transcripts, comments and channel analytics.
- Cross-channel attribution and BigQuery KPI warehouse.
- Multi-tenant row-level security.

---

## 7. Related documents

- `README.md` - project overview and run instructions.
- `APP_OVERVIEW_AND_USAGE.md` - current application walkthrough.
- `MIGRATIONS_AND_FEATURES.md` - migration and feature changelog.
- `docs/DEPLOYMENT.md` - Cloud Run, Cloud SQL and Secret Manager runbook.
- `Kalika_Sales_Deploy_UAT_Runbook.md` - UAT deployment checklist.
- `ROADMAP.md` - longer product roadmap.
- Reddit source: `D:\KaliSoftAI\Reddit-Post-Topic-Finder-main\backend`
