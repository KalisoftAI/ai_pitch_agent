# Kalisoft AI Sales Pipeline - Migrations and Feature Changelog

**Project:** Kalisoft AI Sales Pipeline  
**Production URL:** https://kalisoft-sales-19782268668.asia-south1.run.app  
**Last Updated:** 2026-11-03  
**Commit:** a16507f

---

## Deployment Status

| Environment | Status | URL |
|---|---|---|
| Production | Live | https://kalisoft-sales-19782268668.asia-south1.run.app |
| Local Dev | Running | http://127.0.0.1:8000 |

Health: /api/health returns status=healthy, env=production, database=ok, gcs_available=true

---

## Database Migrations

### Migration 0007 - Instore Visits

File: migrations/versions/0007_instore_visits.py

Columns added to company_visits:
- meet_person (VARCHAR 255)
- meet_home_location (VARCHAR 255)
- previous_discussion (TEXT)
- mail_chat_details (TEXT)
- map_location (VARCHAR 512)

### Migration 0008 - Tally and Prompt Review

File: migrations/versions/0008_tally_prompt_review.py

Tables: tally_sales (18 cols, 6 indexes), prompt_reviews (13 cols, 3 indexes)
Idempotent - safe for production databases that already auto-created these tables.

---

## Features

### Mail Desk - Client Mapping

Client directory maps emails to names and owners:
- rpatil@instorindia.com -> Instor India (R. Patil), owner neoinsights@neosapien.ai
- dhiraj.zatale@jsw.in -> JSW (Dhiraj Zatale), owner neoinsights@neosapien.ai

WhatsApp exports decoded: working_title, client_name, outcome, entities extracted.

### Field Samples - POST /api/visits/samples

Creates 3 sample visits (Kflex, Jabil, Ranjangaon MIDC). Idempotent.

### Follow-up Copy/Send

Copy button and WhatsApp link in Company History table.

### LLM Error Tagging

Tags: llm:http_404_model, llm:http_429_quota, llm:http_401_auth, llm:unavailable
Log: logs/llm_errors.log
Fallback: requested -> local SLM -> Gemma -> flash -> echo

### Rate Calculator Collapsible

calcOpen state persisted in localStorage.

---

## Token Reductions

- Mail snapshot limit: 12 -> 8
- Chat max_output_tokens: 700 -> 512
- Instore ask max_output_tokens: 900 -> 512

---

## Production Verify

curl https://kalisoft-sales-19782268668.asia-south1.run.app/api/health

---

Deployed by: ai.solutions@kalisoftai.in
Image: asia-south1-docker.pkg.dev/gen-lang-client-0132243782/sales-pipeline/kalisoft-sales:a16507f


---

## Architecture - High Level

`
[Browser / Mobile]
       |
       v
Cloud Run :8080 (FastAPI)
       |
       +--- Cloud SQL (Postgres)
       +--- GCS (contacts, mails, tally, erp)
       +--- Redis (queue, cache)
`

### Data Flow

`
WhatsApp/Gmail/IMAP
       |
       v
instore_mail.normalize()
       |
       v
insights.json  -->  GCS snapshot
       |
       v
/api/instore/*  -->  Dashboard UI
`

### Current Implementation Status

| Component | Status | Module |
|---|---|---|
| Mail desk (client mapping) | Live | instore_mail.py, routers/instore.py |
| Field samples sync | Live | routers/visits.py |
| Follow-up copy/send | Live | features.jsx |
| LLM fallback (gemma -> flash -> echo) | Live | llm/providers.py |
| Rate calculator collapse | Live | main.jsx |
| Scheduler (cron) | Live | scheduler.py |

### Future Scope

- BigQuery KPI warehouse
- Multi-tenant RLS
- Account catalog + billing
- Knowledge graph DB
- Smart mail notifications
- Mobile offline sync
