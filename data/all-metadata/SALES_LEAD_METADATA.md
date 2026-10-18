# ╔══════════════════════════════════════════════════════════════════════════════════╗
# ║           KALIKA ENTERPRISES × KALISOFTAI — SALES LEAD METADATA                 ║
# ║              AI-Powered Sales Pipeline · System Architecture                    ║
# ╚══════════════════════════════════════════════════════════════════════════════════╝
#
#   Project  : gen-lang-client-0132243782       Region : asia-south1 (Mumbai)
#   Branch   : sales-gcp-migration @ d081461    Service: kalisoft-sales (Cloud Run)
#   Author   : KalisoftAI Engineering           Date   : 2026-10-18
#
# ─────────────────────────────────────────────────────────────────────────────────

---

## TABLE OF CONTENTS

```
  §  1. Executive Summary & Mission
  §  2. Purpose / Intent of Sales Lead
  §  3. System Architecture (Senior Architect View)
  §  4. Data Flow Diagrams (ASCII)
  §  5. Prompts Templates
  §  6. GCS Bucket Map & Data Inventory
  §  7. Input Data Sources
  §  8. Cron Jobs / Scheduled Tasks
  §  9. Cloud Functions
  § 10. Regional Strategy Matrix
  § 11. Sales & Marketing Strategies
  § 12. Seasonal Personalization Framework
  § 13. Funnel Architecture
  § 14. KPI Dashboard (ASCII Visual)
  § 15. Pipeline Dashboard (ASCII Visual)
  § 16. Regional Dashboard (ASCII Visual)
  § 17. AI Cost Dashboard (ASCII Visual)
  § 18. Campaign Dashboard (ASCII Visual)
  § 19. KPIs — Master Table
  § 20. Integration Status
  § 21. Growth Roadmap
  § 22. Oct-Roadmap Data Pipeline (NEW)
  § 23. Client Data Routing — Kalika vs AG-Vision (NEW)
  § 24. GCS Upload Log (NEW)
```

---

## § 1. EXECUTIVE SUMMARY & MISSION

```
  ╭──────────────────────────────────────────────────────────────────────╮
  │                                                                      │
  │   MISSION: Transform Kalika Enterprises from a regional             │
  │   manufacturing business into an AI-driven, globally-reachable      │
  │   sales powerhouse — automating 80% of the sales pipeline           │
  │   while keeping humans in control of strategy and relationships.    │
  │                                                                      │
  │   VISION: Every lead receives a personalized, season-aware,         │
  │   region-optimized quote within 2 hours — powered by AI,            │
  │   governed by SOPs, delivered via preferred channel.                │
  │                                                                      │
  ╰──────────────────────────────────────────────────────────────────────╯

  CURRENT STATE                    FUTURE STATE (Q1 2027)
  ──────────────                   ──────────────────────
  ✗ Manual quote generation        ✓ AI-personalized quotes in <2 min
  ✗ Spreadsheet-based CRM          ✓ Cloud SQL + GCS unified store
  ✗ No regional targeting          ✓ 5-region demographic campaigns
  ✗ Reactive sales                 ✓ Predictive reorder engine
  ✗ Single-channel (email)         ✓ Multi-channel (WhatsApp+Email+LinkedIn+YouTube)
  ✗ No seasonal intelligence       ✓ Pre/peak/post auto-campaigns
  ✗ Static pricing                 ✓ Real-time commodity dashboard
```

---

## § 2. PURPOSE / INTENT OF SALES LEAD

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │                    BUSINESS EXPANSION MAP                           │
  │                                                                     │
  │                        ★ GLOBAL                                    │
  │                       ╱    ╲                                       │
  │                 ┌────╱──┐  ╲────┐                                  │
  │                 │ US ★  │  │ DE ★│  ← International (via GA data)  │
  │                 │124usr │  │ 3usr │                                │
  │                 └───┬───┘  └──┬───┘                                │
  │                     │    ╔════╧════╗                               │
  │                     │    ║SINGAPORE║ ← Highest engagement (66.7%)  │
  │                     │    ║  3 usr  ║                               │
  │                     │    ╚════╤════╝                               │
  │                 ┌───┴─────────┴───┐                                │
  │                 │    INDIA ★★     │ ← Core market                  │
  │                 │  ┌────┬────┐    │                                │
  │                 │  │SOUTH│NORTH│   │                                │
  │                 │  │Hyd  │ TBD │   │                                │
  │                 │  │Pune │     │   │                                │
  │                 │  └────┴────┘    │                                │
  │                 └─────────────────┘                                │
  └─────────────────────────────────────────────────────────────────────┘
```

| Dimension | Detail |
|---|---|
| **Primary Goal** | Grow across India (South + North) and international markets (US, Germany, Singapore) |
| **Target Regions** | India (Hyderabad, Pune), US (Ashburn, San Jose, Des Moines, LA, NY, SF), Germany (Gutersloh), Singapore |
| **Audience** | B2B (manufacturing buyers, procurement managers, packaging industry) + B2C (retail, ecommerce) |
| **Channels** | GA, LinkedIn, Reddit, YouTube, WhatsApp, Email (SMTP/IMAP) |
| **Business Model** | Manufacturing (packaging, tarpaulin, bubble roll, ecommerce) → ERP-integrated automation |
| **Automation Scope** | SOP-driven workflows, quote generation, invoice processing, contact enrichment, campaigns |
| **Human-in-the-Loop** | Quote approval, pricing overrides, governance/PII review, campaign sign-off |
| **Funnel Focus** | Awareness → Lead Capture → Enrichment → Personalized Outreach → Quote → Close → Reorder |
| **Growth Vector** | Regional expansion + seasonal personalization + real-time commodity pricing |

---

## § 3. SYSTEM ARCHITECTURE — Senior Architect View

```
  ╔══════════════════════════════════════════════════════════════════════════════════════╗
  ║                    KALISOFTAI SALES PIPELINE — REFERENCE ARCHITECTURE                ║
  ╠══════════════════════════════════════════════════════════════════════════════════════╣
  ║                                                                                      ║
  ║  ┌─── PRESENTATION TIER ──────────────────────────────────────────────────────────┐ ║
  ║  │                                                                                │ ║
  ║  │   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                     │ ║
  ║  │   │   React SPA  │    │  Cloud Run   │    │  Mobile Web  │                     │ ║
  ║  │   │   (Vite)     │◄──►│  (FastAPI)   │◄──►│  (PWA-ready) │                     │ ║
  ║  │   │  port 5173   │    │  port 8080   │    │              │                     │ ║
  ║  │   └──────┬───────┘    └──────┬───────┘    └──────────────┘                     │ ║
  ║  │          │                   │                                                  │ ║
  ║  └──────────┼───────────────────┼──────────────────────────────────────────────────┘ ║
  ║             │                   │                                                    ║
  ║  ┌─── API TIER ─────────────────┼──────────────────────────────────────────────────┐ ║
  ║  │          │                   │                                                  │ ║
  ║  │          ▼                   ▼                                                  │ ║
  ║  │   ┌─────────────────────────────────────────────────────────────────────────┐  │ ║
  ║  │   │                     FASTAPI APPLICATION                                  │  │ ║
  ║  │   │  ┌────────┐ ┌──────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐   │  │ ║
  ║  │   │  │  auth  │ │contacts  │ │campaign│ │ events │ │ social │ │  kpi   │   │  │ ║
  ║  │   │  │router  │ │  router  │ │ router │ │ router │ │ router │ │ router │   │  │ ║
  ║  │   │  └────────┘ └──────────┘ └────────┘ └────────┘ └────────┘ └────────┘   │  │ ║
  ║  │   │  ┌────────┐ ┌──────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐   │  │ ║
  ║  │   │  │email   │ │whatsapp  │ │templ-  │ │feedback│ │ govern-│ │system  │   │  │ ║
  ║  │   │  │router  │ │  router  │ │ates    │ │ router │ │  ance  │ │ router │   │  │ ║
  ║  │   │  └────────┘ └──────────┘ └────────┘ └────────┘ └────────┘ └────────┘   │  │ ║
  ║  │   │                                                                          │  │ ║
  ║  │   │  ┌─── SERVICE LAYER ──────────────────────────────────────────────┐     │  │ ║
  ║  │   │  │  GCSStorage · EmailService · WhatsAppService · SocialService   │     │  │ ║
  ║  │   │  │  SchedulerService · AnalyticsService · GovernanceService       │     │  │ ║
  ║  │   │  └────────────────────────────────────────────────────────────────┘     │  │ ║
  ║  │   │                                                                          │  │ ║
  ║  │   │  ┌─── AI/LLM ROUTER ─────────────────────────────────────────────┐     │  │ ║
  ║  │   │  │                                                                │     │  │ ║
  ║  │   │  │   TIER 1 (NANO)    TIER 2 (SMALL)   TIER 3 (MEDIUM)          │     │  │ ║
  ║  │   │  │   qwen2.5:0.5b     qwen2.5:3b       llama3.1:8b              │     │  │ ║
  ║  │   │  │   ├── classify     ├── extract      ├── analyze              │     │  │ ║
  ║  │   │  │   ├── tag          ├── summarize    ├── enrich               │     │  │ ║
  ║  │   │  │   └── route        └── format       └── score                │     │  │ ║
  ║  │   │  │                                                                │     │  │ ║
  ║  │   │  │   TIER 4 (LARGE — CLOUD FALLBACK)                            │     │  │ ║
  ║  │   │  │   gemini-2.0-flash · gemini-2.5-pro                          │     │  │ ║
  ║  │   │  │   ├── quote generation · campaign writing · trend prediction │     │  │ ║
  ║  │   │  │   └── budget: 5M tokens/month · enforce: ON                  │     │  │ ║
  ║  │   │  └────────────────────────────────────────────────────────────────┘     │  │ ║
  ║  │   └─────────────────────────────────────────────────────────────────────────┘  │ ║
  ║  │                                                                                │ ║
  ║  └────────────────────────────────────────────────────────────────────────────────┘ ║
  ║                                                                                      ║
  ║  ┌─── DATA TIER ──────────────────────────────────────────────────────────────────┐ ║
  ║  │                                                                                │ ║
  ║  │   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐             │ ║
  ║  │   │   Cloud SQL      │  │   GCS Buckets    │  │   Redis          │             │ ║
  ║  │   │   PostgreSQL     │  │   (8 buckets)    │  │   (cache/queue)  │             │ ║
  ║  │   │                  │  │                  │  │                  │             │ ║
  ║  │   │  ┌────────────┐  │  │  ┌────────────┐  │  │  ┌────────────┐  │             │ ║
  ║  │   │  │ contacts   │  │  │  │ datahub    │  │  │  │ campaign   │  │             │ ║
  ║  │   │  │ campaigns  │  │  │  │ (1.2 GB)   │  │  │  │ queue      │  │             │ ║
  ║  │   │  │ events     │  │  │  ├────────────┤  │  │  ├────────────┤  │             │ ║
  ║  │   │  │ quotes     │  │  │  │ kalika_    │  │  │  │ session    │  │             │ ║
  ║  │   │  │ feedback   │  │  │  │ enterprises│  │  │  │ store      │  │             │ ║
  ║  │   │  │ audit_logs │  │  │  │ (163 MB)   │  │  │  ├────────────┤  │             │ ║
  ║  │   │  │ templates  │  │  │  ├────────────┤  │  │  │ rate       │  │             │ ║
  ║  │   │  │ schedules  │  │  │  │ client_data│  │  │  │ limiter    │  │             │ ║
  ║  │   │  └────────────┘  │  │  │ official_  │  │  │  └────────────┘  │             │ ║
  ║  │   │                  │  │  │ docs       │  │  │                  │             │ ║
  ║  │   │  5 Alembic       │  │  │ sales_crm  │  │  │                  │             │ ║
  ║  │   │  migrations      │  │  │ (planned)  │  │  │                  │             │ ║
  ║  │   └──────────────────┘  │  └────────────┘  │  └──────────────────┘             │ ║
  ║  │                          └──────────────────┘                                   │ ║
  ║  └────────────────────────────────────────────────────────────────────────────────┘ ║
  ║                                                                                      ║
  ║  ┌─── INTEGRATION TIER ───────────────────────────────────────────────────────────┐ ║
  ║  │                                                                                │ ║
  ║  │   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │ ║
  ║  │   │ Gmail   │ │WhatsApp │ │LinkedIn │ │ Reddit  │ │ YouTube │ │ Google  │   │ ║
  ║  │   │SMTP/IMAP│ │Cloud API│ │  API    │ │   API   │ │Data API │ │   GA    │   │ ║
  ║  │   └─────────┘ └────┬────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │ ║
  ║  │                    │                                                          │ ║
  ║  │              ┌─────┴─────┐                                                    │ ║
  ║  │              │ Wechaty   │  (Node.js sidecar — WhatsApp/WeChat gateway)       │ ║
  ║  │              │ Gateway   │                                                    │ ║
  ║  │              │ port 8788 │                                                    │ ║
  ║  │              └───────────┘                                                    │ ║
  ║  └────────────────────────────────────────────────────────────────────────────────┘ ║
  ║                                                                                      ║
  ║  ┌─── SECURITY & GOVERNANCE ──────────────────────────────────────────────────────┐ ║
  ║  │                                                                                │ ║
  ║  │   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │ ║
  ║  │   │ Google   │ │  Fernet  │ │   PII    │ │  Audit   │ │  Rate    │           │ ║
  ║  │   │ Sign-In  │ │Encrypt   │ │ Redact   │ │  Logs    │ │ Limit    │           │ ║
  ║  │   │ (OAuth)  │ │(AES-128) │ │          │ │ (365d)   │ │          │           │ ║
  ║  │   └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘           │ ║
  ║  │                                                                                │ ║
  ║  │   Retention: Audit = 365 days · Contacts = 730 days · GDPR-ready              │ ║
  ║  └────────────────────────────────────────────────────────────────────────────────┘ ║
  ║                                                                                      ║
  ║  ┌─── INFRASTRUCTURE ─────────────────────────────────────────────────────────────┐ ║
  ║  │                                                                                │ ║
  ║  │   Cloud Run (asia-south1) ─── 512Mi RAM · 1 CPU · 0-5 instances · 300s timeout│ ║
  ║  │   Cloud Build ─── Dockerfile.sales → gcr.io/PROJECT/kalisoft-sales:$SHORT_SHA  │ ║
  ║  │   Secret Manager ─── SALES_SECRET_KEY · SALES_DATABASE_URL                     │ ║
  ║  │   Cloud Scheduler ─── cron triggers → Cloud Functions + /api/scheduler/run     │ ║
  ║  └────────────────────────────────────────────────────────────────────────────────┘ ║
  ╚══════════════════════════════════════════════════════════════════════════════════════╝
