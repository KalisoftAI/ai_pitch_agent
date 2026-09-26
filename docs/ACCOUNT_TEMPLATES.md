# Account Catalog, Quote & Invoice Templates

> **Status: future scope / design only.** The source workbook is local and intentionally
> ignored by Git. This document defines the service contract before any account, billing,
> or persistent catalog tables are added.

## 1. Source of truth

The initial catalog is derived from:

- `data/All-project-matrices.xlsx`
- Sheet: `Pricing detils of projects`
- Currency: INR
- Price unit: project service, expressed as a minimum–maximum range
- Tax: not supplied by the workbook and must be selected explicitly in a quote
- Blank price cells: manual-pricing services; they must not be converted to zero

The workbook is a business input, not an application secret. It remains excluded from
commits so customer or commercial data is not pushed accidentally. A production
implementation should load the approved catalog through a controlled GCS/import job
with a version and checksum.

## 2. Workbook mapping

The pricing sheet has a non-standard first row: the first cell contains a local file
path and the actual headers begin in the next cells. The importer must identify the
header by `Description`, not by position alone.

| Workbook column | Catalog field | Processing |
|---|---|---|
| A | `service_name` | Trim and normalize whitespace; preserve the display name |
| B | `description` | Keep as customer-facing summary; optionally translate with Gemma 4 |
| C | `basic_features` | Parse bullets/commas into ordered feature list |
| D | `advanced_features` | Parse bullets/commas into ordered feature list |
| E | `basic_price_min`, `basic_price_max` | Parse INR range; leave both blank when absent |
| F | `advanced_price_min`, `advanced_price_max` | Parse INR range; leave both blank when absent |
| G+ | `notes` / `source_metadata` | Preserve only reviewed business notes; do not expose raw rows by default |

Initial catalog records from the workbook include:

| Service | Basic plan | Advanced / customizable plan |
|---|---:|---:|
| Commercial Website | ₹7,000–₹10,000 | ₹15,000–₹40,000 |
| E-commerce Website | ₹15,000–₹22,000 | ₹30,000–₹90,000 |
| AI Chatbot | ₹12,000–₹25,000 | ₹40,000–₹1,20,000 |
| Marketing Outreach AI | ₹8,000–₹12,000 | ₹14,000–₹20,000 |
| WhatsApp Automation | ₹8,000–₹18,000 | ₹25,000–₹60,000 |
| Procurement AI Agent | ₹30,000–₹60,000 | ₹80,000–₹2,50,000 |
| ClipCraftAI | Manual | Manual |
| LinkedIn Post Automation | ₹7,000–₹15,000 | ₹20,000–₹50,000 |
| E-commerce + SAP Integration | ₹60,000–₹1,20,000 | ₹1,50,000–₹4,00,000 |
| Food Ordering Bot | ₹15,000–₹30,000 | ₹40,000–₹90,000 |
| Custom AI Agent Development | Manual | Manual |
| AI Workflow Automation | Manual | Manual |
| AI Prompt Engineering | Manual | Manual |
| AI Document Processing | Manual | Manual |

These ranges are catalog defaults, not approved customer prices. A salesperson must
select a value or provide an approved override before a quote can be sent.

## 3. Account template

The account record is the parent for quotes, catalog selections, and invoices.

| Field | Type | Required | Notes |
|---|---|---:|---|
| `account_id` | UUID | Yes | Internal identifier |
| `legal_name` | string | Yes | Registered customer name |
| `display_name` | string | Yes | Name shown in the workspace |
| `billing_name` | string | No | May differ from legal name |
| `email` | string | Yes | Account owner or billing contact |
| `phone` | string | No | International E.164 preferred |
| `billing_address` | object | Yes | Address, city, state, postal code, country |
| `gstin` | string | No | Mask in all normal UI responses; encrypt at rest |
| `place_of_supply` | string | No | Required for the applicable tax workflow |
| `currency` | enum | Yes | Start with `INR` |
| `payment_terms_days` | integer | No | Default from workspace settings |
| `quote_terms` | text | No | Versioned commercial terms |
| `owner_user_id` | integer | Yes | Tenant/user scoping |
| `created_at` / `updated_at` | datetime | Yes | Audit timestamps |

