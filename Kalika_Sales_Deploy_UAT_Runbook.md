# Sales App — Deploy, Guardrails & ERP-UAT Runbook (30-Oct-2026)

> Applies to the Kalisoft AI Sales Pipeline (FastAPI + React). ERP (`D:\KaliSoftAI\ERP-System`,
> branch `master`) stays **production and untouched** — the sales app only reads its published
> GCS report. UAT runs for **one week** (until 2026-11-06) on `DEPLOY_ENV=preprod`.

---

## 1. Environments & phases

| Layer | Value | Notes |
|---|---|---|
| Sales app (this repo) | `preprod` → `stage` → `uat` → `prod` | `DEPLOY_ENV` env var |
| ERP | `prod` (`master` branch) | read-only report feed |
| UAT window | 2026-10-30 → 2026-11-06 (7 days) | `UAT_ENABLED`, `UAT_ENABLED_UNTIL` |
| Human review | required for all customer-facing sends | `HUMAN_REVIEW_REQUIRED=true` |
| Model default | `gemini-2.5-flash` (Google Flash) | `GEMINI_FLASH_MODEL`; Gemma `gemma-4-27b-it` available |

```text
 ERP prod (master)                Sales app (preprod -> stage -> uat -> prod)
   │ daily report                          │
   └──> GCS ERP-V1/Reports ──> sync ──> dashboards ──> feedback/journey ──> users
                                          │
                                    guardrail checks (20:00 IST)
                                    prompt refinement (21:00 IST)
                                    UAT digest        (22:00 IST)
```

---

## 2. Guardrail layers (all executed by `GET /api/ops/preflight`)

```text
 1 CONFIG      deploy env · secret strength · dev-login posture
 2 SECURITY    allowed hosts · CORS · body limit · PII redaction · audit log
 3 AUTH        admin emails · Google sign-in
 4 DATA        core tables · contacts loaded
 5 ERP         dispatch synced · report freshness
 6 SCHEDULER   cron registry · 20:00-22:00 IST window present
 7 LLM         enabled · flash model · gemma model · human review required
 8 UAT         window active · days left
 9 STORAGE     GCS reachability (ADC)
```

**Result form:** `pass / warn / fail` + remediation text. Ready-to-deploy = zero `fail`.

### Current result (live)

| Metric | Value |
|---|---|
| Checks | 22 total |
| Pass | **21** |
| Warn | 1 (`LLM_ENABLED=false` — set `LLM_ENABLED=true` + provider key for live AI) |
| Fail | **0** |
| Status | **READY** |

---

## 3. Daily schedule — 20:00–22:00 IST window

IST = UTC+05:30, so the window is 14:30–16:30 UTC. Crons are stored in UTC.

| Job | IST | UTC cron | Purpose |
|---|---|---|---|
| `erp_dispatch_sync` | 06:00 | `0 6 * * *` | pull ERP report → dispatch/orders tables |
| `youtube_channel_sync` | 07:00 | `0 7 * * *` | YouTube Data API stats |
| `daily_guardrail_checks` | **20:00** | `30 14 * * *` | full preflight → `sync_runs` |
| `daily_llm_prompt_refine` | **21:00** | `30 15 * * *` | prompt refinement vs last-week outcomes (human review) |
| `daily_uat_report` | **22:00** | `30 16 * * *` | UAT digest: ERP sync, journey, feedback, model usage |
| `weekly_uat_review` | Mon 20:00 | `30 14 * * 1` | weekly feature enablement + RL candidates |

Run manually: `POST /api/ops/run-checks` (admin) · `POST /api/cron/run` (queues all 17 tasks).

---

## 4. Model selection with human-verified sending

| Model | Tier | Best for | Review |
|---|---|---|---|
| `gemma-4-27b-it` | medium | outreach personalisation, feedback summaries, journey next-step | required |
| `gemini-2.5-flash` (default) | medium | fast classification, reply drafting, daily prompt refinement | required |
| `gemini-2.0-flash` / `-lite` | medium/small | fallback flash, JSON extraction | required |
| `gemini-2.5-pro` | large | deep research synthesis, multi-section pitches | required |
| local `qwen2.5:3b` | small | offline classification (no data leaves device) | auto |

Flow: user picks task + model → `POST /api/llm/run` (guardrailed, budgeted) → draft → **human review** →
send (wa.me / queue). Logs: `GET /api/ops/logs` (model usage, audit, sync runs).

---

## 5. Customer journey & behaviour patterns

```text
 awareness → interest → evaluation → purchase → onboarding → retention → advocacy
     │           │           │            │            │           │          │
 welcome     rate share   quotation    first order  delivery    repeat    referral
 catalogue   requirement  sample       repeat       feedback    reorder   review
```

| Pattern | Detect | Next action by stage |
|---|---|---|
| New customer | synced < 7d, no order | WA-NEW-01 → WA-NEW-02 → WA-QT-01 → WA-FBK-02 |
| Repeat customer | 2+ orders | WA-ORD-01 → WA-DSP-01 → WA-FBK-06 → WA-RT-01 |
| At risk | negative sentiment / 60d idle | WA-FBK-06 → WA-FU-03 |
| High value | top-decile gross | WA-RT-01 → WA-EXP-01 |

Endpoints: `POST /api/journey/event`, `GET /api/journey/{stories,behaviours,patterns,summary}`.

---

## 6. Prompt samples (JSON, human-reviewed)

Published at `gs://kalika_enterprises/sales-metadata/weekly_prompts.json` and served at
`GET /api/ops/prompt-samples` (local file first, GCS fallback = realtime fetch).

| ID | Task | Model | Review |
|---|---|---|---|
| PR-01 | customer_feedback_summary | gemma-4-27b-it | yes |
| PR-02 | journey_next_step | gemini-2.5-flash | yes |
| PR-03 | behaviour_pattern_extract | gemini-2.5-flash | no |
| PR-04 | weekly_prompt_refinement | gemini-2.5-flash | yes |
| PR-05 | dispatch_followup_draft | gemma-4-27b-it | yes |

Each prompt has `template`, `variables`, `sample_input`, `expected_output` — directly testable in the UI.

---

## 7. UAT enablement (one week)

| Feature | Status |
|---|---|
| ERP dispatch + orders dashboards | enabled |
| Sales forecast | enabled |
| Daily rate calculator | enabled |
| Feedback pipeline (wa.me, human review) | enabled |
| Customer journey + stories | enabled |
| YouTube channel sync (Data API) | enabled |
| YouTube Analytics API (OAuth) | next scope |
| RL pattern suggestions | next scope |

UAT users see this list at `GET /api/ops/uat` and on the **UAT & ops** page.

---

## 8. Deploy checklist

1. `GET /api/ops/preflight` → 0 fail (currently ✅ 21 pass / 1 warn).
2. `POST /api/erp/sync` → dispatch 117 / orders 89.
3. `POST /api/ops/run-checks` → report stored in `sync_runs`.
4. Verify journeys: record 2 events → story shows correct stage + next template.
5. Confirm crons: 17 tasks, IST window mapped to UTC.
6. Build frontend (`npm run build` → `sales_fastapi/static`) or run dev server.
7. Publish docs + prompt JSON to GCS `sales-metadata/`.
8. Hand UAT logins to Kalika ERP users (read-only + admin for `ai.solutions@kalisoftai.in`).

---

## 9. Rollback

- Sales app: previous container image / `git revert`; ERP unaffected (separate repo, read-only feed).
- Disable UAT instantly: `UAT_ENABLED=false`.
- Disable AI: `LLM_ENABLED=false` (deterministic templates keep working).
