# Kalisoft AI Sales Pipeline — Application Guide

**Kya hai ye app?** Kalika Enterprises + Kalisoft AI ka ek private sales workspace.
Isme customer contacts, email/WhatsApp outreach, field visit tracking, voice notes,
ERP dispatch/orders, Tally sales, daily rate calculator, events, AI assistant — sab
ek hi dashboard ke andar hai.

- **Production URL:** https://kalisoft-sales-19782268668.asia-south1.run.app
- **Tech:** React frontend + FastAPI backend (`/api/*`) + PostgreSQL (Cloud SQL) + GCS
- **Login:** Google Sign-In (sirf allowed emails) ya username+password (agar users banaye gaye ho)

---

## Login kaise karein

| Tarika | Kab kaam karta hai | Kaise |
|---|---|---|
| **Google Sign-In** | Jab server pe `GOOGLE_CLIENT_ID` configured ho | Login page pe "Sign in with Google" button — sirf allow-listed emails (`GOOGLE_ALLOWED_EMAILS`) |
| **Username + Password** | Jab admin ne user banaya ho | Login page ka "Kalika username & password" form. Email ya plain username dono chalte hain (e.g. `kalika` → `kalika@kalika.local`) |
| **Dev login** | Sirf jab `AUTH_DEV_MODE=true` ho (local dev) | "Local development access" box me email daalo |

> Session short-lived token se hota hai (default 60 min). Token expire → app khud login page pe bhej deta hai.

---

## Navigation — konse group me kaunsa tab

Sidebar 4 groups me divided hai:

| Group | Tabs |
|---|---|
| **KALIKA DAILY** | Dashboard · Mail desk · Company history · Catalogue & rates · Field desk · Sales analytics & BI · ERP & forecast |
| **OUTREACH** | Contacts · Marketing companies · Events · Signal desk · Outreach · Scheduler · Email connections |
| **FEEDBACK** | Feedback · Feedback pipeline |
| **INSIGHTS & ADMIN** | Pipeline overview · Business KPIs · Social & AI · Access · UAT & ops · Recent changes |

> Note: Sabhi signed-in users ko saare tabs dikhte hain. Admin-only kaam (user management,
> ERP sync, Tally upload, guardrail checks) server-side 403 se blocked hota hai.

---

# Tab-by-Tab Guide

## 1. Dashboard (`dash`) — "Kalika command center"

Roz ka main screen. Har 60 second me auto-refresh hota hai.

**Dikhta kya hai:**
- Live strip: time, env badge (DEV/UAT/PROD), last ERP sync, companies/orders count
- Metrics: API endpoints live, GCP services healthy, Dispatch completion %, Orders value (₹), Voice transcripts (analysed/pending), Outreach queued
- Tally Sales panel (compact) — period-wise sales value, top buyers
- Top companies by dispatched qty (share bars ke saath)
- "Daily actions" — AI recommendations
- Social daily metrics: YouTube views, LinkedIn profiles, Reddit posts, 6-month order forecast
- Platform service health (GCP services)
- Team chat thread + "Voice · recent field audio"

**API:** `GET /api/dashboard/summary`, `GET/POST /api/team/messages`

**Kaise use karein:**
1. Subah dashboard kholo → Daily actions dekho.
2. Team chat box me message likho → team ko dikhega.
3. "Field desk" / "Rate calculator" shortcut buttons se direct jump.

---

## 2. Mail desk (`instore`) — "InstoreMails"

Mailbox ka snapshot → insights. Kalika ke instore emails ka analysis.

**Dikhta kya hai:**
- Metrics: mails linked/unlinked, missing links, attachments, link accuracy % + next-month forecast
- "Latest mail" table — expandable rows (client, sender, intent, outcome, attachments, entity chips)
- "Ask the mail desk" — AI chat: expertise select karo, model chuno, question poocho

**API:** `GET /instore/summary`, `GET /instore/mails`, `GET /instore/prompts`, `POST /instore/sync`, `POST /instore/ask`

