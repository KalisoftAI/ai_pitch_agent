"""Build Kalika_CRM_Integration_Analysis.xlsx — structured CRM analysis + integration map."""
import os
import google.auth
from google.cloud import storage
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "Kalika_CRM_Integration_Analysis.xlsx")
GCS_DEST = "sales-metadata/Kalika_CRM_Integration_Analysis.xlsx"

HDR_FILL = PatternFill("solid", fgColor="1F4E79")
HDR_FONT = Font(color="FFFFFF", bold=True, size=11)
TITLE_FONT = Font(bold=True, size=14, color="1F4E79")
SUB_FONT = Font(bold=True, size=11, color="2E74B5")
THIN = Border(*[Side(style="thin", color="BFBFBF")] * 4)
WRAP = Alignment(vertical="top", wrap_text=True)

wb = Workbook()
wb.remove(wb.active)


def sheet(name, title, subtitle, widths):
    ws = wb.create_sheet(name)
    ws.cell(row=1, column=1, value=title).font = TITLE_FONT
    ws.cell(row=2, column=1, value=subtitle).font = Font(italic=True, size=9, color="808080")
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    return ws, 4


def table(ws, r, headers, rows):
    for j, h in enumerate(headers):
        c = ws.cell(row=r, column=1 + j, value=h)
        c.fill = HDR_FILL; c.font = HDR_FONT; c.border = THIN
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    r += 1
    for row in rows:
        for j, v in enumerate(row):
            c = ws.cell(row=r, column=1 + j, value=v)
            c.border = THIN; c.alignment = WRAP
        r += 1
    return r + 1


# ================================================================ 1. OVERVIEW
ws, r = sheet("1_Overview", "KALIKA CRM TOOL — ANALYSIS FOR INTEGRATION INTO KALISOFT AI SALES PIPELINE",
              "Source: D:\\KaliSoftAI\\Kalika-CRM-tool-main | NOT a git repo (single snapshot, no branches — all modules/parts covered) | Analyzed 30-Oct-2026", [26, 46, 60])
r = table(ws, r, ["Area", "Details", "Notes"], [
    ["Project", "Kalika CRM — AI-powered CRM (React 19 + TS + Vite + Tailwind v4 client; FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL server)", "JWT auth; Gemma AI via provider abstraction; IMAP email ingestion"],
    ["Repo layout", "client/ (React src: pages, components, hooks, lib, contexts) · server/ (app: api, crud, models, schemas, services, utils; alembic; seeds; tests) · docs/ (7 design docs) · root md files", "backend.md = 661-line architecture spec; prompt.txt = original POC→MVP vision (GCS/Parquet/vector — largely NOT built)"],
    ["Branches", "No git repository / no branches exist in the snapshot", "Analysis covers every module: client, server, docs, tests, seeds, devops"],
    ["DB", "7 tables, 2 Alembic migrations (001_initial, 002_email_sync); PostgreSQL (no SQLite fallback); UUID PKs; 10 CHECK constraints; 14 indexes", "Seed: user@kalika.com / password123 (4 clients, 5 deals, 4 tasks, 7 timeline events)"],
    ["API", "36 endpoints under /api, JWT-protected (HTTPBearer), CORS localhost:3000/5173", "Health: GET /api/health (public)"],
    ["AI", "Gemma via google-genai SDK; LLMProvider ABC; summary + sentiment; score map (Pos +3/+2, Neu 0/+1, Neg −5/−3, clamped 0–100)", ".env.example LLM_MODEL=gemma-4-26b-a4b-it; config default gemma-3; docs warn gemma-3-12b-it unavailable"],
    ["Tests", "72 pytest unit tests (verified count) + ai_live_test.py manual smoke", "integration_test.py (20 E2E) referenced but MISSING from repo"],
    ["DevOps", "Dockerfile (python:3.12-slim, uvicorn :8000); docker-compose: postgres:15-alpine + api with --reload", "Target: Cloud Run"],
    ["Key defects", "Dead UI (Add Client, Kanban drag, Calendar page static, AI chat shell, composer); syntax artifacts in Tasks.tsx/Calendar.tsx/Login.tsx; camelize mismatch on analytics keys; 'PageLoader' text bug on 3 pages; sidebar hidden below md (no mobile nav)", "These must be fixed/avoided during integration"],
])