```

---

## § 4. DATA FLOW DIAGRAMS

### 4.1 — Contact Ingestion Flow

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │                    CONTACT INGESTION PIPELINE                        │
  └──────────────────────────────────────────────────────────────────────┘

  [User Upload]          [GCS Trigger]           [Scheduler]
       │                      │                      │
       ▼                      ▼                      ▼
  ┌─────────┐          ┌───────────┐          ┌───────────┐
  │ POST    │          │ GCS upload│          │ Daily cron│
  │ /api/   │          │ event on  │          │ contact   │
  │contacts/│          │ all-sales-│          │ enrich    │
  │upload   │          │ contacts- │          │ job       │
  └────┬────┘          │ data/     │          └─────┬─────┘
       │               └─────┬─────┘                │
       │                     │                      │
       ▼                     ▼                      ▼
  ┌──────────────────────────────────────────────────────────┐
  │                    VALIDATION LAYER                       │
  │                                                          │
  │   ┌────────────┐  ┌────────────┐  ┌────────────────┐    │
  │   │ GCS prefix │  │  File type │  │  PII redaction │    │
  │   │ validation │  │  check     │  │  (Fernet enc)  │    │
  │   │ (must be   │  │  xlsx/csv/ │  │                │    │
  │   │  within    │  │  vcf/xls   │  │  Name→Hash     │    │
  │   │  contacts) │  │            │  │  Phone→Mask    │    │
  │   └────────────┘  └────────────┘  └────────────────┘    │
  └──────────────────────────┬───────────────────────────────┘
                              │
                              ▼
  ┌──────────────────────────────────────────────────────────┐
  │              PARSING & NORMALIZATION                      │
  │                                                          │
  │   openpyxl (xlsx)  ·  xlrd (xls)  ·  csv  ·  vcard      │
  │          │                                               │
  │          ▼                                               │
  │   ┌──────────────────────────────────────────┐          │
  │   │  Standard Contact Schema:                │          │
  │   │  { name, email, phone, company,          │          │
  │   │    region, industry, source_file,        │          │
  │   │    uploaded_by, created_at, tags[] }     │          │
  │   └──────────────────────────────────────────┘          │
  └──────────────────────────┬───────────────────────────────┘
                              │
                              ▼
  ┌──────────────────────────────────────────────────────────┐
  │              AI ENRICHMENT (Ollama local)                  │
  │                                                          │
  │   NANO tier (qwen2.5:0.5b):                             │
  │     ├── Classify: B2B / B2C                              │
  │     ├── Tag: industry vertical                           │
  │     └── Score: lead quality (1-10)                       │
  │                                                          │
  │   MEDIUM tier (llama3.1:8b):                             │
  │     ├── Enrich: company size estimate                    │
  │     ├── Region mapping: city → state → country           │
  │     └── Deduplicate: fuzzy name + email match            │
  └──────────────────────────┬───────────────────────────────┘
                              │
                              ▼
  ┌──────────────────────────────────────────────────────────┐
  │              PostgreSQL (Cloud SQL)                       │
  │                                                          │
  │   INSERT INTO contacts (...) ON CONFLICT DO UPDATE       │
  │   + audit_log entry                                      │
  └──────────────────────────────────────────────────────────┘
```

### 4.2 — Quote Generation Flow

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │                    QUOTE GENERATION PIPELINE                         │
  └──────────────────────────────────────────────────────────────────────┘

  [Trigger Sources]
       │
       ├── Customer request (email/WhatsApp)
       ├── Reorder predictor (scheduled)
       ├── Event-based (trade show follow-up)
       └── Manual (sales rep)
       │
       ▼
  ┌──────────────────────────────────────────────────────────┐
  │              CONTEXT ASSEMBLY                             │
  │                                                          │
  │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
  │   │ Customer     │  │ Catalog      │  │ Seasonal     │  │
  │   │ History      │  │ Prices       │  │ Trends       │  │
  │   │ (Cloud SQL)  │  │ (ERP-V1/)    │  │ (GA + CRM)   │  │
  │   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
  │          │                 │                  │          │
  │          └─────────────────┼──────────────────┘          │
  │                            │                             │
  │   ┌──────────────────────────────────────────────┐      │
  │   │  + Chat intent (WhatsApp sync JSON)           │      │
  │   │  + LinkedIn signals (job title, company)      │      │
  │   │  + Demographic region (GA city → timezone)    │      │
  │   │  + Buy cycle position (pre/peak/post season)  │      │
  │   └──────────────────────────────────────────────┘      │
  └──────────────────────────┬───────────────────────────────┘
                              │
                              ▼
  ┌──────────────────────────────────────────────────────────┐
  │              LLM ROUTER                                   │
  │                                                          │
  │   Task complexity assessment:                            │
  │     ├── Simple reorder quote  → TIER 2 (qwen2.5:3b)     │
  │     ├── Standard new quote    → TIER 3 (gemini-2-flash) │
  │     └── Complex multi-SKU     → TIER 4 (gemini-2.5-pro) │
  │                                                          │
  │   Budget check: 5M tokens/month, enforce ON              │
  └──────────────────────────┬───────────────────────────────┘
                              │
                              ▼
  ┌──────────────────────────────────────────────────────────┐
  │              QUOTE RENDERING                              │
  │                                                          │
  │   ┌──────────────────────────────────────────────┐      │
  │   │  Personalized elements:                       │      │
  │   │  • "Based on your last order of [X] in [Mon]" │      │
  │   │  • "With [season] approaching, we recommend…" │      │
  │   │  • "Current market rate for [commodity]: ₹Y"  │      │
  │   │  • "Your region's top demand: [product]"      │      │
  │   │  • Multi-currency (₹ / $ / €)                │      │
  │   └──────────────────────────────────────────────┘      │
  └──────────────────────────┬───────────────────────────────┘
                              │
                              ▼
  ┌──────────────────────────────────────────────────────────┐
  │              HUMAN APPROVAL GATE                          │
  │                                                          │
  │   ┌────────────┐     YES     ┌──────────────────┐       │
  │   │ Sales rep  │────────────►│ Send via channel  │       │
  │   │ reviews    │             │ (WhatsApp/Email)  │       │
  │   │ & approves │     NO      └──────────────────┘       │
  │   └─────┬──────┘──────────┐                             │
  │         │                 │                              │
  │         │            ┌────▼─────┐                       │
  │         │            │ Revise   │                       │
  │         │            │ & retry  │                       │
  │         │            └──────────┘                       │
  └──────────────────────────────────────────────────────────┘
```

### 4.3 — WhatsApp Chat Sync Flow (Cloud Function)

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │              WHATSAPP CHAT SYNC — CLOUD FUNCTION                     │
  └──────────────────────────────────────────────────────────────────────┘

  Cloud Scheduler (every 6h)
       │
       ▼
  ┌──────────────────┐
  │  Cloud Function  │
  │  whatsapp-chat-  │
  │  sync            │
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────────────────────────────────────────────┐
  │  Step 1: LIST FILES                                      │
  │  gs://kalika_enterprises/Contacts/*.zip                  │
  │  gs://kalika_enterprises/Contacts/*.txt                  │
  │  gs://kalika_enterprises/Contacts/*.md                   │
  │  gs://kalika_enterprises/Contacts/*.vcf                  │
  └──────────────────────────┬───────────────────────────────┘
                              │
                              ▼
  ┌──────────────────────────────────────────────────────────┐
  │  Step 2: PARSE                                            │
  │                                                          │
  │   zip → unzip → .txt                                     │
  │   txt → line parser (timestamp, sender, message)         │
  │   vcf → vcard parser (name, phone, email, org)           │
  └──────────────────────────┬───────────────────────────────┘
                              │
                              ▼
  ┌──────────────────────────────────────────────────────────┐
  │  Step 3: AI EXTRACTION (NANO tier — qwen2.5:0.5b)        │
  │                                                          │
  │   For each message batch:                                │
  │   ┌──────────────────────────────────────────────┐      │
  │   │  {                                             │      │
  │   │    "intent": "pricing_inquiry",                │      │
  │   │    "entities": {                              │      │
  │   │      "product": "bubble_roll",                 │      │
  │   │      "quantity": "500 rolls",                  │      │
  │   │      "deadline": "next_week"                   │      │
  │   │    },                                          │      │
  │   │    "sentiment": "positive",                    │      │
  │   │    "lead_score": 8,                            │      │
  │   │    "follow_up": true,                          │      │
  │   │    "channel": "whatsapp",                      │      │
  │   │    "contact_phone": "+91XXXXXXXXXX"            │      │
  │   │  }                                             │      │
  │   └──────────────────────────────────────────────┘      │
  └──────────────────────────┬───────────────────────────────┘
                              │
                              ▼
  ┌──────────────────────────────────────────────────────────┐
  │  Step 4: WRITE OUTPUT                                     │
  │                                                          │
  │   gs://kalika_enterprises/Contacts/processed/             │
  │     └── chat_insights_{date}.json                         │
  │                                                          │
  │   + INSERT into Cloud SQL (contacts, activities)          │
  └──────────────────────────────────────────────────────────┘
```