**Kaise use karein:**
1. "Sync" dabao → latest mailbox + interaction dump GCS/local snapshot me aata hai.
2. Table me mail pe click karo → full context khulta hai.
3. Right panel me question likho (e.g. "is client se next kya karna hai?") → AI reply milta hai (Gemma → local SLM → flash fallback chain).

---

## 3. Company history (`visits`) — "CompanyVisits"

Field visits ka register. Har company visit ka record + photo/video proof.

**Dikhta kya hai:**
- Metrics: total visits, this month, follow-ups, attachments
- "New visit" form: company*, contact, phone, date, outcome, follow-up date, person met, location, Google Maps link, previous discussion, notes, next action
- "Visit history" table: date, outcome, follow-up, media count

**API:** `GET /visits`, `GET /visits/stats`, `POST /visits`, `POST /visits/samples`, `POST /visits/{id}/media`

**Kaise use karein:**
1. Visit ke baad "New visit" form bharo → Save.
2. Photo/video upload karo (GCS me store hota hai).
3. Follow-up message **Copy** karo ya **WhatsApp** button se direct wa.me link kholo (10-digit number pe auto +91).
4. "Sync samples" se demo field visits load ho jaate hain.

---

## 4. Catalogue & rates (`catalog`) — "Catalogue"

Product master + daily rate approval + quote calculator.

**Dikhta kya hai:**
- Metrics: products, pending rates, approved rates
- "Product master" — naya product add (name/code/category/unit/description)
- "Submit a rate" — daily rate approval ke liye bhejo (product, rate ₹, effective date, notes)
- "Approval queue" — pending rates approve/reject karo
- "Quote calculator" — film costing (micron, width, length, waste %, conversion cost, margin %) → price, cost stack, price/kg

**API:** `GET /catalog/products`, `GET /catalog/summary`, `GET /catalog/rate-today`, `POST /catalog/products`, `POST /catalog/rates`, `POST /catalog/rates/{id}/review`, `POST /catalog/quote`

**Kaise use karein:**
1. Roz ka rate submit karo → approval queue me jaata hai.
2. Admin/senior approve ya reject kare.
3. Customer ko quote dena ho → calculator me values daalo → instant price.

---

## 5. Field desk (`field`) — "FieldDesk"

Field executives ke liye: voice note → text → approval.

**Dikhta kya hai:**
- Voice recorder (browser SpeechRecognition, `en-IN`) — bolke likhao ya type karo
- "Review queue" — pending field updates (author, body, 🎙 transcript)
- "Team feed" — approved/rejected updates
- Tally Sales panel (compact)

**API:** `GET/POST /team/messages`, `POST /team/messages/{id}/review`

**Kaise use karein:**
1. Mic dabao → visit summary bolo → transcript edit karo → **Send for approval**.
2. Senior/admin review queue me **Approve** ya **Reject** kare.
   (Field executive server-side approve nahi kar sakta.)
3. SpeechRecognition na chale to manual typing allowed.

---

## 6. Sales analytics & BI (`salesbi`) — "SalesBi"

Real ERP data pe sales intelligence.

**Dikhta kya hai:**
- Metrics: Orders, Orders value, Dispatched, Completion %
- "Company mix" table (company-wise orders/value/completion bar)
- "Delivery / Plant view" — plant-wise completion + pending dispatch rows
- Full Tally Sales panel (period switch + latest invoice lines)

**API:** `GET /sales/overview`, `GET /sales/companies`, `GET /sales/delivery`, `GET /sales/export?dataset=companies&format=xlsx|pdf`

**Kaise use karein:**
1. Refresh se latest ERP numbers.
2. **XLSX/PDF export** download karo.
3. Tally panel me period badlo (admin: Sync GCS / Upload XLS).

---

## 7. ERP & forecast (`erp`) — "ErpDashboard"

ERP dispatch/orders + forecast + rate calculator + YouTube channel sync.