# ================================================================ 2. DATABASE
ws, r = sheet("2_Database_Schema", "DATABASE SCHEMA — 7 tables (SQLAlchemy 2.0 + Alembic)",
              "UUID PKs everywhere; FK delete: CASCADE users→owned, clients→deals/timeline; SET NULL clients→tasks/calendar; JSON cols: tags/attachments/attendees", [18, 22, 16, 10, 30, 34])
TABLES = [
    ("users", "Account owners", [
        ("id", "UUID", "PK", "app-side uuid4"), ("name", "String(255)", "not null", ""),
        ("email", "String(255)", "UNIQUE", "login identity"), ("password_hash", "String(255)", "not null", "bcrypt"),
        ("avatar_url", "String(512)", "null", ""), ("created_at/updated_at", "DateTime(tz)", "now()", "auto")],
     "1:N → clients, deals, tasks, timeline_events, calendar_events; 1:1 email_sync_states"),
    ("clients", "CRM companies/accounts", [
        ("id", "UUID", "PK", ""), ("name", "String(255)", "not null", ""), ("logo_url", "String(512)", "null", ""),
        ("industry", "String(255)", "not null", ""), ("relationship_score", "Integer", "default 50", "CHECK 0–100"),
        ("health_score", "Integer", "default 50", "CHECK 0–100; AI-adjusted by sentiment"),
        ("priority", "String(20)", "default Medium", "CHECK Low/Medium/High/Urgent"),
        ("status", "String(20)", "default Active", "CHECK Active/Inactive/At Risk"),
        ("owner_id", "UUID", "FK→users CASCADE", ""), ("last_contact", "DateTime(tz)", "null", ""),
        ("next_follow_up", "DateTime(tz)", "null", ""), ("tags", "JSON", "default []", "string array"),
        ("open_deals_value", "Integer", "default 0", "denormalized SUM of open deals"),
        ("unread_conversations", "Integer", "default 0", ""),
        ("contact_email/phone/website/address", "String", "null", "flattened contact block")],
     "N:1 users; 1:N deals/tasks/timeline/calendar; indexes: owner, status, health, last_contact"),
    ("deals", "Sales pipeline opportunities", [
        ("id", "UUID", "PK", ""), ("title", "String(500)", "not null", ""),
        ("client_id", "UUID", "FK→clients CASCADE", ""), ("value", "Integer", "default 0", "currency as int"),
        ("stage", "String(20)", "default Lead", "CHECK Lead/Qualified/Proposal/Negotiation/Won/Lost"),
        ("expected_close_date", "DateTime(tz)", "not null", ""), ("owner_id", "UUID", "FK→users CASCADE", "")],
     "N:1 clients, N:1 users; 1:N tasks; indexes: client, owner, stage"),
    ("tasks", "To-dos / follow-ups", [
        ("id", "UUID", "PK", ""), ("title", "String(500)", "not null", ""),
        ("client_id", "UUID", "null FK→clients SET NULL", "optional"), ("deal_id", "UUID", "null FK→deals SET NULL", "optional"),
        ("status", "String(20)", "default Todo", "CHECK Todo/In Progress/Done"),
        ("priority", "String(20)", "default Medium", "CHECK Low/Medium/High/Urgent"),
        ("due_date", "DateTime(tz)", "not null", ""), ("owner_id", "UUID", "FK→users CASCADE", "")],
     "indexes: owner, client, status, due_date"),
    ("timeline_events", "Per-client activity stream (email/whatsapp/meeting/call/note...)", [
        ("id", "UUID", "PK", ""), ("client_id", "UUID", "FK→clients CASCADE", ""),
        ("type", "String(30)", "not null", "CHECK email/whatsapp/meeting/call/note/task_completed/deal_stage_change"),
        ("date", "DateTime(tz)", "not null", "event time; DESC index"), ("title", "String(500)", "not null", ""),
        ("description", "Text", "null", ""), ("user_id", "UUID", "FK→users CASCADE", "actor"),
        ("ai_summary", "Text", "null", "LLM-filled"), ("sentiment", "String(20)", "null", "CHECK Positive/Neutral/Negative"),
        ("attachments", "JSON", "default []", "metadata only")],
     "indexes: client, user, type, date DESC"),
    ("calendar_events", "Scheduled meetings/calls", [
        ("id", "UUID", "PK", ""), ("title", "String(500)", "not null", ""), ("description", "Text", "null", ""),
        ("start_time/end_time", "DateTime(tz)", "not null", ""), ("type", "String(20)", "default meeting", "CHECK meeting/call/event"),
        ("client_id", "UUID", "null FK→clients SET NULL", ""), ("attendees", "JSON", "default []", ""),
        ("location", "String(500)", "null", ""), ("meeting_link", "String(512)", "null", ""),
        ("owner_id", "UUID", "FK→users CASCADE", "")],
     "indexes: owner, client, start_time"),
    ("email_sync_states", "Per-user IMAP sync watermarks (migration 002)", [
        ("user_id", "UUID", "PK + FK→users CASCADE", "1:1"), ("last_synced_at", "DateTime(tz)", "null", ""),
        ("last_email_date", "DateTime(tz)", "null", "sync watermark"), ("last_fetched", "Integer", "0", ""),
        ("last_created", "Integer", "0", ""), ("updated_at", "DateTime(tz)", "auto", "")],
     "FK only, no ORM relationship"),
]
for tname, purpose, cols, rels in TABLES:
    ws.cell(row=r, column=1, value=f"TABLE: {tname}").font = SUB_FONT
    ws.cell(row=r, column=2, value=purpose); r += 1
    r = table(ws, r, ["Column", "Type", "Null/Key/Default", "Notes"], cols)
    ws.cell(row=r, column=1, value="Relationships: " + rels).font = Font(italic=True, size=9); r += 2
