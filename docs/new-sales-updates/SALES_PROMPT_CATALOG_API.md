# Sales Update — Read-Only Prompt Catalog API (branch `sales-update`)

## 1. What changed

A read-only JSON API now serves the reviewed sales prompt catalog. No database writes,
no GCS writes, no LLM execution, and no customer-facing send is triggered by these routes.

| File | Purpose |
|---|---|
| `backend/app/services/sales_prompt_catalog.py` | `Prompt` dataclass, catalog loader, filters, 404 lookup |
| `backend/app/data/weekly_prompts.json` | Local snapshot of the reviewed GCS prompt file (version `2026-10-30.1`) |
| `backend/app/routers/sales_prompts.py` | GET-only FastAPI router |
| `backend/app/main.py` | Router mounted under the existing `/api/v1` prefix |
| `backend/tests/self_check_sales_prompts.py` | Standalone self-check (run with `python backend/tests/self_check_sales_prompts.py`) |
| `backend/tests/test_sales_prompts.py` | Pytest coverage for JSON contract, filters, 404 and read-only behaviour |

## 2. API details

| Method | Path | Response | Notes |
|---|---|---|---|
| GET | `/api/v1/sales-prompts` | `200` JSON `{meta, prompts}` | Optional query filters: `task`, `model`, `human_review` |
| GET | `/api/v1/sales-prompts/{prompt_id}` | `200` JSON prompt | `404` with `{"detail": "Prompt '<id>' not found"}` |
| POST / PUT / PATCH / DELETE | `/api/v1/sales-prompts` | `405` | Read-only by design |

Each prompt object: `id`, `task`, `model`, `tier`, `json_mode`, `human_review`,
`template`, `variables`, `sample_input`, `expected_output`.
`meta` carries `version`, `source`, `default_model`, `fallback_chain`,
`human_review_required`, `timezone`, `total`, `catalog_size`.

Published prompts (unchanged from source): `PR-01` customer_feedback_summary,
`PR-02` journey_next_step, `PR-03` behaviour_pattern_extract,
`PR-04` weekly_prompt_refinement, `PR-05` dispatch_followup_draft.

Related existing endpoints (not modified): `GET /api/ops/prompt-samples` (local file first,
GCS fallback), `GET /api/ops/preflight`, `GET /api/ops/uat`, `GET /api/ops/logs`,
`GET /api/journey/{stories,behaviours,patterns,summary}`, `POST /api/erp/sync`,
`POST /api/ops/run-checks`, `POST /api/llm/run`.

## 3. Feature state (sales perspective)

| Feature | State | Evidence |
|---|---|---|
| ERP dispatch + orders dashboards | Enabled | `Kalika_Sales_Deploy_UAT_Runbook.md` §7 |
| Sales forecast | Enabled | same |
| Daily rate calculator | Enabled | same |
| Feedback pipeline (wa.me, human review) | Enabled | same |
| Customer journey + stories | Enabled | same |
| YouTube channel sync (Data API) | Enabled | same |
| YouTube Analytics API (OAuth) | Next scope | same |
| RL pattern suggestions | Next scope | same |
| Preflight guardrails | READY: 21 pass / 1 warn / 0 fail | same, §2 (`LLM_ENABLED=false` is the warn) |
| Human review on customer-facing sends | Required | `weekly_prompts.json` + runbook §4 |
| New read-only prompt catalog API | Implemented on this branch | self-check + pytest |
| UAT → stage → prod promotion | Pending human approval | runbook §1/§8 |

Sample KPI context (snapshot, not live): 118 quotations (₹2.17 Cr), 91 sales orders
(₹98.69 L), 125 purchase orders (₹5.26 Cr), 110 packaging lists / 68,174 kg dispatched,
201 active PRNs, 7–10 T/day extrusion. Dashboard sample: MTD ₹24,85,000, 14 pending
ASN/dispatches, 9 RFQ threads, 4 rate cards, 3 executives, 2 conversations,
last sync 2026-11-21 14:30 IST. All figures are labelled sample until verified.

## 4. Cost optimization — approaches reviewed

| Approach | Use | Cost / control posture | Human decision |
|---|---|---|---|
| Local `qwen2.5:3b` | Offline classification | No data leaves device; zero API spend | Auto for internal-only results |
| `gemini-2.0-flash` / `-lite` | Fallback JSON extraction | Small/medium tier; last fallback in `fallback_chain` | Review before send |
| `gemini-2.5-flash` | Default: classification, drafts, prompt refinement | Medium tier; default in `weekly_prompts.json` | Required for customer-facing output |
| `gemma-4-27b-it` | Outreach personalisation, feedback summary, journey next-step | Medium tier; PR-01 and PR-05 | Required |
| `gemini-2.5-pro` | Deep research, multi-section pitches | Large tier — reserve for high-value accounts | Required |

Recommended refinement (for human sign-off): keep `gemini-2.5-flash` as default, route
PR-01/PR-05 to `gemma-4-27b-it` only where personalisation justifies it, try local
`qwen2.5:3b` for PR-03-style extraction, and never let `gemini-2.5-pro` run on the daily
20:00–22:00 IST batch without explicit approval. The catalog API exposes the model and
tier so the dashboard can show these choices without changing them.

## 5. GCS paths read for context (read-only)

- `gs://kalika_enterprises/sales-metadata/weekly_prompts.json` — catalog source (downloaded)
- `gs://kalika_enterprises/sales-metadata/Kalika_CRM_Screenshots_Feature_and_Data_Extraction.md` / `.xlsx` — feature/field inventory
- `gs://kalika_enterprises/sales-metadata/Kalika_Sales_Deploy_UAT_Runbook.md` — state, guardrails, models, next scope
- `gs://kalika_enterprises/sales-metadata/Kalika_Dashboard_Summary.xlsx`, `Sales-Roadmap.xlsx` — dashboard/roadmap
- `gs://sales-crm/Sales_Intelligence_Analysis/sales_intelligence_report_knowledge_graph.md` — product/rate and lead context
- `gs://sales-crm/prompts/kalika_kali_softai_production_safe_backend_api_frontend_ui_gcs_sales_crm_automation_spec.md` — KPI/API blueprint
- `gs://sales-crm/assets/docs/Kalika_Barcode_Feature_Forecast_Tracker.xlsx` — barcode/forecast tracker
- `gs://sales-crm/assets/UI/update-kit/data/dashboard_overview_sample.json` — dashboard fixture
- Sample reference (not verified live): `gs://kalika-erp-prod-data/processed/dashboard-cache/overview_all.json`

No object was written, replaced or deleted.

## 6. Gaps found and steps for human review

1. BOPP tape unit differs between fixtures (`each` in overview JSON, `roll` in creative JSON). Preserve both; do not silently reconcile.
2. Dashboard/finance figures are sample snapshots. Verify against ERP before any external use.
3. `LLM_ENABLED=false` — set provider key and enable only after human approval.
4. YouTube Analytics OAuth and RL pattern suggestions remain next scope.
5. Lead hygiene: roughly 120+ invalid/out-of-service numbers and missing contacts in the intelligence report; clean before outreach.
6. Regional trade figures are planning assumptions, not audited quotations; keep separate from factory dashboard.
7. `gs://kalika-erp-prod-data/...` cache path needs classpath/credential verification before it is treated as live.

## 7. Verification performed

- `python backend/tests/self_check_sales_prompts.py` → passed
- `python -m pytest tests/test_sales_prompts.py -q --noconftest` → 6 passed
- `python -m py_compile` on `main.py` and the two new modules → clean

Deployment and merge to the parent branch were **not** performed; they require explicit approval and UAT.