**Dikhta kya hai:**
- KPI strip: Orders value (₹L), Dispatch completion %, Pending follow-ups, Customers served
- Funnel strip: Orders → Value → Scheduled qty → Dispatched qty
- Forecast panel: monthly bars + next-month projection, top customers
- "Channel sync · YouTube" (admin: API key + channel ID save, Sync now)
- **Daily rate calculator**: polymer rate, density, micron, width, length, waste %, conversion ₹/kg, margin % → quote price + cost stack + formula explainer + official XLSX sheet link
- Dispatch table (status filter ke saath)

**API:** `GET /erp/status`, `GET /erp/analytics`, `GET /erp/dispatch?status=`, `GET /erp/forecast?months=6`, `GET /erp/youtube/status`, `POST /erp/sync` (admin), `PUT /erp/settings` (admin), `POST /erp/youtube/sync` (admin), `POST /erp/rate-calculator`

**Kaise use karein:**
1. Dispatch table me status filter lagao (pending etc.).
2. Rate calculator kholo (state browser me saved rehta hai) → "Calculate & verify" se server cross-check.
3. Admin: "Sync ERP now" se GCS report pull; YouTube keys save karke channel stats sync.

---

## 8. Contacts (`contacts`)

CRM — har relationship yahin.

**Dikhta kya hai:**
- GCS prefix sync bar, mini-stats (total/domains/intents)
- "Capture a contact" form: email*, name, company, phone, intent (auto-classify bhi), context
- Searchable table (name/company/email, signal tag, source, delete)

**API:** `GET /contacts?q=`, `GET /contacts/stats`, `POST /contacts`, `DELETE /contacts/{id}`, `POST /contacts/upload` (CSV/XLSX/XLS/VCF/JSON), `POST /contacts/import/gcs`

**Kaise use karein:**
1. **Upload files** — multiple CSV/Excel/VCF/JSON ek saath.
2. **Import GCS** — bucket se sync (prefix daalke "Sync GCS path").
3. Intent auto-classify hota hai; manual select bhi kar sakte ho.

---

## 9. Marketing companies (`marketing`)

Kalika marketing workbook ka live view.

**Dikhta kya hai:** stats (total, with phone/email/requirements), search + category + call-status filters, table with inline editable **Requirements** column.

**API:** `GET /marketing-companies?q=&category=&call_status=`, `GET /marketing-companies/stats`, `PATCH /marketing-companies/{id}`, `POST /marketing-companies/import`

**Kaise use karein:** search/filter karo; Requirements cell me likhke blur karo → auto-save; "Import" se workbook re-import.

---

## 10. Events (`events`)

Event workbook → WhatsApp invites scheduling.

**Dikhta kya hai:**
- Metrics: events tracked, next 30 days, recipients, queued messages
- Event list (filters: search, upcoming/past/unscheduled, in_person/online/hybrid)
- Right panel: event facts → STEP 1 recipient picker → STEP 2 template (variables `{{name}} {{company}} {{event_title}} {{event_dates}} {{where_lines}}`) → preview → schedule time (UTC) → Queue
- "Outreach queue" table: Send/Cancel per message, "Send due now"

**API:** `GET /events/summary`, `GET /events`, `GET /events/recipients`, `POST /events/import` (xlsx), `GET /events/{id}/message-template`, `POST /events/{id}/schedule`, `POST /events/messages/{id}/send|cancel`, `POST /events/messages/send-due`

**Kaise use karein:**
1. Workbook upload karo ya "Load local workbook".
2. Event select karo → recipients tick karo → template edit karo → preview → time set → **Queue**.
3. Queued messages **kabhi auto-send nahi hote** — due hone pe manually Send dabao.

---

## 11. Signal desk (`signals`)

Market intelligence one-click scans. Raw JSON output panel me result.

**Actions:** LinkedIn hiring search · Reddit hiring search · YouTube signal scan · Run cron sweep

**API:** `POST /social/linkedin/search`, `POST /social/reddit/search`, `POST /social/youtube/search`, `POST /scheduler/run`

---

## 12. Outreach (`outreach`)

Templates → AI-personalised bulk campaigns → human review → send. **Kuch bhi bina approval ke send nahi hota.**