ws.cell(row=r, column=1, value="ENUMS (String+CHECK): Priority=Low/Medium/High/Urgent · ClientStatus=Active/Inactive/At Risk · DealStage=Lead/Qualified/Proposal/Negotiation/Won/Lost · TaskStatus=Todo/In Progress/Done · TimelineType=email/whatsapp/meeting/call/note/task_completed/deal_stage_change · Sentiment=Positive/Neutral/Negative · CalendarType=meeting/call/event").font = SUB_FONT

# ================================================================ 3. API
ws, r = sheet("3_API_Endpoints", "API ENDPOINT CATALOG — 36 endpoints (all /api, JWT except auth+health)",
              "Auth: bcrypt + python-jose HS256, 24h expiry, payload {sub:user_id}; no refresh tokens; no RBAC", [12, 10, 40, 40, 40])
API = [
    ["Auth", "POST", "/api/auth/register", "Create account (201); duplicate email → 400", "name, email, password → UserResponse"],
    ["Auth", "POST", "/api/auth/login", "Login → JWT bearer", "email, password → access_token"],
    ["Users", "GET", "/api/users/me", "Current profile", "→ UserResponse"],
    ["Users", "PATCH", "/api/users/me", "Update profile (name/email/avatar)", "400 on empty/taken email"],
    ["Clients", "GET", "/api/clients", "List: search, owner_id, status, sort_by/order, limit/offset; items enriched with latest ai_summary + sentiment + activity_count", "→ ClientListResponse{items,total}"],
    ["Clients", "POST", "/api/clients", "Create (name, industry required); owner=current user; contact{} flattened", "201 → ClientResponse"],
    ["Clients", "GET", "/api/clients/{id}", "Detail + AI enrichment", "404 if missing"],
    ["Clients", "PATCH", "/api/clients/{id}", "Partial update incl. scores, next_follow_up, unread", "→ ClientResponse"],
    ["Clients", "DELETE", "/api/clients/{id}", "Delete (cascades deals/timeline)", "204"],
    ["Deals", "GET", "/api/deals", "List: client_id, owner_id, stage filters", "→ DealListResponse"],
    ["Deals", "POST", "/api/deals", "Create; recalcs client.open_deals_value", "title, client_id, value, stage, expected_close_date"],
    ["Deals", "GET", "/api/deals/{id}", "Detail incl. client_name join", ""],
    ["Deals", "PATCH", "/api/deals/{id}", "Update; always recalcs open_deals_value", "title/value/stage/close"],
    ["Deals", "DELETE", "/api/deals/{id}", "Delete + recalc", "204"],
    ["Tasks", "GET", "/api/tasks", "List: owner/client/status filters", ""],
    ["Tasks", "POST", "/api/tasks", "Create (status defaults Todo)", "title, due_date required"],
    ["Tasks", "GET/PATCH/DELETE", "/api/tasks/{id}", "Detail / partial update (status toggle) / delete", ""],
    ["Timeline", "GET", "/api/timeline", "List: client_id, type, user_id; date DESC", "→ events with ai_summary/sentiment"],
    ["Timeline", "POST", "/api/timeline", "Create + BackgroundTask AI processing (summary+sentiment+score updates)", "client_id, type, date, title, description, attachments"],
    ["Timeline", "GET/PATCH/DELETE", "/api/timeline/{id}", "Detail / update / delete", ""],
    ["Calendar", "GET", "/api/calendar/events", "List owner-scoped; month+year filter", "start_time ASC"],
    ["Calendar", "POST", "/api/calendar/events", "Create (type meeting/call/event; attendees[])", ""],
    ["Calendar", "GET/PATCH/DELETE", "/api/calendar/events/{id}", "Detail / update / delete", ""],
    ["Analytics", "GET", "/api/analytics/dashboard", "active_clients, total_open_deals_value, tasks_due_today, total_unread, avg_health_score", "owner-scoped"],
    ["Analytics", "GET", "/api/analytics/revenue-trend?months=7", "SUM of Won deal value per calendar month", "1–24 months"],
    ["Analytics", "GET", "/api/analytics/revenue-forecast", "Per quarter: won (Won) vs projected (all non-Lost)", "current year, unweighted"],
    ["Analytics", "GET", "/api/analytics/communications?days=7", "Per-day email/whatsapp timeline counts", "1–30 days"],
    ["Analytics", "GET", "/api/analytics/pipeline-by-stage", "count + total_value for all 6 stages", ""],
    ["AI", "POST", "/api/ai/process/{event_id}", "Manual AI reprocess: summary, sentiment, health/relationship deltas", "404 unknown event"],
    ["Integrations", "GET", "/api/integrations/status", "email + ai config status from env", ""],
    ["Integrations", "GET", "/api/integrations/email/activity", "pending_ai, is_syncing, watermarks, last 20 sync entries", ""],
    ["Integrations", "POST", "/api/integrations/email/test", "IMAP login + folder test", "400 if unconfigured"],
    ["Integrations", "POST", "/api/integrations/email/fetch?limit=10", "Background IMAP sync (409 if already running)", "per-whitelisted-sender limit"],
    ["Integrations", "GET", "/api/integrations/email/preview?limit=10", "Sync-less fetch preview (from/subject/date/200-char body)", ""],
]
r = table(ws, r, ["Group", "Method", "Path", "Purpose / behavior", "Request → Response / notes"], API)

