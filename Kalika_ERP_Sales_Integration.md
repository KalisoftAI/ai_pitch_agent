# Kalika ERP × Sales Pipeline — Integration Spec (30-Oct-2026)

> Scope: daily ERP report sync (Dispatch + Orders) into the sales app, sales forecasting, rate calculator,
> GA-style operational dashboard, admin/user access model, YouTube Data API settings, and future stories.
> **ERP system (`D:\KaliSoftAI\ERP-System`, deployed branch `master`) is NOT modified** — we only read its
> published GCS report. The live ERP UI/UX for Kalika users is untouched.

---

## 1. Source of truth

| Type of data | GCS path | File / subdirectory |
|---|---|---|
| ERP app delivery data | `gs://kalika_enterprises/ERP-V1/Reports` | `Dispatch`, `Orders`, `Production`, `Inventory` sheets |
| Contacts | `gs://kalika_enterprises/sales-contacts` | marketing list, pune region, Sales-data |
| WhatsApp backups | `gs://kalika_enterprises/kalika backup` | 48 chat exports |
| Sales registers | `gs://kalika_enterprises/kalika_sales2026` | 9 monthly Tally exports |
| Feedback system | `gs://kalika_enterprises/sales-metadata` | `Kalika_Real_Time_Customer_Feedback_System.md` |

---

## 2. Daily sync flow (ASCII)

```text
 ERP app (branch: master, untouched)
      │ publishes daily
      v
 gs://kalika_enterprises/ERP-V1/Reports/kalika_report_YYYY-MM-DD.xlsx
      │
      │  cron 0 6 * * *   (erp_dispatch_sync)
      v
 POST /api/erp/sync  (admin only)
      │  parse: Dispatch + Orders sheets
      v
 sales_pipeline.db: erp_dispatch (per report_date) · erp_orders (per report_date) · sync_runs audit
      │
      +--> GET /api/erp/status      KPIs + last sync
      +--> GET /api/erp/analytics   funnel, top customers, plants, pending follow-up (GA-style)
      +--> GET /api/erp/dispatch    filterable table
      +--> GET /api/erp/forecast    monthly series + next-month projection
      +--> POST /api/erp/rate-calculator  film costing
      +--> GET/PUT /api/erp/settings     YouTube key + channel (admin)
      +--> POST /api/erp/youtube/sync    channel stats (Data API v3)
```

---

## 3. Subtask breakdown

| # | Subtask | Status | Detail |
|---|---|---|---|
| 1 | DB tables for ERP mirror | DONE | `erp_dispatch`, `erp_orders` (unique per report_date+no), `integration_settings`, `sync_runs` |
| 2 | Report loader (local mirror → GCS fallback) | DONE | `sales_fastapi/erp_sync.py::load_report` |
| 3 | Idempotent upsert sync + audit | DONE | `sync_erp_report()`; re-run updates instead of duplicating |
| 4 | Read API (status/analytics/dispatch/orders/forecast) | DONE | 5 endpoints, auth required, company-wide data |
| 5 | Rate calculator | DONE | weight = w × l × micron/1000 × density ; price = (material + conversion) × (1+margin) |
| 6 | Admin guard | DONE | `require_admin` → ADMIN_EMAILS (default `ai.solutions@kalisoftai.in`) |
| 7 | YouTube Data API sync + manual key entry | DONE | key stored in `integration_settings` (DB) or env; Data API v3 channels endpoint |
| 8 | Crons | DONE | `erp_dispatch_sync 0 6 * * *`, `youtube_channel_sync 0 7 * * *` |
| 9 | UI page "ERP & forecast" (admin + user views) | DONE | KPIs, funnel, forecast bars, dispatch table, calculator, YouTube card |
| 10 | Mobile refinement + ERP-aligned design | DONE | Inter font, amber brand `#f59e0b`, 18px card radius, hover lift, mobile breakpoints |
| 11 | YouTube Analytics API (OAuth) | NEXT | needs OAuth consent + refresh token storage |
| 12 | Graph/RL patterns from ERP events | NEXT | see §6 |