**Kaise use karein:**
1. Template chuno (ya "Seed defaults" se 12 Kalisoft templates banao).
2. "Build a campaign": name, channel (email/whatsapp/linkedin/wechat), strategy (cold_outreach/follow_up/nurture), intent filter, contact limit → **Generate for review** (Gemma se personalise).
3. "Review & send": messages padho → **Approve all** → **Send approved**.
4. Campaign history se purane campaigns reopen.

**API:** `GET /templates`, `GET /templates/meta`, `POST /templates/seed`, `POST /campaigns`, `GET /campaigns/{id}`, `POST /campaigns/{id}/approve`, `POST /campaigns/{id}/send`

---

## 13. Scheduler (`scheduler`)

Background cron tasks ka control room.

**Dikhta kya hai:** registered recurring tasks (name, cron), queue status (scheduler running, backend redis/in-memory, queued count).

**API:** `GET /scheduler/status`, `GET /scheduler/tasks`, `POST /scheduler/run` (SMTP email notification ke saath), `POST /scheduler/clear`

**Kaise use karein:** "Run now" = saare tasks queue; "Clear queue" = apna queue saaf.

---

## 14. Email connections (`email`)

IMAP/SMTP mailboxes + Gmail OAuth + read-only mail fetch.

**Kaise use karein:**
1. "Add IMAP mailbox": email + **App Password** (normal Gmail password nahi!) + hosts/ports → encrypted store hota hai.
2. Ya "Connect Gmail with OAuth" (tabhi jab server pe configured ho).
3. Source select karo → "Test IMAP / SMTP".
4. Fetch inspector: search/sender/intent/date filters, limit ≤50, unread-only → **Fetch context** → message cards dekho (full body optional).

**API:** `GET/POST /email/connections`, `POST /email/connections/{id}/test`, `POST /email/connections/{id}/fetch`, `GET /email/google/mailboxes`, `GET /email/google/authorize`, `POST /email/google/mailboxes/{id}/fetch`

---

## 15. Feedback (`feedback`)

App ke baare me feedback do. Category (general/bug/feature/ux) + 1–5 star + message → history list (mailed/saved status ke saath).

**API:** `POST /feedback`, `GET /feedback`

---

## 16. Feedback pipeline (`pipeline`)

Segments se personalised WhatsApp follow-ups.

**Kaise use karein:**
1. Segment card chuno (audience count dikhta hai).
2. Template + row limit (10–200) → **Personalise & preview** → table me message + context (order no/amount/status).
3. Har row pe "Open WhatsApp" (wa.me manual send) ya **Queue all with phone** se bulk queue.

**API:** `GET /pipeline/segments`, `GET /pipeline/templates?segment=`, `POST /pipeline/preview`, `POST /pipeline/queue`

---

## 17. Pipeline overview (`overview`)

Simple home view: total contacts, ready-to-reach, API status, latest contacts, connected services (DB/GCS/Google Sign-In), security guardrails, "How it works" strip.

**API:** `GET /contacts/stats`, `GET /contacts`, `GET /health`, `GET /security/status`

---

## 18. Business KPIs (`kpis`)

Read-only analytics: total contacts (+7d), signals captured, messages sent + delivery rate, AI spend ($), contacts-by-intent funnel, campaigns-by-status, **GA4 website traffic** (active users, engagement, top pages, sources, top city).

**API:** `GET /kpi/overview`, `GET /kpi/pipeline`, `GET /kpi/outreach`, `GET /kpi/costs`, `GET /kpi/website`

---

## 19. Social & AI (`socialai`)

**Dikhta kya hai:** recommendation engine status, "Next best actions" list, social channels status (Instagram/YouTube/LinkedIn/Reddit/WhatsApp) + recent Instagram media, communication mix, voice/tone sentiment breakdown.

**API:** `GET /social/overview`, `GET /ai/recommendations`, `GET /ai/communication-analytics`, `GET /ai/status`, `POST /social/instagram/sync`

---

## 20. Access (`access`) — **Admin only**

User management. Non-admin ko sirf warning banner dikhta hai (server 403).