# ================================================================ 4. UI PAGES
ws, r = sheet("4_UI_Pages", "FRONTEND UI — pages, functionality, defects (React 19 + TS + Tailwind v4 + TanStack Query + Recharts)",
              "Routing: /login public; all else behind ProtectedRoute (localStorage token). API client camelizes responses / snakizes requests. Tailwind responsive via breakpoint classes; sidebar hidden below md (NO mobile nav)", [16, 10, 40, 44, 42])
UI = [
    ["Dashboard", "/", "4 KPI stat cards (active clients, open deals Rs, tasks due, unread) + AreaChart revenue trend (6mo) + static 'AI Insights' panels", "useDashboardStats, useRevenueTrend(6)", "Hardcoded deltas (+2 this week, 8%); AI insights hardcoded; read-only"],
    ["Clients", "/clients", "Server-side search table: avatar+name+industry, status Badge, health/relationship progress bars, open deals Rs, activity count + unread, last contact, AI sentiment badge w/ tooltip; row→profile", "useClients({search,limit:100})", "'Add Client' + Filter + row action buttons DEAD; columns progressively hidden by breakpoint"],
    ["ClientProfile", "/clients/:id", "360° view: score cards, contact details, tags; tabs overview/timeline/emails/whatsapp; vertical timeline with AI summary + sentiment per event; open deals card", "useClient, useTimeline(10s poll), useDeals, useTasks", "tasks fetched but never rendered; whatsapp/deals tabs empty; header action buttons dead"],
    ["Deals", "/deals", "Kanban: 6 stage columns (w-80, scrollable), per-stage count + total footer; deal cards", "useDeals({limit:200})", "NO drag-and-drop (visual only); no click/mutations; 'PageLoader' text bug"],
    ["Tasks", "/tasks", "Filter pills All/Todo/In Progress/Done; row click toggles Todo↔Done; priority badges, due dates, client names", "useTasks, useClients, useUpdateTask", "Syntax artifact line 107 ('</:'); global pending spinner bug; 'PageLoader' text bug"],
    ["Conversations", "/conversations", "2-pane inbox: left = sync controls + status + AI-pending pill + tabs (all/email/whatsapp) + event list; right = client header, AI summary card, full message, reply composer", "useTimeline(10s), useClients, useIntegrationStatus, useEmailActivity(adaptive 1.5s/8s), useFetchEmails", "Search box not wired; Reply/Open Original/Suggest Reply/Send all DEAD"],
    ["Calendar", "/calendar", "Month grid 7×5 with hardcoded events; 'Upcoming Today' sidebar", "useUser only", "ENTIRELY STATIC — doesn't call useCalendarEvents despite hooks existing; corrupted JSX line 106; pager/New Event dead"],
    ["Analytics", "/analytics", "4 KPI cards; AreaChart forecast (won vs projected, quarterly); BarChart comms heatmap (stacked email+whatsapp, 7 days); pipeline-by-stage tile grid", "useDashboardStats, useRevenueForecast, useCommunications(7), usePipelineByStage", "camelize mismatch: snake_case keys vs camelized responses → masked by ||0 fallbacks"],
    ["AIAssistant", "/ai", "Chat shell: welcome bubble, 4 suggested prompts, input row; 'Automated Insights' sidebar cards", "useUser only", "FULLY STATIC — no backend/AI calls; @google/genai unused in src"],
    ["Settings", "/settings", "Profile edit (functional save); communication channels; sync preferences", "useUser, useUpdateUser", "Channels/sync controls hardcoded/dead; fake 500ms save delay"],
    ["Login", "/login", "Centered card, email+password, error banner, demo creds footer", "api.post /auth/login → localStorage token", "Corrupted class attr line 83 (build-breaking)"],
    ["Layout", "—", "AppLayout (Sidebar w-60 + Topbar h-16 + main), shadcn-style UI primitives (Avatar/Badge/Button/Card/Input/Spinner/Tabs self-built)", "contexts/UserContext", "Topbar search/bell/New Entry dead; sidebar hidden <md with no mobile fallback"],
]
r = table(ws, r, ["Page", "Route", "UI functionality", "Hooks / API calls", "Defects / dead parts"], UI)
ws.cell(row=r, column=1, value="Hooks: useCurrentUser, useClients/useClient(+CRUD), useDeals(+CRUD), useTasks(+CRUD), useTimeline(+CRUD, polling), useCalendar*(defined, unused by page), useDashboardStats, useRevenueTrend/Forecast, useCommunications, usePipelineByStage, useIntegrationStatus, useEmailActivity, useFetchEmails — invalidation per entity query keys; global staleTime 5min, retry 1.").font = SUB_FONT