### 4.4 — Multi-Channel Campaign Flow

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │              MULTI-CHANNEL CAMPAIGN ORCHESTRATION                     │
  └──────────────────────────────────────────────────────────────────────┘

  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
  │  Regional   │     │  Seasonal   │     │  Behavioral │
  │  Segment    │     │  Trigger    │     │  Trigger    │
  │  (US/IN/DE) │     │  (pre/peak) │     │  (reorder)  │
  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │     CAMPAIGN BUILDER (LLM)    │
              │                              │
              │  Template + Context + Region  │
              │  + Season + Channel          │
              │  → Personalized message      │
              └──────────────┬───────────────┘
                             │
              ┌──────────────┴───────────────┐
              │     CHANNEL ROUTER            │
              │                              │
              │  B2B + India    → WhatsApp   │
              │  B2B + US/EU    → Email      │
              │  B2C + India    → WhatsApp   │
              │  B2C + Global   → Email      │
              │  All + LinkedIn → LinkedIn   │
              └──┬──────────┬──────────┬─────┘
                 │          │          │
                 ▼          ▼          ▼
          ┌──────────┐ ┌────────┐ ┌──────────┐
          │ WhatsApp │ │ Email  │ │ LinkedIn │
          │ Cloud API│ │ SMTP   │ │   API    │
          │/Wechaty  │ │/Gmail  │ │          │
          └────┬─────┘ └───┬────┘ └────┬─────┘
               │           │           │
               └───────────┼───────────┘
                           │
                           ▼
              ┌──────────────────────────────┐
              │     DELIVERY TRACKER          │
              │                              │
              │  sent / delivered / opened /  │
              │  clicked / replied / bounced  │
              │                              │
              │  → PostgreSQL (campaign_logs) │
              │  → KPI dashboard refresh      │
              └──────────────────────────────┘
```

---

## § 5. PROMPTS TEMPLATES

| # | Template Name | Purpose | Model Tier | Input Context | Output |
|---|---|---|---|---|---|
| 1 | **GA Report Reader** | Summarize GA reports | MEDIUM | GA CSVs from `kalika-google-analytics/` | Executive summary + insights |
| 2 | **Quote Personalizer** | Next-order quotes | LARGE | Customer history + catalog + trends + demographics | Personalized quote PDF |
| 3 | **Seasonal Trend Analyzer** | Pre/peak/post behavior | MEDIUM | Purchase history, calendar, market data | Trend report + recommendations |
| 4 | **LinkedIn Enricher** | Profile insights | NANO | LinkedIn CSV exports | Structured profile JSON |
| 5 | **WhatsApp Chat Classifier** | Intent + entities | NANO/LOCAL | Chat exports (txt/zip) | Intent JSON + metadata |
| 6 | **Social Signal Aggregator** | Lead scoring | MEDIUM | Reddit + YouTube + LinkedIn responses | Lead score (1-10) + signals |
| 7 | **Catalog Price Lookup** | Real-time pricing | LOCAL | `ERP-V1/catalog*` files | Current price + availability |
| 8 | **Regional Outreach Writer** | Region-specific cold outreach | LARGE | Demographics + GA + catalog | Outreach email/WhatsApp text |
| 9 | **Seasonal Campaign Builder** | Campaign generation | LARGE | Purchase patterns + GA + calendar | Campaign copy + schedule |
| 10 | **Customer Reorder Predictor** | Reorder prediction | MEDIUM | CRM history + seasonal + chat intent | Predicted reorder date + product |
| 11 | **Invoice/PO Extractor** | OCR → structured data | MEDIUM | PDF invoices/POs | Line items JSON |
| 12 | **Event Attendee Matcher** | Match events to contacts | NANO | Event workbook + contacts DB | Matched attendee list |

### Prompt Template: Quote Personalizer (Example)

```
  ╭──────────────────────────────────────────────────────────────────╮
  │  SYSTEM: You are a B2B sales quote assistant for Kalika          │
  │  Enterprises, a manufacturing company specializing in            │
  │  packaging, tarpaulin, and ecommerce supplies.                   │
  │                                                                  │
  │  Given:                                                          │
  │  - Customer purchase history (last 12 months)                    │
  │  - Current catalog prices (from ERP)                             │
  │  - Seasonal context (pre/peak/post)                              │
  │  - Customer's region and timezone                                │
  │  - Recent chat intent (if any)                                   │
  │                                                                  │
  │  Generate a personalized quote that:                             │
  │  1. References their last order by product + date                │
  │  2. Recommends 2-3 complementary products                        │
  │  3. Includes seasonal pricing (if applicable)                    │
  │  4. States delivery timeline for their region                    │
  │  5. Ends with a clear CTA                                        │
  │                                                                  │
  │  Tone: Professional, warm, confident. No fluff.                  │
  │  Currency: Match customer's region (₹/ $/ €).                   │
  ╰──────────────────────────────────────────────────────────────────╯
```

---

## § 6. GCS BUCKET MAP & DATA INVENTORY

### 6.1 — Bucket Overview

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │                    GCS BUCKET TOPOLOGY                                │
  │                    Project: gen-lang-client-0132243782               │
  └──────────────────────────────────────────────────────────────────────┘

                          ┌─────────────────────┐
                          │   GCS Project Root   │
                          │   8 buckets total    │
                          └──────────┬──────────┘
                                     │
          ┌──────────────┬───────────┼───────────┬──────────────┐
          │              │           │           │              │
          ▼              ▼           ▼           ▼              ▼
  ┌──────────────┐ ┌──────────┐ ┌────────┐ ┌────────┐ ┌──────────────┐
  │kalisoftai-   │ │kalika_   │ │kalisoft│ │kalisoft│ │  sales-crm   │
  │datahub       │ │enterpri- │ │ai_     │ │ai-     │ │  (planned)   │
  │★ PRIMARY     │ │ses       │ │client_ │ │official│ │              │
  │ (ASIA)       │ │ (US)     │ │data    │ │-docs   │ │  (US, empty) │
  │ 1,242 MB     │ │ 163 MB   │ │ (US)   │ │ (US)   │ │              │
  │ 902 objects  │ │ 48 objs  │ │ 60 MB  │ │ 37 MB  │ │              │
  └──────┬───────┘ └────┬─────┘ │145 objs│ │28 objs │ └──────────────┘
         │              │       └────────┘ └────────┘
         │              │
         ▼              ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  APP READS:                                                   │
  │  GCS_BUCKET_CONTACTS = kalisoftai-datahub                     │
  │  GCS_PATH_CONTACTS   = all-sales-contacts-data/               │
  │                                                              │
  │  CLOUD FUNCTION READS:                                       │
  │  kalika_enterprises/Contacts/ (chat sync)                    │
  │  kalika_enterprises/ERP-V1/  (catalog pricing)               │
  └──────────────────────────────────────────────────────────────┘
```

### 6.2 — `kalisoftai-datahub` (Primary — 902 objects, 1,242 MB)

| Prefix | Objects | Size | Purpose | Priority |
|---|---|---|---|---|
| `all-sales-contacts-data/` | 28 | 18.6 MB | **App contacts module** | ★★★ CRITICAL |
| `kalika-sales-data/` | 18 | 23.7 MB | Invoices, POs, quotes, product images | ★★★ CRITICAL |
| `kalika-main-data/` | 296 | 73.0 MB | Main business data | ★★ HIGH |
| `nano images/` | 232 | 413.9 MB | Product/content images | ★★ HIGH |
| `content-creation-data/` | 46 | 183.6 MB | Marketing content | ★★ HIGH |
| `Agentic_Arena/` | 17 | 117.6 MB | Agent workspace | ★ MEDIUM |
| `Clients_data/` | 5 | 45.2 MB | Client files | ★ MEDIUM |
| `venu-industries/` | 15 | 34.0 MB | Client: Venu Industries | ★ MEDIUM |
| `smoke-detection/` | 8 | 28.1 MB | Project data | ★ LOW |
| `AAMI/` | 3 | 24.9 MB | Client: AAMI | ★ MEDIUM |
| `nm-aluminates/` | 10 | 14.1 MB | Client: NM Aluminates | ★ MEDIUM |
| `swasth-first/` | 1 | 10.3 MB | Client: Swasth First | ★ MEDIUM |
| `Events/` | 4 | 0.55 MB | Event workbooks | ★★ HIGH |
| `prompts/` | 15 | 0.31 MB | Prompt templates | ★★★ CRITICAL |
| `sales-aiagent/` | 4 | 0.07 MB | Agent outputs | ★★ HIGH |
| `linkedin-post-analysis/` | 85 | 0.50 MB | LinkedIn analytics | ★★ HIGH |
| `youtube-analysis/` | 3 | 0.02 MB | YouTube analytics | ★ MEDIUM |
| `procurement-ai-agent/` | 5 | 2.18 MB | Procurement agent | ★ MEDIUM |
| `catalogue/` | 9 | 0.01 MB | Product catalog | ★★★ CRITICAL |
| `processed/` | 13 | 0.31 MB | Processed data | ★★ HIGH |
| Other (15 prefixes) | ~80 | ~5 MB | Misc | ★ LOW |

### 6.3 — `kalika_enterprises` (Client — 48 objects, 163 MB)

| Prefix | Objects | Size | Purpose | Priority |
|---|---|---|---|---|
| `ERP-V1/` | 8 | 94.5 MB | **ERP catalog, SOP manuals, system docs** | ★★★ CRITICAL |
| `Contacts/` | 9 | 33.4 MB | **WhatsApp chats, VCF contacts** | ★★★ CRITICAL |
| `sales-contacts/` | 7 | 14.5 MB | Contact spreadsheets (app copies) | ★★ HIGH |
| `images and videos/` | 13 | 14.2 MB | Product/media files | ★ MEDIUM |
| `docs/` | 5 | 2.2 MB | Invoices, logos | ★ MEDIUM |
| `sales-2025-27/` | 2 | 0.1 MB | GST invoices, roadmap | ★★ HIGH |
| Root | 2 | 4.7 MB | Catalog PDFs | ★★ HIGH |

### 6.4 — Other Buckets

| Bucket | Objects | Size | Purpose |
|---|---|---|---|
| `kalisoftai_client_data` | 145 | 60 MB | AG-Vision, marketing, sales-data |
| `kalisoftai-official-docs` | 28 | 37 MB | Quotations, bills, Data-pro |
| `sales-crm` | 0 | 0 MB | **Planned: future CRM** (needs SA binding) |
| `ai-studio-bucket-*` | — | — | AI Studio auto-created |
| `gen-lang-client-*_cloudbuild` | — | — | Cloud Build artifacts |
| `run-sources-*` | — | — | Cloud Run source deploys |

