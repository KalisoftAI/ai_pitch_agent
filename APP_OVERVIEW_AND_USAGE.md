# Kalisoft AI Sales Pipeline - App Overview and Usage

**Product:** Kalisoft AI Sales Pipeline (Kalika Sales Workspace)  
**GCP project:** `gen-lang-client-0132243782` (`19782268668`)  
**Production:** https://kalisoft-sales-19782268668.asia-south1.run.app  
**Health check:** https://kalisoft-sales-19782268668.asia-south1.run.app/api/health  
**Primary admin account:** ai.solutions@kalisoftai.in  
**Architecture, environment and roadmap:** [PROJECT_STATUS_AND_FUTURE_SCOPE.md](PROJECT_STATUS_AND_FUTURE_SCOPE.md)

---

## 1. What the app does

One workspace for:

- Sales contacts and account intelligence
- Email / WhatsApp / LinkedIn / WeChat outreach
- Human-reviewed AI campaign generation
- Tally sales reporting and monthly BI
- Field visits, voice notes and follow-ups
- In-store mail extraction and client mapping
- Governance, audit logs, PII redaction and usage/cost tracking

The backend is FastAPI. The frontend is React/Vite. Production runs on Cloud Run
with Cloud SQL Postgres, Google Cloud Storage and optional Redis.

---

## 2. High-level architecture

```text
+---------------------------+
| Browser / Mobile browser  |
| React UI (Vite build)     |
+-------------+-------------+
              |
              | HTTPS  /api/*
              v
+---------------------------+
| Cloud Run :8080           |
| FastAPI application       |
|                           |
|  +---------------------+  |
|  | Auth / RBAC         |  |
|  | Contacts            |  |
|  | Outreach/Campaigns  |  |
|  | Tally / Sales BI    |  |
|  | Visits / Voice      |  |
|  | In-store Mail       |  |
|  | Governance / Audit  |  |
|  +----------+----------+  |
+-------------+-------------+
              |
     +--------+---------+----------------+----------------+
     |                  |                |                |
     v                  v                v                v
+---------+       +-----------+    +-----------+    +-----------+
| Cloud   |       | GCS       |    | Redis     |    | SMTP /    |
| SQL     |       | contacts, |    | queue /   |    | IMAP /    |
| Postgres|       | mail,     |    | cache     |    | Gmail     |
|         |       | tally, ERP|    | (optional)|    |           |
+---------+       +-----------+    +-----------+    +-----------+
```

### Request safety path

```text
Client request
   |
   v
Size limit (413) -> Rate limit (429) -> Trusted hosts
   |
   v
Authentication (Google ID token or username/password)
   |
   v
JWT session token -> Role check (admin / sales / field)
   |
   v
Route handler -> SQLAlchemy -> Cloud SQL
   |
   v
Audit event (PII-redacted) + response
```

---

## 3. Sign-in and roles

### Sign-in methods

1. **Google Sign-In** - available when `GOOGLE_CLIENT_ID` is configured.
   Only allow-listed emails are accepted.
2. **Username + password** - for local, field and operations accounts.
   An email address or a configured username can be used.

### Roles

| Role | Typical access |
|---|---|
| `admin` | Full workspace, user management, syncs, exports, approvals |
| `sales` | Dashboard, catalogue, campaigns, reports, team review |
| `field` | Field updates, visits, voice capture; no approvals |

Admins are also identified by `ADMIN_EMAILS` (default:
`ai.solutions@kalisoftai.in`).

### Login flow

```text
+------------------+       +---------------------+       +------------------+
| User enters      |       | FastAPI /api/auth   |       | Cloud SQL users  |
| email/username   | ----> | verify credentials  | ----> | lookup + hash    |
| + password       |       |                     |       | check            |
+------------------+       +----------+----------+       +------------------+
                                      |
                                      v
                           +----------------------+
                           | Issue short-lived JWT|
                           | + audit login event  |
                           +----------------------+
```

---

## 4. Main workspaces and how to use them

### 4.1 Overview / Dashboard

Shows live totals, intent breakdown, recent contacts, system pulse and Tally sales
summary. Use **Refresh** to re-poll. Admin users see sync and integration status.