# ================================================================ 5. AI & EMAIL
ws, r = sheet("5_AI_Email_Analytics", "AI SERVICE, EMAIL/IMAP INGESTION & ANALYTICS LOGIC",
              "Provider abstraction: LLMProvider ABC → GemmaProvider (google-genai SDK); singleton ai_service; background processing via FastAPI BackgroundTasks / daemon threads", [24, 58, 58])
r = table(ws, r, ["Area", "Logic / flow", "Details"], [
    ["AI processing", "process_timeline_event(event_id): analyze(title+description) → write ai_summary + sentiment → adjust client scores", "Triggers: POST /timeline BackgroundTask; email ingestion daemon thread; manual POST /ai/process/{id}"],
    ["Score map", "Positive: health +3, relationship +2 · Neutral: +0/+1 · Negative: −5/−3 · clamped 0–100", "Hardcoded SENTIMENT_SCORE_MAP (comment says configurable)"],
    ["Gemma prompts", "Summary: 'Summarize CRM communication in 1-2 sentences, key points/decisions/next steps' (temp 0.3, 500 tok) · Sentiment: one-word positive/neutral/negative (temp 0.1, 200 tok)", "Skips 'thought' parts (thinking models); failure fallbacks: 'Summary generation failed' / 'neutral'"],
    ["Email fetch", "IMAP4_SSL login → per whitelisted sender search FROM+SINCE (or UNSEEN) → last N IDs → RFC822 parse; fresh connection per operation", "Env: IMAP_HOST/PORT/USER/PASSWORD/USE_SSL + EMAIL_SENDER_WHITELIST"],
    ["Email→client match", "1) exact contact_email ILIKE → 2) domain match → 3) from_name substring vs client.name", "First hit wins; unmatched emails skipped"],
    ["Timeline creation", "type=email, title=subject, description=From/To/CC+body, attachment metadata only; dedup: same client+subject within 60s", "Then AI on daemon thread"],
    ["Sync state", "email_sync_states per user: last_email_date watermark; day-granular IMAP SINCE post-filtered precisely; state persisted only on error-free runs", "409 on concurrent sync (in-memory set); activity ring buffer 20/user"],
    ["Analytics formulas", "dashboard: active clients, SUM(open deals value), tasks due today, unread sum, AVG health · revenue-trend: Won SUM per month · forecast: per-quarter won vs all-non-Lost projected · communications: per-day email/whatsapp counts · pipeline: count+SUM per stage", "All owner-scoped, on-demand (no precompute); forecast NOT probability-weighted"],
])