---

## § 7. INPUT DATA SOURCES

### 7.1 — Google Analytics (kalika-google-analytics)

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  GA PROPERTY: Commercial Ecommerce Tracking                          │
  │  Account: KalisoftAI · Period: 2026-09-20 → 2026-10-17              │
  └──────────────────────────────────────────────────────────────────────┘

  COUNTRY BREAKDOWN (Active Users)
  ─────────────────────────────────
  United States  ████████████████████████████████████████████░░  124 (84.9%)
  India          █████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   15 (10.3%)
  Germany        █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    3  (2.1%)
  Singapore      █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    3  (2.1%)
  (not set)      ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    1  (0.7%)

  CITY BREAKDOWN (Top 10)
  ────────────────────────
  Ashburn        ██████████████████████████████░░░░░░░░  35
  San Jose       ███████████████░░░░░░░░░░░░░░░░░░░░░░  17
  Des Moines     ███████████░░░░░░░░░░░░░░░░░░░░░░░░░░  13
  Flint Hill     ███████████░░░░░░░░░░░░░░░░░░░░░░░░░░  13
  Los Angeles    ██████████░░░░░░░░░░░░░░░░░░░░░░░░░░░  12
  Hyderabad      ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  10  ← India South
  New York       ███████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   9
  Moses Lake     ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   4
  San Francisco  ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   4
  Pune           ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   3  ← India South

  ENGAGEMENT RATE BY CITY
  ────────────────────────
  Singapore      ████████████████████████████████████████████████████████  66.7% ★
  San Jose       ██████████████████████████████████████████████░░░░░░░░░  58.8%
  Des Moines     █████████████████████████████████████████░░░░░░░░░░░░░░  64.3%
  Flint Hill     ████████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░  46.2%
  India (avg)    ███████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  29.4%
  US (avg)       █████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  28.8%

  TECH OVERVIEW
  ─────────────
  Platform:     Web (100%)
  Device:       Desktop 143 (97.9%) · Mobile 3 (2.1%)
  OS:           Windows 90 · Linux 37 · Mac 16 · Android 2 · iOS 1
```

| Report | File | Rows | Key Insights |
|---|---|---|---|
| Country Demographics | `Demographic_details_Country (1).csv` | 5 | US: 124 (85%), IN: 15, DE: 3, SG: 3 |
| City Demographics | `Demographic_details_Town_City.csv` | 20+ | Ashburn: 35, San Jose: 17, Hyderabad: 10 |
| Tech Overview | `Tech_overview.csv` | 33 | Desktop 98%, Windows dominant |
| Engagement/Retention | `View user engagement...csv` | 200 | Full cohort retention data |

### 7.2 — Contact & Chat Data

| Source | GCS Path | Format | Volume | Leads Est. |
|---|---|---|---|---|
| WhatsApp group chats | `kalika_enterprises/Contacts/` | zip, txt, md | 18 MB + 202-264 KB | ~500 |
| VCF contacts | `kalika_enterprises/Contacts/` | vcf | 14.5 MB | ~2,000 |
| App contact spreadsheets | `all-sales-contacts-data/` | xlsx, csv, vcf | 28 files, 18.6 MB | ~1,500 |
| Directory contacts | `all-sales-contacts-data/` | xlsx | 75 KB + 25 KB | ~300 |
| Regional contacts (Pune/Chennai) | `all-sales-contacts-data/` | xlsx | 9.5 KB | ~100 |
| Tarpaulin buyer contacts | `all-sales-contacts-data/` | csv | 48 KB | ~200 |
| Purchase managers list | `all-sales-contacts-data/` | xlsx | 41 KB | ~150 |
| AAMI manufacturing contacts | `all-sales-contacts-data/` | xlsx | 151 KB | ~500 |
| Chattrapati Sambhajinagar companies | `all-sales-contacts-data/` | xlsx | 152 KB | ~400 |
| LinkedIn contacts export | `all-sales-contacts-data/` | csv | 0.2 KB | ~50 |
| Events contacts | `all-sales-contacts-data/` | csv | 0.1 KB | ~20 |

### 7.3 — Catalog & Pricing Data

| Source | GCS Path | Format | Size |
|---|---|---|---|
| **Main Catalog** | `kalika_enterprises/ERP-V1/New_kalika_enterprises_catalog.pdf` | pdf | 41.9 MB |
| Product Catalog (app) | `kalisoftai-datahub/catalogue/` | mixed | 9 files |
| ERP System Doc | `kalika_enterprises/ERP-V1/software-docs/Kalika_ERP_System_Doc.docx` | docx | 37.2 MB |
| SOP Manual | `kalika_enterprises/ERP-V1/software-docs/Kalika_Detailed_SOP_Manual.docx` | docx | 16.6 MB |
| Features PDF | `kalika_enterprises/ERP-V1/software-docs/Kalika_Feat.pdf` | pdf | 0.2 MB |

### 7.4 — Sales History (Invoices / POs / Quotes)

| File | GCS Path | Size |
|---|---|---|
| SALES GST invoices | `kalika_enterprises/sales-2025-27/` | 87 KB |
| Purchase Orders (2) | `kalisoftai-datahub/kalika-sales-data/PurchOrd_*.pdf` | 36 KB each |
| Quote 244 | `kalisoftai-datahub/kalika-sales-data/QUOTE 244.pdf` | 948 KB |
| Delivery notes (2) | `kalisoftai-datahub/kalika-sales-data/` | 777 KB + 1062 KB |
| GST invoices (3) | `kalisoftai-datahub/kalika-sales-data/` | 87-295 KB |
| 21 Sep Receive | `kalika-sales-data/21 SEP RECEIVE.xlsx` | 45 KB |

---

## § 8. CRON JOBS / SCHEDULED TASKS

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │                    CRON SCHEDULE TIMELINE (24h)                       │
  └──────────────────────────────────────────────────────────────────────┘

  Hour: 00  01  02  03  04  05  06  07  08  09  10  11  12  13  14  15  16  17  18  19  20  21  22  23
        │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │
  GA    ●───────────────────────────────────────────────────────────────────────────────────────●
  Sync  │                                                                       (daily 00:00)    │
        │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │
  Chat  ●───────────────●───────────────●───────────────●───────────────●───────────────●─────────
  Sync  │   (every 6h: 00, 06, 12, 18)                                                              │
        │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │
  Price ●   ●   ●   ●   ●   ●   ●   ●   ●   ●   ●   ●   ●   ●   ●   ●   ●   ●   ●   ●   ●   ●
  Refresh (hourly)                                                                                 │
        │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │
  Email ●───────────────●───────────────●───────────────●───────────────●───────────────●─────────
  Sweep │   (every 4h: 00, 04, 08, 12, 16, 20)                                                      │
        │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │
  WhatsApp                                                                             ●───────────
  Sweep                                                                                  (every 4h) │
        │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │
  KPI   ●───────────────────────────────────────●───────────────────────────────────────●─────────
  Refresh (hourly)                                                                                   │
        │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │
  Contact                                                                        ●─────────────────
  Enrich                                                                          (daily 09:00)     │
        │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │
  Social ●───────────────────────────────────────────────────────────────────────────────────────●
  Pull   │   (daily 08:00)                                                                          │
        │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │
  Seasonal                                                                                         ●
  Trend                                                                                      (weekly) │
        │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │
  Audit  ●───────────────────────────────────────────────────────────────────────────────────────●
  Cleanup (daily 01:00)                                                                             │
```

| # | Task | Frequency | Route | Purpose |
|---|---|---|---|---|
| 1 | **GA Report Sync** | Daily (00:00) | Cloud Function → GCS | Pull latest GA reports |
| 2 | **WhatsApp Chat Sync** | Every 6h | Cloud Function | Parse chats → intent/entities JSON |
| 3 | **Contact Enrichment** | Daily (09:00) | `POST /api/scheduler/run` | Enrich + dedupe + PII-redact |
| 4 | **Catalog Price Refresh** | Hourly | Cloud Function | Real-time commodity prices |
| 5 | **Seasonal Trend Analysis** | Weekly | Scheduler task | Pre/peak/post analysis |
| 6 | **Quote Follow-up** | Daily | Scheduler task | Flag reorder candidates |
| 7 | **LinkedIn Signal Pull** | Daily (08:00) | `POST /api/social/...` | Connections, views, engagement |
| 8 | **Reddit/YouTube Monitor** | Daily | `POST /api/social/youtube/search` | Lead discovery |
| 9 | **KPI Dashboard Refresh** | Hourly | `GET /api/kpi/overview` | Funnel, delivery, AI spend |
| 10 | **Email Campaign Sweep** | Every 4h | Scheduler task | Send queued emails |
| 11 | **WhatsApp Campaign Sweep** | Every 4h | Scheduler task | Send queued WhatsApp messages |
| 12 | **Event Workbook Import** | On upload | `POST /api/events/import` | Parse events → schedule invites |
| 13 | **Audit Log Cleanup** | Daily (01:00) | Scheduler | Purge expired audit logs |

### Scheduler Config

| Setting | Value |
|---|---|
| Endpoint | `POST /api/scheduler/run` (manual + Cloud Scheduler target) |
| Status | `GET /api/scheduler/status` |
| Task list | `GET /api/scheduler/tasks` (cron expressions per task) |
| Queue | Redis with in-memory fallback |
| Scope | User-scoped |

---

## § 9. CLOUD FUNCTIONS

| # | Function | Trigger | Input | Output | Purpose |
|---|---|---|---|---|---|
| 1 | **WhatsApp Chat Sync** | Scheduler (6h) | `Contacts/*.zip` | JSON (intent, entities, metadata) | Chats → structured leads |
| 2 | **GA Report Ingest** | Scheduler (daily) | GA API / CSV | CSV in `kalika-google-analytics/` | Keep analytics fresh |
| 3 | **Catalog Price Fetch** | Scheduler (hourly) | Commodity APIs / ERP | JSON prices → `catalogue/` | Real-time pricing |
| 4 | **Invoice/PO Extractor** | GCS upload event | `kalika-sales-data/*.pdf` | Structured JSON | OCR → line items → CRM |
| 5 | **VCF Contact Parser** | GCS upload event | `Contacts/*.vcf` | JSON contacts | Dedupe + enrich |

---

## § 10. REGIONAL STRATEGY MATRIX

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │                    REGIONAL PRIORITY MATRIX                           │
  └──────────────────────────────────────────────────────────────────────┘

  Engagement Rate
  100% │
       │                                              ★ Singapore (66.7%)
   75% │                                         ╱
       │                                   ╱
   50% │                              ★ San Jose (58.8%)
       │                         ╱
   25% │          ★ US avg (28.8%) · ★ India avg (29.4%)
       │     ╱              ╲
    0% │★ Germany (0%)       ╲
       └──────────────────────────────────────────────────────────
          0      25      50      75     100     125     150
                          Active Users

  STRATEGY QUADRANT
  ─────────────────
                    HIGH ENGAGEMENT
                         │
         ┌───────────────┼───────────────┐
         │   NURTURE     │   PRIORITIZE  │
         │               │               │
         │   India South │  Singapore    │
         │   (scale up)  │  (convert!)   │
  LOW ───┼───────────────┼───────────────┼─── HIGH
  VOLUME │               │               │  VOLUME
         │   EXPLORE     │   MAINTAIN    │
         │               │               │
         │   Germany     │  United States│
         │   (test)      │  (scale)      │
         │               │               │
         └───────────────┼───────────────┘
                         │
                    LOW ENGAGEMENT
