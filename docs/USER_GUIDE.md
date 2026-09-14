# Kalisoft AI Sales — User Guide

A single workspace for **contacts, outreach templates, bulk email/WhatsApp/WeChat
campaigns**, powered by a cost-optimised model router (Gemma + small local models),
with governance/audit and human-in-the-loop review.

- **Frontend (dev):** http://localhost:5173/static/
- **API + docs:** http://localhost:8000/ · http://localhost:8000/docs
- **Wechaty gateway:** http://localhost:8788/health
- **Production:** https://kalisoft-sales-19782268668.asia-south1.run.app

---

## 1. Run the stack

```powershell
# 1) Backend (FastAPI) — Redis is disabled for local runs
python run.py --seed                     # http://localhost:8000

# 2) Frontend (React + Vite, proxies /api -> :8000)
cd frontend; npm install; npm run dev     # http://localhost:5173/static/

# 3) Wechaty gateway (WhatsApp/WeChat)
cd wechaty-gateway
$env:WECHATY_GATEWAY_MODE="mock"; $env:WECHATY_GATEWAY_TOKEN="dev-token"
$env:WECHATY_WEBHOOK_SECRET="dev-secret"; $env:PORT="8788"
npm start
```

Enable the WhatsApp/WeChat channel on the API (environment variables):

```powershell
$env:WHATSAPP_ENABLED="true"
$env:WECHATY_GATEWAY_URL="http://127.0.0.1:8788"
$env:WECHATY_GATEWAY_TOKEN="dev-token"
$env:WECHATY_WEBHOOK_SECRET="dev-secret"
python run.py
```

---

## 2. Sign in