# ================================================================ 6. TESTS & DEVOPS
ws, r = sheet("6_Tests_DevOps", "TESTS (72 unit) + DEVOPS + CONFIG",
              "integration_test.py (20 E2E) referenced in README/docs but MISSING from repo; ai_live_test.py = manual live-server AI smoke", [30, 60, 50])
r = table(ws, r, ["Item", "Content", "Notes"], [
    ["Unit tests (72)", "auth 6 · clients 7 · deals 6 · tasks 6 · timeline 9 · calendar 9 · analytics 6 · ai_service 5 · email_ingestion 18", "SQLite test.db + dependency override; MockLLMProvider; conftest registers test@example.com"],
    ["ai_live_test.py", "login → first client → POST timeline (positive email) → sleep 8s → verify ai_summary/sentiment → verify client scores → manual reprocess", "Needs running server + GOOGLE_AI_API_KEY"],
    ["Dockerfile", "python:3.12-slim, pip install requirements, uvicorn app.main:app :8000", "single-stage"],
    ["docker-compose", "db: postgres:15-alpine (kalika/kalika, kalika_crm, :5432, pgdata volume, pg_isready) + api (build ., :8000, --reload, bind mount)", "dev mode"],
    ["requirements.txt", "fastapi 0.115 · uvicorn 0.30.6 · sqlalchemy 2.0.35 · alembic 1.13.2 · psycopg2-binary 2.9.9 · pydantic 2.9.2[email] · pydantic-settings 2.5.2 · python-jose 3.3.0 · bcrypt 5.0.0 · python-multipart · httpx · pytest 8.3.3 · pytest-asyncio · google-genai 1.7.0", ""],
    ["Env vars", "DATABASE_URL · SECRET_KEY · ALGORITHM=HS256 · ACCESS_TOKEN_EXPIRE_MINUTES=1440 · GOOGLE_AI_API_KEY · LLM_MODEL · IMAP_HOST/PORT/USER/PASSWORD · (config-only: IMAP_USE_SSL, EMAIL_SENDER_WHITELIST)", "docs/07 future: GCP_PROJECT_ID, GCS_BUCKET, BIGQUERY_DATASET"],
    ["docs/ (7 files)", "01 architecture · 02 database schema · 03 api spec · 04 implementation plan (8 phases) · 05 progress (phases 1–4) · 06 remaining tasks (phases 1–7 done, deploy guide) · 07 GCP BigQuery migration roadmap (hybrid PG+BigQuery+GCS Parquet, dataset kalika_crm, CRON 6PM IST)", "crmdetails.txt: 'show instor india and ozori data to show ok conversation flow'"],
    ["prompt.txt vision (not built)", "GCS buckets data sources, guardrails, Redis, Parquet intermediates, vector DB as pickles in GCS, SSO, CRON CI/CD", "backend.md explicitly avoided: LangChain, vector DBs, Redis, Celery, microservices, CQRS"],
])

# ================================================================ 7. INTEGRATION MAP
ws, r = sheet("7_Integration_Map", "INTEGRATION MAP — Kalika CRM → Kalisoft AI Sales Pipeline (current app)",
              "Current app: sales_fastapi (kalisoft-sales, /api) + sales_pipeline.db (SQLite dev) | Priority: P1=high value/low effort, P2=medium, P3=later", [22, 34, 34, 40, 10])