```

| Region | GA Users | Engagement | Strategy | Channel Priority | Target Revenue |
|---|---|---|---|---|---|
| **United States** | 124 (85%) | 28.8% | Scale via LinkedIn + Email, target procurement managers | LinkedIn > Email > YouTube | $50K/mo |
| **India — South** (Hyderabad, Pune) | 13 | 29.4% | WhatsApp-first, regional language, local events | WhatsApp > Email > LinkedIn | ₹15L/mo |
| **India — North** | TBD | TBD | Trade shows, industry directories, cold outreach | Email > LinkedIn > WhatsApp | ₹10L/mo |
| **Germany** | 3 | 0% | LinkedIn targeting, English outreach, trade portals | LinkedIn > Email | €5K/mo |
| **Singapore** | 3 | 66.7% | **Highest intent — prioritize follow-up, personalized quotes** | Email > WhatsApp > LinkedIn | $15K/mo |

---

## § 11. SALES & MARKETING STRATEGIES

### 11.1 — Strategy Framework

```
  ╭──────────────────────────────────────────────────────────────────────╮
  │                    4-PILLAR GROWTH STRATEGY                          │
  ╰──────────────────────────────────────────────────────────────────────╯

  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
  │   PILLAR 1      │  │   PILLAR 2      │  │   PILLAR 3      │  │   PILLAR 4      │
  │   REGIONAL      │  │   CHANNEL       │  │   SEASONAL      │  │   AUTOMATION    │
  │   EXPANSION     │  │   DOMINANCE     │  │   INTELLIGENCE  │  │   ENGINE        │
  │                 │  │                 │  │                 │  │                 │
  │ • US scale-up   │  │ • WhatsApp: 80% │  │ • Pre-season    │  │ • AI quotes     │
  │ • India South   │  │   India B2B     │  │   forecasts     │  │ • Auto-enrich   │
  │   penetration   │  │ • LinkedIn: 70% │  │ • Peak: flash   │  │ • Smart routing │
  │ • Singapore     │  │   US/EU B2B     │  │   deals         │  │ • Predictive    │
  │   conversion    │  │ • Email: 90%    │  │ • Post: reorder │  │   reorder       │
  │ • Germany test  │  │   global        │  │   prompts       │  │ • Auto-invoice  │
  │   market        │  │ • YouTube: 50%  │  │ • Festival:     │  │ • SOP-driven    │
  │                 │  │   awareness     │  │   corporate     │  │   workflows     │
  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘
```

### 11.2 — Tactical Playbook

| Strategy | Tactics | Channel | Timeline | KPI |
|---|---|---|---|---|
| **US Procurement Blitz** | LinkedIn InMail to 500 procurement managers + personalized email with catalog | LinkedIn + Email | Weeks 1-4 | 10% reply rate |
| **India South WhatsApp** | WhatsApp Business API → Hyderabad/Pune packaging buyers + event follow-ups | WhatsApp | Weeks 1-2 | 25% response rate |
| **Singapore High-Intent** | Immediate follow-up to 3 active users + personalized quote with SGD pricing | Email + WhatsApp | Week 1 | 100% follow-up within 24h |
| **Germany Trade Portal** | List on Europages + LinkedIn outreach in English | LinkedIn + Email | Weeks 3-8 | 5 qualified leads |
| **Seasonal Pre-Season** | Bulk order forecasts to top 50 B2B clients 6 weeks before peak | Email + WhatsApp | Per calendar | 20% pre-order conversion |
| **Reorder Engine** | AI predicts reorder date → auto-send personalized quote 1 week before | Email | Continuous | 15% reorder rate |
| **Content Marketing** | YouTube product demos + LinkedIn posts from `content-creation-data/` | YouTube + LinkedIn | Weekly | 2x brand awareness |
| **Event-Driven** | Trade show attendee matching → WhatsApp invite + follow-up quote | WhatsApp + Email | Per event | 30% booth-to-quote |
| **Referral Program** | Existing clients get 5% discount for referrals → tracked via unique codes | Email + WhatsApp | Ongoing | 10 new leads/mo |
| **ABM (Account-Based)** | Top 20 accounts get dedicated landing pages + personalized catalogs | Email + LinkedIn | Q1 2027 | 30% account penetration |

### 11.3 — Content Strategy Matrix

| Content Type | Source | Channel | Frequency | Target |
|---|---|---|---|---|
| Product catalog PDFs | `ERP-V1/` | Email attachments | Per quote | B2B buyers |
| WhatsApp status videos | `images and videos/` | WhatsApp | Daily | India B2C |
| LinkedIn industry posts | `linkedin-post-analysis/` | LinkedIn | 3x/week | US/EU B2B |
| YouTube product demos | `content-creation-data/` | YouTube | Weekly | Global awareness |
| Case studies | `Clients_data/` | Email + Website | Monthly | Enterprise leads |
| Seasonal lookbooks | `catalogue/` | Email + WhatsApp | Per season | All segments |

---

## § 12. SEASONAL PERSONALIZATION FRAMEWORK

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │                    SEASONAL CYCLE (Annual)                            │
  └──────────────────────────────────────────────────────────────────────┘

  Q1 (Jan-Mar)          Q2 (Apr-Jun)          Q3 (Jul-Sep)          Q4 (Oct-Dec)
  ───────────          ───────────          ───────────          ───────────
  ┌──────────┐         ┌──────────┐         ┌──────────┐         ┌──────────┐
  │ PRE-SEASON│         │ PEAK     │         │ POST-    │         │ FESTIVAL │
  │          │         │ SEASON   │         │ SEASON   │         │ SEASON   │
  │ • Forecast│         │ • Express│         │ • Reorder│         │ • Corporate│
  │ • Contract│         │   fulfill│         │   prompts│         │   gifting │
  │ • Early  │         │ • Inventory│       │ • Feedback│        │ • Gift    │
  │   bird   │         │   alerts │         │ • Clearance│       │   hampers │
  └──────────┘         └──────────┘         └──────────┘         └──────────┘
       │                    │                    │                    │
       ▼                    ▼                    ▼                    ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │  B2B FOCUS:  Bulk orders · Contract renewals · Volume discounts      │
  │  B2C FOCUS:  Early-bird · Flash sales · Loyalty rewards             │
  │  PRODUCTS:   Packaging · Tarpaulin · Bubble roll · Custom prints    │
  └──────────────────────────────────────────────────────────────────────┘
```

| Season | Timing | B2B Focus | B2C Focus | Catalog Items | LLM Prompt |
|---|---|---|---|---|---|
| **Pre-Season** | 4-6 weeks before | Bulk forecasts, contract renewals | Early-bird, wishlists | Packaging, tarpaulin, bubble roll | "Generate pre-season forecast for [region]" |
| **Peak Season** | During | Express fulfillment, inventory alerts | Flash sales, bundle deals | All products | "Create flash deal for [segment]" |
| **Post-Season** | 2-4 weeks after | Reorder prompts, feedback collection | Clearance, loyalty rewards | Leftover, new arrivals | "Write reorder email for [customer]" |
| **Festival/Event** | Per calendar | Corporate gifting, event supplies | Gift hampers, special editions | Custom prints, branded items | "Design festival campaign for [region]" |

---

## § 13. FUNNEL ARCHITECTURE

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │                    SALES FUNNEL — 7 STAGES                            │
  └──────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────────┐
                    │           AWARENESS                  │
                    │   GA visitors: 146/mo                │
                    │   LinkedIn reach: 5,000/mo           │
                    │   YouTube views: 2,000/mo            │
                    │   ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  100%
                    └──────────────────┬──────────────────┘
                                       │ 30% conversion
                    ┌──────────────────▼──────────────────┐
                    │           LEAD CAPTURE              │
                    │   Contacts in DB: ~5,000            │
                    │   New contacts/mo: ~200             │
                    │   Sources: GCS + WhatsApp + LinkedIn│
                    │   ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░   30%
                    └──────────────────┬──────────────────┘
                                       │ 40% conversion
                    ┌──────────────────▼──────────────────┐
                    │           ENRICHMENT                 │
                    │   AI-classified: B2B/B2C             │
                    │   Lead score: 1-10                   │
                    │   Region mapped + tagged             │
                    │   ▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░   12%
                    └──────────────────┬──────────────────┘
                                       │ 25% conversion
                    ┌──────────────────▼──────────────────┐
                    │     PERSONALIZED OUTREACH            │
                    │   Emails sent: ~1,000/mo             │
                    │   WhatsApp sent: ~500/mo             │
                    │   LinkedIn sent: ~200/mo             │
                    │   ▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░    3%
                    └──────────────────┬──────────────────┘
                                       │ 15% conversion
                    ┌──────────────────▼──────────────────┐
                    │           QUOTE                       │
                    │   Quotes generated: ~50/mo           │
                    │   Avg value: $2,000                  │
                    │   AI-personalized: 100%              │
                    │   ▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░   0.5%
                    └──────────────────┬──────────────────┘
                                       │ 30% conversion
                    ┌──────────────────▼──────────────────┐
                    │           CLOSE                       │
                    │   Deals won: ~15/mo                  │
                    │   Revenue: $30,000/mo                │
                    │   ▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0.15%
                    └──────────────────┬──────────────────┘
                                       │ 40% conversion
                    ┌──────────────────▼──────────────────┐
                    │           REORDER                     │
                    │   Repeat customers: ~6/mo            │
                    │   LTV multiplier: 3.2x               │
                    │   ▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0.06%
                    └─────────────────────────────────────┘

  CONVERSION SUMMARY
  ──────────────────
  Visitor → Lead:        30%
  Lead → Enriched:       40%
  Enriched → Contacted:  25%
  Contacted → Quoted:    15%
  Quoted → Won:          30%
  Won → Repeat:          40%
  ─────────────────────
  Overall (Visitor→Won): 0.15%  (industry avg: 0.1-0.3%)
  Overall (Lead→Won):    0.45%  (industry avg: 0.5-1%)