GSTIN, billing address, and tax values are restricted fields. They must be redacted in
LLM prompts, logs, exports, and support views unless the user explicitly opens the
billing workspace.

## 4. Catalog service template

```json
{
  "service_id": "commercial-website",
  "name": "Commercial Website",
  "description": "Professional business website to establish online presence and generate leads.",
  "plans": [
    {
      "plan": "basic",
      "features": [
        "Company Profile Website",
        "Responsive Design",
        "UI/UX Design"
      ],
      "price_min": 7000,
      "price_max": 10000,
      "currency": "INR"
    },
    {
      "plan": "advanced",
      "features": [
        "Custom UI/UX",
        "CMS/Admin Panel",
        "Advanced SEO"
      ],
      "price_min": 15000,
      "price_max": 40000,
      "currency": "INR"
    }
  ],
  "source": "All-project-matrices.xlsx",
  "source_version": "review-required",
  "active": true
}
```

Catalog import rules:

1. Deduplicate by normalized `service_id`.
2. Keep the previous version for audit and rollback.
3. Never overwrite an approved catalog item with a blank workbook price.
4. Mark conflicts for human review instead of choosing a price automatically.
5. Record the source workbook checksum and import timestamp.

## 5. Quote template

A quote is a versioned proposal linked to exactly one account and one or more catalog
line items.

| Field | Type | Notes |
|---|---|---|
| `quote_id` | UUID | Internal identifier |
| `quote_number` | string | Human-readable, unique per workspace |
| `account_id` | UUID | Parent account |
| `valid_until` | date | Explicit expiry |
| `currency` | enum | Defaults to account currency |
| `line_items` | array | Service, plan, quantity, unit price, discount |
| `subtotal` | decimal | Deterministic calculation |
| `tax_rate` | decimal | Explicitly selected, never inferred by AI |
| `tax_amount` | decimal | Deterministic calculation |
| `total` | decimal | `subtotal - discount + tax_amount` |
| `status` | enum | `draft`, `review`, `approved`, `sent`, `accepted`, `expired` |
| `notes` | text | Customer-facing terms |
| `created_by` | integer | Authenticated user |
| `created_at` / `updated_at` | datetime | Audit fields |

Suggested line item:

```json
{
  "service_id": "ai-chatbot",
  "service_name": "AI Chatbot",
  "plan": "basic",
  "description": "FAQ bot, website integration, lead capture, and basic analytics",
  "quantity": 1,
  "unit_price": 18000,
  "discount": 0,
  "tax_rate": 0.18,
  "line_total": 21240
}
```

All monetary calculations must use a decimal type and server-side arithmetic. A model
may explain a quote or recommend a plan, but it must not be the authority for totals,
tax, discount, or invoice numbering.

## 6. Invoice template

An invoice is created only from an approved quote or an explicitly approved manual
line-item review.

| Field | Type | Notes |
|---|---|---|
| `invoice_id` | UUID | Internal identifier |
| `invoice_number` | string | Immutable after finalization |
| `quote_id` | UUID | Source quote, if applicable |
| `account_id` | UUID | Parent account |
| `issue_date` | date | Invoice issue date |
| `due_date` | date | Derived from approved payment terms |
| `line_items` | array | Frozen copy of approved quote lines |
| `tax_rate` / `tax_amount` | decimal | Frozen approved values |
| `subtotal` / `grand_total` | decimal | Server-calculated frozen totals |
| `payment_status` | enum | `unpaid`, `partial`, `paid`, `overdue`, `void` |
| `payment_reference` | string | Optional reconciliation reference |
| `place_of_supply` | string | Tax jurisdiction input |
| `notes` | text | Terms and payment instructions |