- **Production** (https://kalisoft-sales-19782268668.asia-south1.run.app): the
  dev field is prefilled with the official email **`ai.solutions@kalisoftai.in`** —
  click **Enter**. Only this allow-listed email is accepted (`AUTH_DEV_MODE=true` +
  `AUTH_DEV_ALLOWED_EMAILS`); any other email gets **403**.
- **Google Sign-In** appears once a real `GOOGLE_CLIENT_ID` is configured; until
  then the page shows "Google Sign-In is not configured".
- **Local dev** (`AUTH_DEV_MODE=true`): type any email and press *Enter*; the first
  login creates the user.
- **Admin user:** `ai.solutions@kalisoftai.in` (name: Kalisoft).

### Plans shown on the sign-in page
The page also shows transparent pricing: **Free** (2 AI users, ₹0), Starter ₹499,
Growth ₹1,499, Scale ₹3,999 per month (INR, excl. 18% GST; annual = 2 months free),
plus a **WhatsApp cost-per-message** table and calculator sourced from Meta's
official India rate card.

---

## 3. Overview tab

Live totals, intent breakdown, recent contacts, and a "system pulse" for database,
GCS and Google Sign-In. Use **Refresh** to re-poll.

---

## 4. Contacts tab

| Action | How |
|---|---|
| Search | Type in the search box (matches company, name, email). |
| Add one | **New contact** → fill email (required) + details → Save. Intent/domain auto-classified. |
| Upload many | **Upload files** → select one or more `.csv`, `.xlsx`, `.xls`, `.vcf`, `.json`. |
| Sync a GCS path | Enter a prefix (e.g. `sales-contacts/`) → **Sync GCS path**. |
| Import default GCS | **Import GCS** uses the configured contacts prefix. |
| Delete | Trash icon on a row (confirm). |

Uploads are per-user and de-duplicated by email. Excel (`openpyxl`/`xlrd`), vCard
and CSV/JSON are all parsed server-side.

> The admin workspace was populated from `gs://kalika_enterprises/sales-contacts/`.

---

## 5. Templates tab (in Outreach)

Click **Seed templates** to load the Kalisoft defaults (12 templates) covering:

- **Channels:** `email`, `whatsapp`, `linkedin`, `wechat`
- **Strategies:** `cold_outreach`, `follow_up`, `nurture`, `proposal`, `closing`, `re_engage`
- **Funnel stages:** awareness → interest → consideration → decision → retention

Placeholders use `{{name}}`, `{{company}}`, `{{intent}}`, `{{sender_name}}`,
`{{calendar_link}}` and are filled per contact.

---

## 6. Outreach tab — bulk campaigns

1. **Select a template** (pick channel + strategy automatically).
2. **Build a campaign:** name, channel, strategy, intent filter, number of contacts.
3. **Generate for review** — messages are rendered per contact; when `LLM_ENABLED`
   and an API key are set, Gemma personalises each message. Otherwise the template
   render is used (`ai_model=template`).
4. **Approve all** — human-in-the-loop gate. Nothing sends before approval.
5. **Send approved** — dispatches by channel:
   - `email` → SMTP via your saved Email connection
   - `whatsapp` / `wechat` → Wechaty gateway
   - `linkedin` → queued for manual action
6. **Campaign history** shows status and sent/failed counts; open any campaign to
   see per-message status.

Every create/approve/send action is written to the audit trail.

---

## 7. Gemma personalisation

Set these to enable model-generated messaging (otherwise templates are used):

```powershell
$env:LLM_ENABLED="true"
$env:GEMINI_API_KEY="<key>"
$env:LLM_GEMMA_MODEL="gemma-4-27b-it"     # default
```

The router tries **Gemma → local small model → cloud flash → offline echo**. Task
routing, token budgets and per-call cost are tracked in `model_usage` and visible at
`GET /api/governance/usage`.

---

## 8. Wechaty gateway (WhatsApp / WeChat)

- **Mock mode** (default): no account needed — ideal for testing the full flow.
  `POST /simulate/inbound` injects a message; outbound `/send` returns a synthetic id.
- **Live mode:** `WECHATY_GATEWAY_MODE=live WECHATY_PUPPET=wechaty-puppet-wechat4u`
  then scan the QR shown at `GET /qr`. For hosted puppets use
  `wechaty-puppet-service` + `WECHATY_PUPPET_SERVICE_TOKEN`.

Inbound messages are forwarded to `/api/whatsapp/webhook` with an HMAC signature
(`X-Wechaty-Signature`).

> Use a **dedicated number**; automated sending risks a platform ban.

---

## 9. Accessibility

- Semantic landmarks: `nav`, `main`, `section`, `button`, `label`.
- Forms use real `<label>` elements; icon-only buttons carry `aria-label`.
- Template and campaign rows are keyboard-focusable buttons (`role="listitem"`,
  `aria-pressed` on selection).
- Status is shown as text (not colour alone): `sent`, `failed`, `queued`, `pending_review`.
- High-contrast palette; focus outlines via the browser default and `.selected` outline.
- Responsive layout down to mobile with a collapsible sidebar.

---

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| Login fails | Ensure `AUTH_DEV_MODE=true`; email must be non-empty. |
| Upload does nothing | Check the file extension is supported; watch the toast message. |
| Campaign send fails for all | Email: add an Email connection. WhatsApp: set `WHATSAPP_ENABLED=true` and start the gateway. |
| `ai_model=template` | `LLM_ENABLED` off or no `GEMINI_API_KEY` — expected fallback. |
| Gateway 401 | Token mismatch between API `WECHATY_GATEWAY_TOKEN` and the gateway. |
| Health shows `redis: disabled` | Expected locally; Redis is commented out. |
| GCS import 503 | ADC unavailable or bucket/prefix wrong. |

---

## 11. API quick reference (new)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/templates` | list templates (`?channel=&strategy=`) |
| POST | `/api/templates` | create template |
| PATCH/DELETE | `/api/templates/{id}` | edit / delete |
| POST | `/api/templates/seed` | load Kalisoft defaults |
| GET | `/api/templates/meta` | channels, strategies, funnel stages |
| POST | `/api/contacts/upload` | multipart: `files[]`, `gcs_prefix`, `gcs_bucket` |
| POST | `/api/campaigns` | create campaign (renders messages) |
| GET | `/api/campaigns` · `/api/campaigns/{id}` | list / detail |
| PATCH | `/api/campaigns/{id}/messages/{mid}` | edit / approve a message |
| POST | `/api/campaigns/{id}/approve` | approve all pending |
| POST | `/api/campaigns/{id}/send` | send approved |
| GET | `/api/whatsapp/status` | gateway + channel status |