```

---

## § 14. KPI DASHBOARD (ASCII Visual)

```
  ╔══════════════════════════════════════════════════════════════════════════════════╗
  ║                        📊 KALIKA SALES KPI DASHBOARD                            ║
  ║                        Updated: 2026-10-18 · Region: ALL                        ║
  ╠══════════════════════════════════════════════════════════════════════════════════╣
  ║                                                                                  ║
  ║   ┌─── CONTACTS FUNNEL ──────────────────────────────────────────────────────┐  ║
  ║   │                                                                          │  ║
  ║   │   Total Contacts    ████████████████████████████████████████  5,200      │  ║
  ║   │   Enriched          ████████████████████████████░░░░░░░░░░░░  3,100  60% │  ║
  ║   │   Contacted         ████████████████░░░░░░░░░░░░░░░░░░░░░░░░  1,560  30% │  ║
  ║   │   Replied           ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    468   9% │  ║
  ║   │   Quoted            ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    140   3% │  ║
  ║   │   Closed            ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░     42   1% │  ║
  ║   │                                                                          │  ║
  ║   └──────────────────────────────────────────────────────────────────────────┘  ║
  ║                                                                                  ║
  ║   ┌─── OUTREACH DELIVERY ────────────────────────────────────────────────────┐  ║
  ║   │                                                                          │  ║
  ║   │   Channel        Sent      Delivered   Opened    Replied   Rate         │  ║
  ║   │   ─────────────────────────────────────────────────────────────         │  ║
  ║   │   Email          1,200     1,152       461       138       12.0% ✓     │  ║
  ║   │   WhatsApp       580       568         398       114       20.0% ✓     │  ║
  ║   │   LinkedIn       220       210         84        25        11.4% ✓     │  ║
  ║   │   ─────────────────────────────────────────────────────────────         │  ║
  ║   │   TOTAL          2,000     1,930       943       277       14.3%       │  ║
  ║   │                                                                          │  ║
  ║   └──────────────────────────────────────────────────────────────────────────┘  ║
  ║                                                                                  ║
  ║   ┌─── AI SPEND (Micro-USD Ledger) ──────────────────────────────────────────┐  ║
  ║   │                                                                          │  ║
  ║   │   Monthly Budget: $5.00  ████████████████████████░░░░░░░░░░░░  $3.12    │  ║
  ║   │                                                       Used: 62.4%       │  ║
  ║   │                                                                          │  ║
  ║   │   Model Breakdown:                                                       │  ║
  ║   │     qwen2.5:0.5b (NANO)    ████████████████████░░░░░░░░░░  $0.89  29%  │  ║
  ║   │     qwen2.5:3b  (SMALL)    ████████████████░░░░░░░░░░░░░░  $0.72  23%  │  ║
  ║   │     llama3.1:8b (MEDIUM)   ██████████████░░░░░░░░░░░░░░░░  $0.65  21%  │  ║
  ║   │     gemini-2-flash (LARGE) ████████████░░░░░░░░░░░░░░░░░░  $0.58  18%  │  ║
  ║   │     gemini-2.5-pro (XL)    ██████░░░░░░░░░░░░░░░░░░░░░░░░  $0.28   9%  │  ║
  ║   │                                                                          │  ║
  ║   └──────────────────────────────────────────────────────────────────────────┘  ║
  ╚══════════════════════════════════════════════════════════════════════════════════╝
```

---

## § 15. PIPELINE DASHBOARD (ASCII Visual)

```
  ╔══════════════════════════════════════════════════════════════════════════════════╗
  ║                        🔄 SALES PIPELINE STATUS                                 ║
  ║                        Active Deals: 42 · Total Value: $124,500                 ║
  ╠══════════════════════════════════════════════════════════════════════════════════╣
  ║                                                                                  ║
  ║   STAGE              DEALS    AVG VALUE    AGE (days)    WIN PROB    BAR        ║
  ║   ──────────────────────────────────────────────────────────────────────        ║
  ║   New Lead            180      $800          2            5%        ████░░░░░░  ║
  ║   Enriched            120      $1,200        5           10%        ██████░░░░  ║
  ║   Contacted            85      $1,800        8           15%        ████████░░  ║
  ║   Replied              42      $2,500       12           25%        ██████░░░░  ║
  ║   Quoted               28      $3,200       15           35%        ████░░░░░░  ║
  ║   Negotiation          15      $4,500       20           55%        ███░░░░░░░  ║
  ║   Verbal Commit         8      $6,000       22           75%        ██░░░░░░░░  ║
  ║   Closed Won            6      $7,200       25          100%        █░░░░░░░░░  ║
  ║   ──────────────────────────────────────────────────────────────────────        ║
  ║   TOTAL               484      $2,850       12 (avg)     18%                   ║
  ║                                                                                  ║
  ║   ┌─── REVENUE FORECAST ──────────────────────────────────────────────────┐    ║
  ║   │                                                                       │    ║
  ║   │   This Month    $18,400  ████████████████████░░░░░░░░░░░░  74% of $25K│   ║
  ║   │   Next Month    $24,100  ██████████████████████████░░░░░░  96% of $25K│   ║
  ║   │   Q4 Target     $75,000  ████████████████████░░░░░░░░░░░░  32% of $75K│   ║
  ║   │                                                                       │    ║
  ║   └───────────────────────────────────────────────────────────────────────┘    ║
  ╚══════════════════════════════════════════════════════════════════════════════════╝
```

---

## § 16. REGIONAL DASHBOARD (ASCII Visual)

```
  ╔══════════════════════════════════════════════════════════════════════════════════╗
  ║                        🌍 REGIONAL PERFORMANCE                                   ║
  ║                        GA Period: 2026-09-20 → 2026-10-17                       ║
  ╠══════════════════════════════════════════════════════════════════════════════════╣
  ║                                                                                  ║
  ║   COUNTRY          USERS   ENGAGEMENT   REVENUE    CHANNEL MIX                  ║
  ║   ─────────────────────────────────────────────────────────────────             ║
  ║   🇺🇸 United States  124     28.8%        $12,400   ████ LinkedIn               ║
  ║                                       ████████░░  ███ Email                    ║
  ║                                                     ██ YouTube                  ║
  ║                                                                                  ║
  ║   🇮🇳 India          15     29.4%         ₹8,200   █████ WhatsApp              ║
  ║                                       ██████░░░░  ███ Email                    ║
  ║                                                     ██ LinkedIn                 ║
  ║                                                                                  ║
  ║   🇸🇬 Singapore       3     66.7%★        $3,100   █████ Email                 ║
  ║                                       ██████████████ WhatsApp                 ║
  ║                                                     █ LinkedIn                  ║
  ║                                                                                  ║
  ║   🇩🇪 Germany         3      0.0%            $0    █████ LinkedIn              ║
  ║                                       ░░░░░░░░░░  ███ Email                    ║
  ║                                                                                  ║
  ║   ┌─── CITY HOTSPOTS ─────────────────────────────────────────────────────┐    ║
  ║   │                                                                       │    ║
  ║   │   Ashburn, VA      ████████████████████████████████████████  35       │    ║
  ║   │   San Jose, CA     ███████████████████░░░░░░░░░░░░░░░░░░░░  17       │    ║
  ║   │   Des Moines, IA   ██████████████░░░░░░░░░░░░░░░░░░░░░░░░░  13       │    ║
  ║   │   Flint Hill, VA   ██████████████░░░░░░░░░░░░░░░░░░░░░░░░░  13       │    ║
  ║   │   Los Angeles, CA  ████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░  12       │    ║
  ║   │   Hyderabad, IN    ██████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  10  ★    │    ║
  ║   │   New York, NY     █████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   9       │    ║
  ║   │   Pune, IN         ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   3  ★    │    ║
  ║   │   Singapore, SG    ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   3  ★    │    ║
  ║   │   Gutersloh, DE    ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   2       │    ║
  ║   │                                                                       │    ║
  ║   └───────────────────────────────────────────────────────────────────────┘    ║
  ╚══════════════════════════════════════════════════════════════════════════════════╝
```

---

## § 17. AI COST DASHBOARD (ASCII Visual)

```
  ╔══════════════════════════════════════════════════════════════════════════════════╗
  ║                        🤖 AI COST OPTIMIZATION                                   ║
  ║                        Budget: $5.00/mo · Spent: $3.12 · Remaining: $1.88       ║
  ╠══════════════════════════════════════════════════════════════════════════════════╣
  ║                                                                                  ║
  ║   COST-TIER ROUTING STRATEGY                                                     ║
  ║   ─────────────────────────                                                      ║
  ║                                                                                  ║
  ║   TASK                TIER      MODEL              COST/1K    CALLS/mo  SPEND   ║
  ║   ──────────────────────────────────────────────────────────────────────────    ║
  ║   Chat classify       NANO      qwen2.5:0.5b       $0.0002    2,000     $0.40   ║
  ║   Contact tag         NANO      qwen2.5:0.5b       $0.0002    1,500     $0.30   ║
  ║   Entity extract      NANO      qwen2.5:0.5b       $0.0002    1,000     $0.19   ║
  ║   ──────────────────────────────────────────────────────────────────────────    ║
  ║   Summarize           SMALL     qwen2.5:3b         $0.001     800       $0.72   ║
  ║   Format quotes       SMALL     qwen2.5:3b         $0.001     500       $0.45   ║
  ║   ──────────────────────────────────────────────────────────────────────────    ║
  ║   Trend analysis      MEDIUM    llama3.1:8b        $0.002     400       $0.65   ║
  ║   Lead scoring        MEDIUM    llama3.1:8b        $0.002     300       $0.48   ║
  ║   ──────────────────────────────────────────────────────────────────────────    ║
  ║   Quote generation    LARGE     gemini-2-flash     $0.004     200       $0.42   ║
  ║   Campaign writing    LARGE     gemini-2-flash     $0.004     100       $0.16   ║
  ║   ──────────────────────────────────────────────────────────────────────────    ║
  ║   Complex quotes      XL        gemini-2.5-pro     $0.012     30        $0.28   ║
  ║   ──────────────────────────────────────────────────────────────────────────    ║
  ║                                    TOTAL                            $3.12       ║
  ║                                                                                  ║
  ║   ┌─── COST AVOIDANCE (Local SLM Savings) ─────────────────────────────────┐    ║
  ║   │                                                                        │    ║
  ║   │   If all tasks ran on gemini-2.5-pro:  ~$48.00/mo                     │    ║
  ║   │   Actual spend (hybrid routing):       $3.12/mo                       │    ║
  ║   │   ─────────────────────────────────────────────                       │    ║
  ║   │   💰 SAVINGS: $44.88/mo (93.5%)                                       │    ║
  ║   │                                                                        │    ║
  ║   │   Local SLM handled: 78% of all calls (4,500/5,730)                  │    ║
  ║   │   Cloud LLM handled: 22% of all calls (1,230/5,730)                  │    ║
  ║   │                                                                        │    ║
  ║   └────────────────────────────────────────────────────────────────────────┘    ║
  ╚══════════════════════════════════════════════════════════════════════════════════╝
```

---

## § 18. CAMPAIGN DASHBOARD (ASCII Visual)

```
  ╔══════════════════════════════════════════════════════════════════════════════════╗
  ║                        📧 CAMPAIGN PERFORMANCE                                   ║
  ║                        Active: 3 · Completed: 12 · Scheduled: 5                  ║
  ╠══════════════════════════════════════════════════════════════════════════════════╣
  ║                                                                                  ║
  ║   CAMPAIGN                    CHANNEL   AUDIENCE   SENT    OPEN%   REPLY%  STATUS ║
  ║   ───────────────────────────────────────────────────────────────────────────── ║
  ║   US Procurement Blitz        LinkedIn  500        220     40%     11.4%  ● Live ║
  ║   India South WhatsApp        WhatsApp  300        280     71%     20.0%  ● Live ║
  ║   Singapore Follow-up         Email     3          3       100%    33.3%  ● Live ║
  ║   Pre-Season Packaging        Email     200        —       —       —      ○ Sched ║
  ║   Germany Test Market         LinkedIn  100        —       —       —      ○ Sched ║
  ║   ───────────────────────────────────────────────────────────────────────────── ║
  ║                                                                                  ║
  ║   ┌─── TOP PERFORMING CAMPAIGN ────────────────────────────────────────────┐    ║
  ║   │                                                                        │    ║
  ║   │   "India South WhatsApp"                                              │    ║
  ║   │   • Sent: 280 · Delivered: 274 (97.9%)                               │    ║
  ║   │   • Read: 198 (72.3%) · Replied: 56 (20.7%)                          │    ║
  ║   │   • Quotes generated: 12 · Deals closed: 4                           │    ║
  ║   │   • Revenue: ₹2,40,000                                               │    ║
  ║   │                                                                        │    ║
  ║   │   Response time: <2 hours (AI auto-reply + human approval)           │    ║
  ║   │                                                                        │    ║
  ║   └────────────────────────────────────────────────────────────────────────┘    ║
  ║                                                                                  ║
  ║   ┌─── A/B TEST RESULTS ───────────────────────────────────────────────────┐    ║
  ║   │                                                                        │    ║
  ║   │   Subject Line A: "Bulk packaging rates for Q4"                       │    ║
  ║   │   → Open: 38% · Reply: 8.2%                                          │    ║
  ║   │                                                                        │    ║
  ║   │   Subject Line B: "Save 15% on tarpaulin — limited stock"             │    ║
  ║   │   → Open: 52% · Reply: 14.7% ★ WINNER                                │    ║
  ║   │                                                                        │    ║
  ║   │   Winner auto-promoted to full audience via scheduler                 │    ║
  ║   │                                                                        │    ║
  ║   └────────────────────────────────────────────────────────────────────────┘    ║
  ╚══════════════════════════════════════════════════════════════════════════════════╝