A finalized invoice is immutable. Corrections create a credit note or a new revision;
they do not silently rewrite the issued document. GST/e-invoice compliance, numbering,
signatures, and delivery requirements require a separate Indian tax review before the
feature is enabled in production.

## 7. Gemma 4 processing and routing

Account workflows use Gemma 4 for unstructured work, while the application remains the
authority for identity, arithmetic, permissions, and state transitions.

```text
Workbook / GCS catalog
        │ validate, normalize, version
        v
Gemma 4 extraction and account matching
        │ confidence + proposed service/plan
        v
Quote draft ── human review ── deterministic totals ── approval
        │
        v
Invoice draft ── tax/compliance checks ── human approval ── immutable issue
```

| Future task | Model tier | Gemma 4 responsibility | Deterministic boundary |
|---|---|---|---|
| `extract_catalog_entities` | Small/medium | Normalize descriptions, features, and ambiguous service names | Do not invent prices or IDs |
| `match_account_requirements` | Medium | Recommend services and plan from account requirements | User confirms selections |
| `draft_quote_summary` | Medium | Write customer-facing scope and exclusions | Server calculates line totals |
| `draft_invoice_summary` | Small | Summarize approved line items and terms | Server freezes approved totals and numbers |
| `explain_catalog_change` | Small | Explain a version or price-range change | Audit record remains system-owned |

The planned router policy is:

1. Use Gemma 4 for catalog/account text processing when `LLM_ENABLED=true`.
2. Use local small models for validation, normalization, and low-risk summaries.
3. Use cloud flash only as a configured fallback when the Gemma provider is unavailable.
4. Keep the offline `echo` fallback for tests and budget exhaustion.
5. Record model, tokens, latency, and cost in `model_usage` for invoice-grade reporting.
6. Require human approval before a generated quote or invoice can change status.

Future task names should be added to `sales_fastapi/llm/tasks.py` only when the account
API and database migration are implemented. They are not production routes yet.

## 8. Planned service boundaries

| Future endpoint | Purpose |
|---|---|
| `GET /api/accounts` | List user-scoped accounts |
| `POST /api/accounts` | Create an account |
| `GET /api/catalog/services` | List active catalog services |
| `POST /api/catalog/import` | Import/version the approved workbook export |
| `POST /api/quotes/preview` | Generate a draft with deterministic totals |
| `POST /api/quotes/{id}/approve` | Human approval transition |
| `POST /api/quotes/{id}/send` | Send through the approved email channel |
| `POST /api/invoices/from-quote/{id}` | Create a draft invoice from an approved quote |
| `POST /api/invoices/{id}/finalize` | Validate and freeze an invoice |

The future implementation should add tenant/user scoping, audit events, idempotency
keys, optimistic version checks, and a PDF renderer only after the data contract is
approved.

## 9. Delivery plan

- [ ] **A1** — Confirm service IDs, tax fields, numbering, and approval roles.
- [ ] **A2** — Build a reviewed workbook importer and catalog version history.
- [ ] **A3** — Add account, quote, and invoice migrations with tenant scoping.
- [ ] **A4** — Add deterministic quote/invoice arithmetic and audit events.
- [ ] **A5** — Add Gemma 4 tasks behind `LLM_ENABLED` and a feature flag.
- [ ] **A6** — Add human-review UI and approval gates.
- [ ] **A7** — Add PDF delivery, payment reconciliation, and tax-compliance review.
- [ ] **A8** — Load-test import, quote, and invoice workflows before production enablement.

## 10. Explicitly next scope

The following remain separate backlog items and are not required to start this account
service:

- BigQuery KPI warehouse and forecasting.
- Multi-tenant PostgreSQL row-level security.
- Knowledge catalog graph database and graph explorer.
- Sarvam voice notes and Wechaty live mode.
- Official LinkedIn and Reddit API integrations.
- Automated payment collection, credit notes, and statutory e-invoicing.

The account service should begin with the reviewed catalog import and account data
model. Gemma 4 routing and the UI are gated until the human approval and deterministic
calculation boundaries above are implemented and tested.