r = table(ws, r, ["CRM module", "CRM capability", "Current app equivalent", "Integration action", "Priority"], [
    ["clients table", "CRM accounts with health/relationship scores, priority, status, tags, contact block, next_follow_up", "contacts table (company, intent, domain, notes, tags)", "ADD scores/status/next_follow_up columns to contacts (Alembic migration); map CRM clients ← contacts by email/domain; keep contact model as superset (has purchase_* fields)", "P1"],
    ["timeline_events", "Per-client activity stream with type/email/whatsapp + ai_summary + sentiment + attachments", "whatsapp_messages (flat queue only); events module messages", "ADOPT: new timeline_events table linked to contacts; auto-create entries from whatsapp queue sends + email fetches; port the 60s dedup rule", "P1"],
    ["ai_service + GemmaProvider", "Summary + sentiment per event → health/relationship score deltas (Pos +3/+2, Neg −5/−3)", "gemma_service.py (personalization chain gemma-3-27b→12b→gemini-flash) + llm router (guardrailed /api/llm/run)", "PORT provider pattern as new LLM task 'summarize_sentiment' in llm/tasks.py; reuse existing model chain; write scores onto contacts", "P1"],
    ["deals (Kanban)", "Deal pipeline Lead→…→Won/Lost with open_deals_value denormalized on client", "none (campaigns ≠ deals)", "ADOPT: new deals table + /api/deals CRUD; Kanban UI page; sync Won deals to sales-register context", "P2"],
    ["tasks", "Todo/In Progress/Done with priority + due dates, client/deal links", "scheduler module (jobs only), no user tasks", "ADOPT: tasks table + /api/tasks; surface follow-up tasks from pipeline actions (call-later → task with due date)", "P2"],
    ["analytics_service", "dashboard stats, revenue trend, forecast, comms heatmap, pipeline-by-stage", "kpi router (overview/pipeline/outreach/costs/website)", "MERGE: add CRM KPIs as /api/kpi/crm/* endpoints; reuse owner-scoped SQL patterns; add Recharts to current React UI or port charts", "P2"],
    ["email_service (IMAP ingestion)", "Whitelist fetch → parse → match client (email/domain/name) → timeline + AI", "email router (connections, fetch, inbox) + extractor (Gemini entity extraction)", "MERGE: keep current email connections; ADD CRM matcher + timeline creation + sync-state watermark table; reuse extractor for PO detection", "P2"],
    ["calendar_events", "Meeting/call scheduling with client link + attendees", "events module (expo messaging, different purpose)", "ADOPT as new table (rename current events→event_campaigns if confusing); month filter API pattern is reusable", "P3"],
    ["ClientProfile page", "360° client view with tabbed timeline + AI summaries", "current UI has flat contact rows only", "PORT page concept into current React app (new ContactProfile view) using existing panel/table CSS; wire to /api/contacts/{id} + timeline", "P1"],
    ["Conversations page", "2-pane inbox with sync status + AI summaries + adaptive polling", "current UI: none (email fetch is utilitarian)", "PORT layout; wire to current /api/email/* + new timeline endpoints; keep adaptive polling pattern (1.5s/8s)", "P2"],
    ["Deals Kanban UI", "6-column stage board", "none", "PORT but implement real drag-drop (CRM version is visual-only) or stage dropdown", "P2"],
    ["Auth (JWT+bcrypt register/login)", "Local email/password accounts", "Google OAuth + dev-mode tokens", "KEEP current Google auth; optionally add local login from CRM for non-Google users (auth router already consolidated)", "P3"],
    ["Calendar page", "Month grid", "none", "SKIP CRM version (static/broken); rebuild from calendar_events API if needed", "P3"],
    ["AIAssistant page", "Chat copilot shell", "none (llm router exists)", "SKIP for now (CRM version is static shell); revisit with llm tasks later", "P3"],
    ["BigQuery roadmap (docs/07)", "PG→BigQuery analytics sync, GCS Parquet", "GCS reports already used; analysis.py patterns exist", "REFERENCE when scaling analytics; align dataset name kalika_crm", "P3"],
    ["Defects to NOT port", "Dead buttons, static Calendar/AIAssistant, camelize mismatch, 'PageLoader' text bug, syntax artifacts, missing mobile nav", "current UI already has mobile nav + toasts", "Avoid during port; current app's UX patterns (mobile sidebar, toast notices) take precedence", "P1"],
])

wb.save(OUT)
print("Saved:", OUT)

creds, _ = google.auth.default()
client = storage.Client(credentials=creds)
bucket = client.bucket("kalika_enterprises")
blob = bucket.blob(GCS_DEST)
blob.upload_from_filename(OUT)
print(f"Pushed to gs://kalika_enterprises/{GCS_DEST} ({os.path.getsize(OUT)} bytes)")