### 4.2 Contacts

| Task | Steps |
|---|---|
| Search | Type company, name or email in the search box |
| Add one | **New contact** -> fill email + details -> Save |
| Upload many | **Upload files** -> CSV / XLSX / XLS / VCF / JSON |
| Sync GCS | Enter a prefix -> **Sync GCS path** |
| Delete | Trash icon on a row -> confirm |

Contacts are user-scoped and de-duplicated by email.

### 4.3 Templates and Outreach

1. Open **Outreach** -> **Templates**.
2. Click **Seed templates** to load the Kalisoft defaults.
3. Choose channel and strategy.
4. Build a campaign and generate messages.
5. Review every message.
6. **Approve all** (human gate).
7. **Send approved**.

Channels:

- `email` -> SMTP using the configured Email connection
- `whatsapp` / `wechat` -> Wechaty gateway
- `linkedin` -> queued for manual action

Nothing sends before approval. Create / approve / send actions are audited.

```text
Select contacts
      |
      v
Render template + optional AI personalisation
      |
      v
Human review queue  --- reject ---> edit / regenerate
      |
      v
Approve all
      |
      v
Send by channel -> per-message status -> campaign history
```

### 4.4 Sales BI and Tally

The Tally panel reads sales workbooks from GCS or local mirrors.

- Source: `gs://kalika_enterprises/kalika_sales2026/`
- Supported files: `.xls`, `.xlsx`
- Parsed fields: date, period, buyer, GSTIN, voucher, item, quantity, rate, value,
  invoice total, tax
- Cancelled invoices are excluded
- Rows are upserted by `source_file + source_row`

Admin actions:

- `GET /api/tally/status`
- `GET /api/tally/overview`
- `GET /api/tally/sales`
- `POST /api/tally/sync`
- `POST /api/tally/upload`

```text
Tally workbook(s)
      |
      v
Parser: headers, continuation rows, cancelled vouchers
      |
      v
Normalise date / period / buyer / item / value
      |
      v
Upsert tally_sales (source_file + source_row)
      |
      +--> /api/tally/overview  -> dashboard cards
      +--> /api/tally/sales     -> sales table
      +--> /api/dashboard/summary -> Tally block
```

Scheduled sync: `tally_sales_sync` at `06:15` daily.

### 4.5 Field visits and voice

- Record company visits, meeting person, location, previous discussion and
  mail/chat details.
- Capture voice notes; transcripts are stored and searchable.
- Use follow-up copy / WhatsApp links from company history.
- Sample visits: `POST /api/visits/samples` (idempotent).

### 4.6 In-store mail desk

Normalises Gmail / IMAP / WhatsApp exports into client insights:

- Working title, client name, owner, outcome, entities
- Snapshot stored in GCS
- Dashboard reads `/api/instore/*`

```text
Gmail / IMAP / WhatsApp export
          |
          v
instore_mail.normalize()
          |
          v
insights JSON -> GCS snapshot
          |
          v
/api/instore/* -> Mail desk UI
```

### 4.7 Prompt review / UAT

Users can submit prompt comments and proposed changes. Admins review them.

- Submit: `POST /api/ops/prompt-reviews`
- List: `GET /api/ops/prompt-reviews`
- Approve / reject: `POST /api/ops/prompt-reviews/{id}/review`

```text
User comment / proposed prompt change
              |
              v
        pending review queue
              |
       +------+------+
       |             |
    approve        reject
       |             |
       v             v
  applied note   review note
       +------+------+
              |
              v
        audit trail
```

### 4.8 Governance and security

- Google ID-token verification and short-lived JWT sessions
- Role-based access control
- Fernet encryption for stored mail passwords
- PII redaction and classification
- Append-only audit log
- Rate limits, request size limits, trusted hosts, CSP/HSTS in production
- LLM guardrails and cost budgets

Useful endpoints:

- `GET /api/governance/policy`
- `GET /api/governance/gcp`
- `GET /api/governance/audit`
- `GET /api/governance/usage`
- `GET /api/security/status`

---

## 5. Quick start

### Production