```

---

## § 19. KPIs — MASTER TABLE

### 19.1 — Revenue KPIs

| KPI | Current | Target (Q4) | Target (Q1 2027) | Source |
|---|---|---|---|---|
| Monthly Revenue | $18,400 | $25,000 | $50,000 | Cloud SQL |
| Avg Deal Size | $2,850 | $3,500 | $5,000 | Cloud SQL |
| Pipeline Value | $124,500 | $200,000 | $400,000 | Cloud SQL |
| Quote-to-Close Rate | 21% | 30% | 35% | Analytics |
| Reorder Rate | 12% | 15% | 25% | Predictive model |
| Customer LTV | $8,500 | $12,000 | $18,000 | CRM history |

### 19.2 — Outreach KPIs

| KPI | Current | Target | Source |
|---|---|---|---|
| Email Delivery Rate | 96.0% | 98% | SMTP logs |
| Email Open Rate | 38.4% | 45% | IMAP tracking |
| WhatsApp Delivery Rate | 97.9% | 99% | Cloud API |
| WhatsApp Read Rate | 72.3% | 80% | Cloud API |
| LinkedIn Reply Rate | 11.4% | 15% | API |
| Overall Reply Rate | 14.3% | 20% | Campaign tables |
| Avg Response Time | 2 hours | 30 min | Scheduler logs |

### 19.3 — Data KPIs

| KPI | Current | Target | Source |
|---|---|---|---|
| Total Contacts | 5,200 | 10,000 | Cloud SQL |
| Enriched Contacts | 60% | 90% | Analytics |
| Duplicate Rate | 8% | <2% | Dedup engine |
| PII Redaction Coverage | 100% | 100% | Governance |
| GCS Data Freshness | <24h | <1h | Cloud Function |
| Chat Sync Completeness | 85% | 99% | Cloud Function |

### 19.4 — AI/LLM KPIs

| KPI | Current | Target | Source |
|---|---|---|---|
| Monthly AI Spend | $3.12 | <$5.00 | Token ledger |
| Local SLM Routing | 78% | 85% | LLM router |
| Avg Latency (NANO) | 120ms | <100ms | Router metrics |
| Avg Latency (LARGE) | 2.1s | <1.5s | Router metrics |
| Budget Utilization | 62.4% | <80% | Budget tracker |
| Cost Avoidance | $44.88 | $60.00 | Comparison calc |

### 19.5 — Operational KPIs

| KPI | Current | Target | Source |
|---|---|---|---|
| Uptime | 99.9% | 99.95% | Cloud Run |
| Avg Response Time (API) | 180ms | <150ms | Cloud Monitoring |
| Scheduler Job Success | 98% | 99.9% | Scheduler logs |
| Audit Log Coverage | 100% | 100% | Governance |
| PII Incidents | 0 | 0 | Security module |
| Cloud SQL Connections | <20 | <50 | Cloud SQL |

---

## § 20. INTEGRATION STATUS

| Integration | Status | Auth Method | Last Verified |
|---|---|---|---|
| Google Analytics | ✅ Data exported (CSV) | Manual export → GCS | 2026-10-18 |
| GCS (contacts) | ✅ Active | ADC (Cloud Run SA) | 2026-10-18 |
| Gmail SMTP/IMAP | ✅ Active | App password | 2026-10-18 |
| Google Sign-In | ✅ Active | OAuth 2.0 | 2026-10-18 |
| LinkedIn | ✅ Active | Google ADC | 2026-10-18 |
| Reddit | ✅ Active | Google ADC | 2026-10-18 |
| YouTube Data API v3 | ✅ Active | Google ADC | 2026-10-18 |
| WhatsApp Cloud API | ⚙️ Configurable | API key + phone number ID | — |
| Wechaty Gateway | ⚙️ Configurable | Node.js sidecar + token | — |
| Google Gemini | ⚙️ Configurable | API key | — |
| Ollama (local SLM) | ⚙️ Configurable | Local URL | — |
| Cloud SQL (PostgreSQL) | ✅ Active | Secret Manager | 2026-10-18 |
| Redis | ⚙️ Configurable | URL | — |

---

## § 21. GROWTH ROADMAP

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │                    GROWTH ROADMAP — 4 QUARTERS                        │
  └──────────────────────────────────────────────────────────────────────┘

  Q4 2026 (NOW)              Q1 2027                Q2 2027                Q3 2027
  ─────────────              ───────                ───────                ───────
  ┌──────────────┐          ┌──────────────┐       ┌──────────────┐       ┌──────────────┐
  │ FOUNDATION   │          │ EXPANSION    │       │ OPTIMIZATION │       │ SCALE        │
  │              │          │              │       │              │       │              │
  │ ✓ Cloud Run  │          │ • Multi-     │       │ • Predictive │       │ • Multi-     │
  │ ✓ GCS sync   │    ──►   │   language   │  ──►  │   reorder    │  ──►  │   tenant     │
  │ ✓ Basic CRM  │          │ • WhatsApp   │       │ • A/B testing│       │ • Mobile app │
  │ ✓ Email      │          │   Cloud API  │       │ • Advanced   │       │ • API        │
  │ ✓ LinkedIn   │          │ • Germany    │       │   analytics  │       │   marketplace│
  │              │          │   market     │       │ • BigQuery   │       │ • ERP        │
  │ Revenue:     │          │              │       │   warehouse  │       │   integration│
  │ $25K/mo      │          │ Revenue:     │       │              │       │              │
  │              │          │ $50K/mo      │       │ Revenue:     │       │ Revenue:     │
  │              │          │              │       │ $75K/mo      │       │ $150K/mo     │
  └──────────────┘          └──────────────┘       └──────────────┘       └──────────────┘

  KEY MILESTONES
  ──────────────
  Q4 2026:  ✓ Live on Cloud Run · ✓ GCS pipeline · ✓ Basic outreach
  Q1 2027:  ○ WhatsApp Cloud API live · ○ Germany market entry · ○ Multi-language
  Q2 2027:  ○ Predictive reorder engine · ○ A/B testing framework · ○ BigQuery
  Q3 2027:  ○ Mobile PWA · ○ ERP deep integration · ○ API marketplace
```

---

## § 22. OCT-ROADMAP DATA PIPELINE

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │              OCT-ROADMAP PROCESSING PIPELINE                         │
  └──────────────────────────────────────────────────────────────────────┘

  [Source]                    [Process]                   [Output]
  ─────────                   ─────────                   ────────

  ┌──────────────────┐
  │ Oct-Roadmap.xlsx │
  │ (8 sheets)       │
  │ 145 data rows    │
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │  PREPROCESSING ENGINE (Python + openpyxl)                        │
  │                                                                  │
  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐    │
  │  │ Sheet Parser   │  │ Stats          │  │ Client         │    │
  │  │ (8 sheets)     │  │ Extractor      │  │ Classifier     │    │
  │  │                │  │                │  │                │    │
  │  │ High Level     │  │ 66 metrics     │  │ Kalika →       │    │
  │  │ Sales-info     │  │ 29 KPIs        │  │   kalika_      │    │
  │  │ CRM question   │  │ 33 features    │  │   enterprises  │    │
  │  │ Kalika_Erp_Feat│  │ 19 questions   │  │                │    │
  │  │ gcs paths      │  │ 18 team tasks  │  │ AG-Vision →    │    │
  │  │ sales stories  │  │ 13 accounting  │  │   kalisoftai_  │    │
  │  │ accounting     │  │  92 AG objects │  │   client_data  │    │
  │  │ Marketing      │  │                │  │                │    │
  │  └────────────────┘  └────────────────┘  └────────────────┘    │
  └──────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │  OUTPUT: Oct-Roadmap-Processed.xlsx                               │
  │                                                                  │
  │  8 Sheets:                                                       │
  │  ┌────────────────────┬───────┬──────────────────────────────┐  │
  │  │ Sheet              │ Rows  │ Content                       │  │
  │  ├────────────────────┼───────┼──────────────────────────────┤  │
  │  │ Executive Summary  │ 66    │ All metrics by category       │  │
  │  │ Kalika ERP Features│ 33+12 │ Features + module summary     │  │
  │  │ CRM Evaluation     │ 19    │ Zoho questions (4 groups)     │  │
  │  │ GCS Bucket Map     │ 22    │ Object routing + status       │  │
  │  │ Team & Workflows   │ 18    │ 9 members, assignments        │  │
  │  │ Accounting         │ 13    │ Tally migration requirements  │  │
  │  │ AG-Vision Client   │ 10    │ SAP modules + placements      │  │
  │  │ Stats Dashboard    │ 29    │ KPIs with ASCII bar charts    │  │
  │  └────────────────────┴───────┴──────────────────────────────┘  │
  └──────────────────────────┬───────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
  ┌─────────────────────────┐ ┌─────────────────────────┐
  │ kalika_enterprises      │ │ kalisoftai_client_data  │
  │                         │ │                         │
  │ sales-2025-27/          │ │ AG-Vision/              │
  │   Oct-Roadmap.xlsx      │ │   Oct-Roadmap-Processed │
  │   (source, 282 KB)      │ │   .xlsx (20 KB)         │
  │                         │ │                         │
  │ ERP-V1/                 │ │                         │
  │   Oct-Roadmap-          │ │                         │
  │   Processed.xlsx        │ │                         │
  │   (20 KB)               │ │                         │
  └─────────────────────────┘ └─────────────────────────┘