**Kaise use karein (admin):**
1. "Create a user": email/username, name, temporary password (min 8), role (sales/field/admin).
2. Table me inline role change, Activate/Deactivate (apna account deactivate nahi kar sakte; last admin remove nahi ho sakta).
3. Per-user activity counts (contacts/visits/voice) + last login.

**API:** `GET /users/detail`, `GET /users/activity`, `POST /users`, `PATCH /users/{id}`

---

## 21. UAT & ops (`uat`) — mostly Admin

**Dikhta kya hai:** UAT days-left, rollout progress, feature flags, model catalog (provider/tier/cost/PII), prompt samples + human review queue, guardrail checks table, customer journey stories, logs (sync runs, model usage, audit).

**Kaise use karein:**
- Admin: "Run guardrail checks", prompt reviews approve/reject, "Daily rate chat" copilot.
- Sab: models/prompts/stories/logs dekh sakte hain.

**API:** `GET /ops/uat`, `GET /ops/models`, `GET /ops/prompt-samples`, `POST /ops/run-checks`, `GET/POST /ops/prompt-reviews`, `POST /ops/chat`, `GET /journey/stories`, `GET /ops/logs`

---

## 22. Recent changes (`changelog`)

Static "what changed" list — recent feature updates ka summary. Koi API nahi.

---

# Kalika AI Assistant (har tab pe available)

Topbar ka "Kalika AI" button ya bottom-right FAB se khulta hai (right drawer).

- Model select (default pehle; availability marked) — Gemma local SLM → cloud fallback
- 4 one-tap prompt chips (rate review, film calculation, etc.)
- Chat thread: model · latency · fallback notice ke saath
- Image attach (<2 MB, sirf metadata bheja jaata hai), Enter = send, Shift+Enter = newline, Esc = close, "Clear" history

**API:** `GET /ops/models`, `POST /ops/chat`

---

# Roles & Permissions

| Role | Kya kar sakta hai |
|---|---|
| **admin** | Sab kuch + user management, ERP sync, Tally sync/upload, guardrail checks, YouTube settings |
| **sales** | Dashboard, catalogue approval, team review, reports — admin actions blocked |
| **field** | Field updates, visits, voice capture — approvals nahi kar sakta (server-side block) |

Admin rights do sources se aate hain: `ADMIN_EMAILS` env (default `ai.solutions@kalisoftai.in`)
ya user ka `role="admin"`. Frontend pe tabs sabko dikhte hain; enforcement server pe hoti hai.

---

# Common Workflows

## Roz ka routine (sales/admin)
1. **Dashboard** → daily actions + dispatch/orders dekho.
2. **Mail desk** → sync + AI se next actions poochho.
3. **Catalogue & rates** → aaj ka rate submit/approve karo.
4. **Field desk** → team ke updates approve karo.
5. **Social & AI** → next best actions check karo.

## Field executive routine
1. **Company history** → visit log + photo upload.
2. **Field desk** → voice note record → Send for approval.
3. **Catalogue & rates** → quote calculator se on-spot price.

## Outreach campaign bhejni ho
1. **Contacts** me data upload/import.
2. **Outreach** → template → campaign generate → review → approve → send.
3. **Events** se WhatsApp invites schedule (manual send due).
4. **Business KPIs** me delivery rate track karo.

---

# Troubleshooting

| Problem | Check |
|---|---|
| Login nahi ho raha | Server pe Google OAuth configured hai ya nahi (`/api/config`); password user bana hai ya nahi (Access tab) |
| "Admin access required" | Tumhara email `ADMIN_EMAILS` me nahi ya role admin nahi hai |
| Mailbox connect fail | Gmail **App Password** use karo (16-char), normal password nahi |
| Upload fail | Sirf CSV/XLSX/XLS/VCF/JSON; size limit `MAX_REQUEST_BYTES` (1MB default) |
| Voice record nahi chal raha | Browser SpeechRecognition support (Chrome best); nahi to type karo |
| Redis unavailable | Scheduler in-memory fallback pe chalta hai — warning theek hai |
| Session baar-baar khatam | Token 60 min me expire hota hai; dobara login karo |