1. Open https://kalisoft-sales-19782268668.asia-south1.run.app
2. Sign in with the approved Google account or username/password.
3. Check the **Overview** tab.
4. Admin users can open user management, syncs and review queues.

### Local development

```powershell
# Backend
python run.py --seed

# Frontend
cd frontend
npm install
npm run dev
```

Open:

- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- Frontend: http://localhost:5173/static/
- Wechaty gateway: http://localhost:8788/health

---

## 6. API map (selected)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | DB / Redis / GCS / sign-in status |
| POST | `/api/auth/google` | Google ID token -> JWT |
| POST | `/api/auth/password` | Username/password -> JWT |
| GET | `/api/auth/me` | Current user |
| GET/POST | `/api/users` | List / create users (admin) |
| PATCH | `/api/users/{id}` | Update role, active flag, password (admin) |
| GET/POST | `/api/contacts` | List / create contacts |
| GET | `/api/contacts/stats` | Contact totals |
| GET/POST | `/api/email/connections` | Mail connection settings |
| POST | `/api/email/send` | Send email via SMTP |
| GET/POST | `/api/campaigns` | Campaign list / create |
| GET | `/api/tally/status` | Tally source and sync status |
| GET | `/api/tally/overview` | Tally monthly summary |
| GET | `/api/tally/sales` | Tally sales rows |
| POST | `/api/tally/sync` | Trigger Tally sync (admin) |
| GET/POST | `/api/visits` | Field visits |
| GET/POST | `/api/instore/*` | In-store mail insights |
| GET/POST | `/api/ops/prompt-reviews` | Prompt review queue |
| GET | `/api/governance/audit` | Audit events |
| GET | `/api/governance/usage` | LLM usage and cost |

---

## 7. Operations

### Database migrations

```powershell
alembic upgrade head
alembic check
```

Local verification helper:

```powershell
.\scripts\verify_migrations.ps1
```

### Tests and checks

```powershell
python -m pytest -q
python -m ruff check sales_fastapi tests migrations
python -m bandit -r sales_fastapi -x sales_fastapi/static -ll
cd frontend; npm run build
```

### Health and deployment

- Production image: `asia-south1-docker.pkg.dev/gen-lang-client-0132243782/sales-pipeline/kalisoft-sales`
- Cloud Run service: `kalisoft-sales` in `asia-south1`
- Cloud SQL instance: `gen-lang-client-0132243782:us-central1:kalisoft-sales-data`
- Health check: `GET /api/health`
- Production docs are disabled; use local `/docs` or this document.

---

## 8. Troubleshooting

| Symptom | Check |
|---|---|
| 401 on login | Account exists, is active, and has a password set |
| 403 admin action | User email is in `ADMIN_EMAILS` or role is `admin` |
| 403 Google login | Email is in `GOOGLE_ALLOWED_EMAILS` |
| 429 responses | Rate limit; wait or disable locally |
| Tally panel empty | Run `/api/tally/sync` and check GCS access |
| LLM always `echo` | Ollama/API key unavailable; offline fallback is expected |
| Mail send fails | SMTP host, user, app password and TLS settings |
| DB connection fails | `DATABASE_URL`, Cloud SQL attachment and credentials |
| `alembic check` drift | Generate and review a new migration |

---

## 9. Security notes

- Never commit `.env`, service-account keys or app passwords.
- Use Google App Passwords for Gmail SMTP/IMAP, not the main password.
- Rotate any credential that was shared in plain text.
- Keep production `AUTH_DEV_MODE=false`.
- Use least-privilege roles: `field` for field staff, `sales` for regular users,
  `admin` only for operations owners.
- Review the audit log after role or permission changes.

---

## 10. Current status snapshot

| Area | Status |
|---|---|
| Production Cloud Run | Live |
| Cloud SQL Postgres | Connected |
| GCS | Available |
| Redis | Optional / may be unavailable |
| Tally sales sync | Implemented |
| Prompt review workflow | Implemented |
| Google OAuth | Configured only when client ID/secret are set |
| Username/password login | Implemented |
| Field visits and voice | Implemented |
| In-store mail desk | Implemented |
| Governance and audit | Implemented |