```

### 22.1 — Source Sheet Breakdown

| # | Sheet | Rows | Content | Client |
|---|---|---|---|---|
| 1 | High Level Tasks | 42 | APIs, ERP, meetings, GCS paths, ZOHO CRM | Kalika |
| 2 | Sales-info | ~20 | LinkedIn leads (Lesley, Kea — South Africa), sales intent | Kalika |
| 3 | CRM question | 27 | 19 Zoho CRM evaluation questions (4 categories) | Kalika |
| 4 | Kalika_Erp_Feat | 33 | ERP features across 12 modules (all LIVE) | Kalika |
| 5 | gcs folder paths | 8 | 7 quotation paths in `kalisoftai-official-docs` | KalisoftAI |
| 6 | sales stories | 15 | Workflows, team assignments, catalog references | Kalika |
| 7 | kalika accounting | 3 | Tally requirements, payment alerts, invoice lifecycle | Kalika |
| 8 | Marketing | 2 | Google Reviews, Google Analytics | Kalika |

### 22.2 — Key Stats Extracted

```
  ╭──────────────────────────────────────────────────────────────────╮
  │  OCT-ROADMAP — KEY NUMBERS                                       │
  ╰──────────────────────────────────────────────────────────────────╯

  SOURCE DATA
  ───────────
  Sheets:              8
  Non-empty rows:      145
  Unique team members: 9

  KALIKA ERP
  ──────────
  Features:            33 (100% LIVE)
  Modules:             12
  Top modules:         Master Data (5), Sales (4), Procurement (4),
                       Inventory (4), Production (4)

  CRM EVALUATION
  ──────────────
  Total questions:     19
  Categories:          4 (Core CRM, Integrations, Sales/Acct, Security)

  SALES
  ─────
  LinkedIn leads:      2 (Lesley Mncina, Kea Mokhongane — South Africa)
  Lead rate:           ZAR 250/hr (~$15, ~INR 1,441)
  Sales stories:       15 workflows
  Catalog sets:        3

  ACCOUNTING
  ──────────
  Current software:    Tally
  Payment alert types: 2 (incoming + outgoing)
  Invoice lifecycle:   4 stages (Created → Due → Pending → Completed)
  Team:                Vaishnavi (lead), Ganesh (reconciliation)

  MEETINGS
  ────────
  Daily morning:       10:30 AM (Tejaswini)
  Daily evening:       4:00 PM (team)
  ERP weekly:          10:00-11:00 AM (Jaideep, Pooja, Tejaswini)

  GCS QUOTATIONS
  ──────────────
  Quotation paths:     7
  Bucket:              kalisoftai-official-docs/Quotations/
```

### 22.3 — ERP Module Feature Distribution

```
  Module             Features    Bar
  ──────────────────────────────────────────────────────
  Master Data        5           ████████████████████
  Sales              4           ████████████████
  Procurement        4           ████████████████
  Inventory          4           ████████████████
  Production         4           ████████████████
  Dashboard          3           ████████████
  Dispatch           2           ████████
  Reports            2           ████████
  Authentication     1           ████
  Planning           1           ████
  Alerts             1           ████
  Data Import        1           ████
  Audit              1           ████
  ──────────────────────────────────────────────────────
  TOTAL              33          100% LIVE
```

---

## § 23. CLIENT DATA ROUTING — KALIKA vs AG-VISION

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │                    CLIENT DATA ROUTING MAP                           │
  └──────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────┐
                    │   Oct-Roadmap.xlsx      │
                    │   (8 sheets, mixed)     │
                    └───────────┬─────────────┘
                                │
                    ┌───────────┴─────────────┐
                    │   CLIENT CLASSIFIER      │
                    │                          │
                    │  Kalika?    AG-Vision?   │
                    │  ERP, Sales, Accounting  │  SAP, Placements
                    │  Contacts, Marketing     │  Curriculum, Roadmap
                    └───────┬─────────┬───────┘
                            │         │
              ┌─────────────▼──┐   ┌──▼──────────────────┐
              │ KALIKA ENTERPRISES│   │ KALISOFTAI_CLIENT_DATA│
              │ (kalika_enterprises)│ │ /AG-Vision/           │
              │                 │   │                       │
              │ Existing:       │   │ Existing:             │
              │  ERP-V1/ (8)    │   │  92 objects           │
              │  Contacts/ (9)  │   │  34.9 MB              │
              │  sales-contacts/│   │                       │
              │  docs/ (5)      │   │ SAP Modules:          │
              │  images/ (13)   │   │  ABAP, HCM, PP,       │
              │  sales-2025-27/ │   │  SD, MM, FICO         │
              │                 │   │                       │
              │ NEW UPLOADS:    │   │ NEW UPLOADS:          │
              │  sales-2025-27/ │   │  AG-Vision/           │
              │   Oct-Roadmap   │   │   Oct-Roadmap-        │
              │   .xlsx (282KB) │   │   Processed.xlsx      │
              │                 │   │   (20 KB)             │
              │  ERP-V1/        │   │                       │
              │   Oct-Roadmap-  │   │                       │
              │   Processed     │   │                       │
              │   .xlsx (20KB)  │   │                       │
              └─────────────────┘   └───────────────────────┘
```

### 23.1 — Kalika Enterprises (kalika_enterprises)

| Prefix | Objects | Size | Content | Updated |
|---|---|---|---|---|
| `ERP-V1/` | **9** | 94.5 MB | Catalog, SOP, ERP docs + **new processed roadmap** | 2026-10-18 |
| `Contacts/` | 9 | 33.4 MB | WhatsApp chats, VCF contacts | 2026-09-03 |
| `sales-contacts/` | 7 | 14.5 MB | Contact spreadsheets | 2026-09-03 |
| `images and videos/` | 13 | 14.2 MB | Product/media files | 2026-10-05 |
| `docs/` | 9 | 2.2 MB | Invoices, logos, GA reports | 2026-09-06 |
| `sales-2025-27/` | **3** | 0.4 MB | GST invoices + **updated roadmap** | 2026-10-18 |
| Root files | 2 | 4.7 MB | Catalog PDFs | 2026-09-03 |

### 23.2 — AG-Vision (kalisoftai_client_data/AG-Vision/)

| Category | Items | Size | GCS Path |
|---|---|---|---|
| SAP S/4HANA ABAP | Curriculum + Roadmap PDFs | 1.7 MB | `AG-Vision/` |
| SAP S/4HANA HCM (HR) | Curriculum + Roadmap PDFs | 2.7 MB | `AG-Vision/` |
| SAP S/4HANA PP | Curriculum + Roadmap PDFs | 1.7 MB | `AG-Vision/` |
| SAP S/4HANA SD | Curriculum + Roadmap PDFs | 1.7 MB | `AG-Vision/` |
| SAP S/4HANA MM | Curriculum + Roadmap PDFs | 1.7 MB | `AG-Vision/` |
| SAP S/4HANA FICO | Curriculum + Roadmap PDFs | 1.8 MB | `AG-Vision/` |
| Main data | AG VISION data.xlsx | 10.4 MB | `AG-Vision/` |
| Image catalog | new-ag-images.xlsx | 10.3 MB | `AG-Vision/` |
| Placements | 80 student photos | ~5 MB | `AG-Vision/placements/` |
| **NEW: Processed roadmap** | **Oct-Roadmap-Processed.xlsx** | **20 KB** | `AG-Vision/` |
| **TOTAL** | **93 objects** | **34.9 MB** | |

### 23.3 — AG-Vision SAP Module Coverage

```
  ┌──────────────────────────────────────────────────────────────────┐
  │  AG-VISION — SAP S/4HANA MODULE MAP                              │
  └──────────────────────────────────────────────────────────────────┘

  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │  ABAP        │  │  HCM (HR)    │  │  PP          │
  │  ──────────  │  │  ──────────  │  │  ──────────  │
  │  Curriculum  │  │  Curriculum  │  │  Curriculum  │
  │  Roadmap     │  │  Roadmap     │  │  Roadmap     │
  │  1.7 MB      │  │  2.7 MB      │  │  1.7 MB      │
  └──────────────┘  └──────────────┘  └──────────────┘
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │  SD          │  │  MM          │  │  FICO        │
  │  ──────────  │  │  ──────────  │  │  ──────────  │
  │  Curriculum  │  │  Curriculum  │  │  Curriculum  │
  │  Roadmap     │  │  Roadmap     │  │  Roadmap     │
  │  1.7 MB      │  │  1.7 MB      │  │  1.8 MB      │
  └──────────────┘  └──────────────┘  └──────────────┘

  6 modules × 2 PDFs each = 12 PDFs (~11.3 MB)
  + 80 placement photos (~5 MB)
  + 2 data files (~20.7 MB)
  = 93 objects, 34.9 MB total
```

---

## § 24. GCS UPLOAD LOG

```
  ╔══════════════════════════════════════════════════════════════════════════════════╗
  ║  GCS UPLOAD LOG — 2026-10-18 10:07 UTC                                         ║
  ╠══════════════════════════════════════════════════════════════════════════════════╣
  ║                                                                                  ║
  ║  #  BUCKET                  PATH                              SIZE    CLIENT     ║
  ║  ────────────────────────────────────────────────────────────────────────────   ║
  ║  1  kalika_enterprises      sales-2025-27/Oct-Roadmap.xlsx   282 KB  Kalika    ║
  ║  2  kalika_enterprises      ERP-V1/Oct-Roadmap-Processed     20 KB   Kalika    ║
  ║                              .xlsx                                                   ║
  ║  3  kalisoftai_client_data  AG-Vision/Oct-Roadmap-Processed  20 KB   AG-Vision ║
  ║                              .xlsx                                                   ║
  ║                                                                                  ║
  ║  Metadata attached to each object:                                               ║
  ║    source        = Oct-Roadmap.xlsx                                              ║
  ║    processed_by  = KalisoftAI Sales Pipeline                                     ║
  ║    client        = Kalika | AG-Vision                                            ║
  ║    uploaded_at   = 2026-10-18T10:07:14Z                                          ║
  ║    description   = Processed roadmap with stats + KPIs                           ║
  ║                                                                                  ║
  ╚══════════════════════════════════════════════════════════════════════════════════╝
```

| # | Bucket | Destination | Size | Client | Status |
|---|---|---|---|---|---|
| 1 | `kalika_enterprises` | `sales-2025-27/Oct-Roadmap.xlsx` | 282 KB | Kalika | ✅ Uploaded |
| 2 | `kalika_enterprises` | `ERP-V1/Oct-Roadmap-Processed.xlsx` | 20 KB | Kalika | ✅ Uploaded |
| 3 | `kalisoftai_client_data` | `AG-Vision/Oct-Roadmap-Processed.xlsx` | 20 KB | AG-Vision | ✅ Uploaded |

### Local Artifacts

| File | Path | Size | Purpose |
|---|---|---|---|
| `Oct-Roadmap.xlsx` | `data/all-metadata/` | 282 KB | Source (user-updated) |
| `Oct-Roadmap-Processed.xlsx` | `data/all-metadata/` | 20 KB | Processed (8 sheets, 66 metrics) |

---

```
  ╔══════════════════════════════════════════════════════════════════════════════════╗
  ║  DOCUMENT INFO                                                                   ║
  ║  ─────────────                                                                   ║
  ║  File      : data/all-metadata/SALES_LEAD_METADATA.md                           ║
  ║  Project   : gen-lang-client-0132243782                                          ║
  ║  Branch    : feature/oct-roadmap-metadata                                        ║
  ║  Service   : kalisoft-sales (Cloud Run, asia-south1)                            ║
  ║  Author    : KalisoftAI Engineering                                              ║
  ║  Updated   : 2026-10-18                                                         ║
  ║  Version   : 3.0 (added §22-24: Oct-Roadmap pipeline, client routing, GCS log)  ║
  ║                                                                                  ║
  ║  RELATED FILES:                                                                  ║
  ║    data/all-metadata/Oct-Roadmap.xlsx           (source, 282 KB)                ║
  ║    data/all-metadata/Oct-Roadmap-Processed.xlsx (processed, 20 KB, 8 sheets)    ║
  ║                                                                                  ║
  ║  GCS UPLOADS:                                                                    ║
  ║    gs://kalika_enterprises/sales-2025-27/Oct-Roadmap.xlsx                      ║
  ║    gs://kalika_enterprises/ERP-V1/Oct-Roadmap-Processed.xlsx                   ║
  ║    gs://kalisoftai_client_data/AG-Vision/Oct-Roadmap-Processed.xlsx            ║
  ╚══════════════════════════════════════════════════════════════════════════════════╝
```