---

## 4. Access model

| Role | Who | Can |
|---|---|---|
| Admin | `ai.solutions@kalisoftai.in` (ADMIN_EMAILS) | everything: sync ERP, manage YouTube keys, all reads |
| Field executive / sales | any authenticated Kalika user | read dashboards, dispatch, forecast, calculator (read-only) |
| ERP users | existing ERP app users | **untouched** — they keep using the ERP app on `master` |

Verified: non-admin `POST /api/erp/sync` → `403`; `GET /api/erp/status` → `is_admin: false` with full read data.

---

## 5. Current numbers (live, after first sync)

| Metric | Value |
|---|---|
| Report date | 2026-10-30 |
| Dispatch records | 117 (73 Completed · 44 Partially Dispatched) |
| Scheduled / dispatched qty | 69,538 / 46,405 (66.7%) |
| Customers served | 52 |
| Orders | 89 · ₹94.83 L |
| Pending follow-up | 44 |
| Top customer by dispatch qty | WHITE POLLY (7,473) |
| Rate calculator example | 500 mm × 1000 m × 23 µm @ ₹92/kg → 10.58 kg, cost ₹1,187.08, price ₹1,282.04 (₹118.8/kg) |
| YouTube | not configured yet (admin adds key + channel; daily 07:00 sync) |

---

## 6. Future scope — graph + reinforcement-learning patterns

Every action (sync, message sent, reply, dispatch completed) can be written as an event node in the
preprocessing graph and exported as JSON metadata:

```json
{
  "event_id": "evt_20261030_001",
  "type": "dispatch_progress",
  "context": {"customer": "WHITE POLLY", "order_no": "LOC-...", "completion_pct": 66.7},
  "action": {"template": "WA-DSP-01", "channel": "whatsapp"},
  "outcome": {"reply": "yes", "order_repeated": true},
  "reward": 1.0,
  "metadata": {"model": "gemma-4-27b-it|gemini-2.5-flash", "human_reviewed": true, "graph_version": "v1"}
}
```

```text
 events (JSON metadata) ──> networkx graph (nodes/edges) ──> outcome labelling ──> RL pattern mining
        │                                                        │
        └──────────── human review gate (admin) ─────────────────┘
```

Deliverable next: `gcs_data/graph/events.jsonl` accumulating these records + periodic pattern reports
(template → reply → repeat-order lift), surfaced as "stories" in the UI.

---

## 7. UI feature stories (tracked in app)

| Story | Status | Where |
|---|---|---|
| See today's dispatch completion at a glance | DONE | ERP & forecast → KPI strip |
| See pending dispatches to follow up | DONE | KPI "Pending dispatch" + table filter |
| Forecast next month's order value | DONE | Forecast bars + projection |
| Quick film costing for a quote | DONE | Rate calculator |
| Admin pulls the latest ERP data on demand | DONE | "Sync ERP now" (admin) |
| Admin configures YouTube, sees channel stats | DONE | Channel sync card |
| Field executive sees same data, no write buttons | DONE | role-based UI |
| YouTube Analytics (watch time, traffic) | NEXT | OAuth flow |
| RL-driven "best next action" suggestions | NEXT | graph + event metadata |
| Mobile push summary of dispatch slippage | NEXT | notifications |

---

## 8. Cost notes (cost-effective dataflow)

- No extra infra: same FastAPI/SQLite/Cloud Run; ERP report parsed in-process.
- GCS reads: one workbook per day (~60 KB) — negligible egress.
- LLM use is opt-in per action; default deterministic templates keep cost at zero for routine sends.
- YouTube Data API: 10,000 units/day free quota; one `channels` call = 1 unit → daily sync ≈ 1 unit.
