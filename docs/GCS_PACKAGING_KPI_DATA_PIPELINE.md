# GCS → Packaging / Quotes → Business KPI Data Pipeline

> **Single-source update document.** This is the complete reference for how data is
> read (contextually), how it is processed from the Google Cloud Storage (GCS)
> bucket, how it connects to the Business KPI metrics dashboards, and how the
> next update is staged on a branch cut from the **deployed** branch so it can be
> human-verified and merged without touching the running ERP user.
>
> **Status:** local / branch-only. Nothing in this document changes the deployed
> Cloud Run revisions until the step-by-step deployment checks in §8 pass.
>
> **Provenance:** `D:\KaliSoftAI\ERP-System\backend\docs` (quotes + packaging +
> ERP KPI), `D:\KaliSoftAI\ai_pitch_agent` (sales app: GCS loader, importers,
> KPI router), and the GCS bucket `kalisoftai-datahub`.

---

## 0. TL;DR connection map

```text
        GOOGLE CLOUD STORAGE  (bucket: kalisoftai-datahub)
+-----------------------------------------------------------------+
|  all-sales-contacts-data/    Kalika_inventory/    scraper_*      |
|  contacts/user_*_{cat}/      campaign_*           Reports_*.csv  |
+----+--------------------------------------------+---------------+
     |                                            |
     | (1) contacts / CSV / XLSX / VCF / JSON     | (2) daily Excel report
     v                                            v
+---------------------------+          +---------------------------+
|  SALES APP (ai_pitch)      |          |  ERP BACKEND (Kalika)     |
|  - importer.py             |          |  - services/gcs.py        |
|  - event_importer.py       |          |  - excel_parser_v2.py     |
|  - analytics.py (GA4)      |          |  - import_common.py       |
+-------------+-------------+          +-------------+-------------+
              |                                      |
              | Postgres (contacts, campaigns,       | PostgreSQL (orders, RM,
              | events, model_usage)                 | production, dispatch)
              v                                      v
+---------------------------+          +---------------------------+
|  /api/kpi/*                |          |  /api/dashboard/*         |
|  Business KPI metrics      |          |  Business KPI metrics     |
+---------------------------+          +---------------------------+
              \                            /
               \                          /
                v                        v
            +--------------------------------+
            |   Business KPI Dashboard UI    |
            +--------------------------------+
```

---

## 1. Current data reading — contextual flow

### 1.1 Two independent read paths, one data hub

Both applications read from the **same** GCS bucket (`kalisoftai-datahub`) but
through different, isolated code paths. They never share a live session; they
share only the bucket.

```text
  SALES APP (FastAPI)                        ERP BACKEND (FastAPI)
  -------------------                        ---------------------
  GCSStorage(bucket=GCS_BUCKET_CONTACTS)     storage.Client() -> bucket(GCS_BUCKET)
  GCS_PATH_CONTACTS=all-sales-contacts-data  GCS_EXCEL_FILE=
      |                                          Kalika_inventory/Daily Report Aug-26.xlsx
      |
  list_contacts(prefix)                      download_excel(dest)
      |  blob suffix filter:                      |
      |  .json .csv .vcf .xlsx .xls               |  blob.exists() guard
      v                                          v
  records_from_bytes(name, raw)              excel_parser_v2 / import_common
      |  .json .csv .xlsx .xls .vcf              |
      v                                          v
  normalise_record(record)                   validation_v2 -> stock_service
      |  header-variant mapping                   |
      |  classify_contact (domain/intent)         v
      v                                      PostgreSQL (inventory, orders,
  PostgreSQL (contacts ...)                     production, dispatch)
```

### 1.2 Contextual enrichment at read time

When a record is normalised (`sales_fastapi/importer.py::normalise_record`) the
app derives **context** from the raw row so nothing is lost even though the
`Contact` model has no dedicated columns for every B2B field:

| Raw GCS field seen | Mapped to | Purpose |
|---|---|---|
| `email` / `e-mail` / `Email (Company / Division)` | `Contact.email` | identity + domain |
| `company` / `organisation` / `firm` | `Contact.company` | account |
| `sector`, `category`, `exporter`, `turnover range` | `Contact.tags[]` (`sector:…`) | segmentation / KPI source mix |
| `requirements`, `description`, `call status`, `website` | `Contact.notes` | contextual reading |
| `purchase / scm contact (name, role)` | `purchase_contact_*` | buying-centre context |
| derived from email domain | `Contact.domain` | classification |
| derived from text intent rules | `Contact.intent` | pipeline funnel KPI |

`classify_contact()` (services.py) produces the `(domain, intent, context)`
triple that feeds `GET /api/kpi/pipeline` (`by_intent`, `by_source`).

```text
  raw row ──► _pick() header matcher ──► normalise_record()
                    │                         │
                    │                         ├─ tags[]     : sector/exporter/turnover
                    │                         ├─ notes      : requirements/website
                    │                         ├─ domain     : from email
                    │                         └─ intent     : infer_intent(text)
                    │                                  │
                    └────────────► classify_contact() ──┘
                                          │
                                          v
                              Contact( ... )  ► KPI pipeline
```

### 1.3 GCS key layout (exact, from code)

```text
gs://kalisoftai-datahub/
├── all-sales-contacts-data/                 # GCS_PATH_CONTACTS
│   ├── Reports_snapshot (2).csv             # GA4 snapshot (analytics.py)
│   ├── *.csv  *.xlsx  *.vcf  *.json         # raw exports imported by importer.py
│   └── contacts/
│       └── user_{id}_{category}/            # user-isolated
│           ├── {uid}.json                   # one contact snapshot
│           └── *.csv                        # CSV uploads/exports (not contacts)
├── scraper_config/
│   ├── keywords.json                        # seeded defaults
│   ├── locations.json                       # seeded defaults
│   ├── progress.json                        # live run progress
│   └── stats.json                           # per-keyword run stats (cap 1000)
├── scraper_runs/{YYYY-MM-DD}/{keyword}.json # historical scrape batches
├── campaign_engine/
│   ├── config.json                          # category, template, daily_limit
│   └── progress.json                        # live campaign progress
├── campaign_runs/{...}.json                 # historical campaign batches
└── Kalika_inventory/
    └── Daily Report Aug-26.xlsx             # ERP source workbook (GCS_EXCEL_FILE)
```

`categories` accepted by the sales app are **linkedin, suppliers, buyers, events**
(`dashboard/views.py`). Reads and writes are both scoped to
`user_{id}_{category}` so one workspace can never read another's contacts.

---

## 2. Data requirements — what must be processed from GCS

This is the explicit "other data requirements" checklist for the next update.

| # | Data source (GCS path) | Format | Required processing | Consumer |
|---|---|---|---|---|
| R1 | `all-sales-contacts-data/*.{csv,xlsx,xls,vcf,json}` | mixed | header-variant normalisation, MD5 fallback email, intent/domain classify | sales `Contact` |
| R2 | `all-sales-contacts-data/contacts/user_*_{cat}/{uid}.json` | JSON | user-isolated list/get/delete/add | sales dashboard |
| R3 | `all-sales-contacts-data/Reports_snapshot (2).csv` | GA4 multi-section CSV | section parser (totals/pages/sources/cities/retention) | `GET /api/kpi/website` |
| R4 | `scraper_config/keywords.json` + `locations.json` | JSON | seed defaults on first use, active flag | scraper engine |
| R5 | `scraper_config/stats.json` | JSON | append per-keyword stat, keep last 1000 | scraper KPI |
| R6 | `scraper_runs/{date}/{keyword}.json` | JSON | list newest-first, fetch single batch | scrape history |
| R7 | `campaign_engine/config.json` | JSON | default `daily_limit=25`, personalise flags | auto-campaign |
| R8 | `campaign_runs/{...}.json` | JSON | list newest-first | campaign history |
| R9 | `Kalika_inventory/Daily Report Aug-26.xlsx` | XLSX | tolerant header scan, mapping to inventory/production/dispatch | ERP |
| **R10** | **`Kalika_inventory/*.xlsx` (packaging BOM lines)** | XLSX | **NEW: map film/tape/bag specs → `Product` + `RawMaterialBalance`** | **ERP KPI** |
| **R11** | **`all-sales-contacts-data/quoting/*.csv` (quote pipeline)** | CSV | **NEW: normalise RFQ/quote rows → quote funnel KPI** | **sales KPI** |

> **R10 / R11 are the "next update" additions.** They are additive read
> requirements only — no schema break, no change to the deployed revisions until
> §8 verification passes.

### 2.1 Planned processing chain for R10/R11

```text
  GCS packaging workbook            GCS quoting CSV
        |                                 |
        v                                 v
  excel_parser_v2.py                importer.py (quote variant)
  tolerant header scan              header-variant map
        |                                 |
        v                                 v
  Product(code, model, category,    QuoteLead(stage, requirements,
          uom, spec)                      value, contact_ref)
        |                                 |
        v                                 v
  RawMaterialBalance                quote funnel counters
        \                               /
         \                             /
          v                           v
     ERP /api/dashboard/*        sales /api/kpi/pipeline
          \                        /
           v                      v
        Business KPI metrics dashboard
```

---

## 3. Existing packaging industrial data read from GCS

The ERP already classifies packaging / film / tape materials during import
(`app/services/migration_v2.py`). The canonical families recognised today:

```text
  PACKAGING MATERIAL FAMILIES (from migration_v2.py)
  +---------------------------------------------+
  |  BOPP / PACKAGING TAPE   |  MASKING TAPE    |
  |  TARPAULINE              |  HDPE BAG        |
  |  STRETCH FILM            |  SHRINK FILM     |
  |  POLY BAGS               |  HAND GLOVES     |
  +---------------------------------------------+
```

Product classification rule (BOPP example):

```text
  model text ──► if "BOPP" or "CELLO TAPE" in text  ->  "BOPP / PACKAGING TAPE"
             └─► else ... specific mapping ...
```

### 3.1 Packaging requirement signals (existing lead data)

These specifications are **already captured** and are the industrial packaging
context that the KPI dashboard consumes:

| Family | Size | Micron / grade | Printing | Source |
|---|---|---|---|---|
| Plastic bags | 17 in | bulk MOQ | — | Plastic Bag (Satish Rathod) |
| Shrink film / pouch | — | — | — | Raamba Foods, Akluj |
| Wrapping roll / shrink film | — | 51 micron | — | Allstate |
| Stretch film | — | 25–30 micron | with printing | Bajaj Reinforcement |
| BOPP tape | 2.5 in × 120 m | 48 micron | — | Ozoori Industries |
| Floor-marking tape | 5 nos. | yellow | — | Kustubh |
| Hand gloves | — | — | — | Baban Bhagade, Manchar |
| Stretch film | — | — | — | **Jabil / Electronics (see §7)** |

### 3.2 What the KPI dashboard derives from packaging data

```text
  packaging products ─► inventory_status (Healthy/Low/Out of Stock)
                    ─► low_stock_list   (reorder alerts)
                    ─► raw_material_stock (opening/inward/balance)
                    ─► production_by_product (planned/produced/pending)
                    ─► dispatch_by_plant
```

---

## 4. Business KPI metrics dashboard — connection

There are **two KPI surfaces** that this pipeline feeds. They are read-only
projections over the databases populated from GCS.

### 4.1 Sales app KPI endpoints (`sales_fastapi/routers/scheduler.py`)

| Endpoint | Metric | Feeds |
|---|---|---|
| `GET /api/kpi/overview` | contacts_total, signals{linkedin,reddit}, campaigns_total, messages_sent, whatsapp_pending, email_connections_active | headline tiles |
| `GET /api/kpi/pipeline` | by_intent, by_source, new_last_7_days | funnel chart |
| `GET /api/kpi/outreach` | campaigns_by_status, messages_by_status, sent, failed, delivery_rate | outreach funnel |
| `GET /api/kpi/costs` | by_task, total_cost_micros, total_cost_usd | cost tile |
| `GET /api/kpi/website` | GA4 snapshot parsed from **GCS** | website tile |

### 4.2 ERP KPI endpoints (`app/routers/dashboard.py`)

| Endpoint | Metric |
|---|---|
| `GET /api/dashboard/summary` | orders, production, RM stock/balance, purchase value, dispatch, counts |
| `GET /api/dashboard/dispatch-by-plant` | scheduled / dispatched / pending |
| `GET /api/dashboard/production-by-product` | planned / produced / pending |
| `GET /api/dashboard/order-pipeline` | counts per order status |
| `GET /api/dashboard/inventory-status` | Healthy / Low / Out of Stock |
| `GET /api/dashboard/raw-material-stock` | opening / inward / balance |
| `GET /api/dashboard/daily-trends` | dispatch & production last 30 days |
| `GET /api/dashboard/low-stock-list` | reorder candidates |

### 4.3 Live / observed KPI numbers (context baseline)

From the sales working matrix (`data/All-project-matrices.xlsx`, Sheet1):

```text
  +-------------------------------------------+---------+
  | KPI                                       |  Value  |
  +-------------------------------------------+---------+
  | Total supplier contacts extracted         |   1263  |
  | Manual RFQs received (quotation requests) |    104  |
  | Quotations received                       |     79  |
  | Product finalised                         |      1  |
  | Mail sent count                           |    785  |
  | Event client requirements                 |     40  |
  +-------------------------------------------+---------+
```

Conversion read-out for review (values only, no inference added):

```text
  RFQ received (104) ──► quotations received (79) ──► product finalised (1)
        │                        │
        └── mail sent 785 ───────┘      event requirements 40
```

### 4.4 How a GCS row becomes a KPI (end-to-end)

```text
  GCS blob ─► importer/normaliser ─► DB row ─► KPI query ─► JSON ─► dashboard tile
     │              │                  │           │
     │              │                  │           └─ /api/kpi/* , /api/dashboard/*
     │              │                  └─ user_id scoped (tenant isolation)
     │              └─ classify_contact (domain/intent/context)
     └─ list_blobs(prefix) + suffix filter
```

---

## 5. Data security checks

All items below are **already implemented** in the codebase and must remain
green across the branch → merge.

| # | Control | Where | Check |
|---|---|---|---|
| S1 | User isolation by prefix `user_{id}_{category}` | `dashboard/gcs.py::_user_category` | a user cannot list/get another user's blob |
| S2 | GCS prefix validation within contacts namespace | commit `3a2f06a` (`routers/contacts.py`) | reject prefixes escaping `contacts/` |
| S3 | PII redaction always on in production | `config.py` `PII_REDACTION_ENABLED` validator | prod boot fails if false |
| S4 | Append-only audit log, redacted details | `governance/audit.py`, `models.AuditLog` | every mutation logged |
| S5 | Secrets never returned; app passwords encrypted | `security.py`, `dashboard/crypto.py` | API never echoes secrets |
| S6 | Contact-file suffix allow-list | `services.GCSStorage.list_contacts` | only `.json/.csv/.vcf/.xlsx/.xls` |
| S7 | CSV vs contact separation | `gcs.list_contacts` skips non-`.json` | CSVs never parsed as contacts |
| S8 | Credentials gitignored | both `.gitignore` files | `credentials.json`, `*-credentials.json`, `*.pem`, `*.key` |
| S9 | Retention windows | `RETENTION_DAYS_AUDIT=365`, `RETENTION_DAYS_CONTACTS=730` | scheduled purge |
| S10 | Production config validator | `config.py::validate_security_settings` | AllowedHosts/CORS/SECRET_KEY enforced |

### 5.1 Security review checklist for THIS update

```text
  [ ] No new secret added to the repo (grep for token/key/password)
  [ ] New GCS paths stay inside the bucket namespace (no absolute / "../")
  [ ] New CSV/quote parser rejects rows without a resolvable identity
  [ ] New KPI queries are filtered by user_id / tenant
  [ ] No raw phone/email written to logs
  [ ] Sample data (this branch) stays OUT of git (see .gitignore)
```

---

## 6. Quotes update — staging without disturbing the deployed branch

The quotes work (ERP Quotation Management module + the Jabil/Amber lead sample)
is staged on a branch cut from the **deployed** branch. The deployed revision is
never modified in place.

```text
  deployed-master (deployed)  o----o----o-----------+  (untouched)
                               \                     \
                                \ next update         \ merge (after human verify)
                                 v                     v
                    docs/gcs-kpi-packaging-and-mcp-local  *  -> branch
                                 |
                                 | commit + push (sales app only)
                                 v
                     origin/docs/gcs-kpi-packaging-and-mcp-local
```

Rules for the quotes update:

1. **Never rebase or force-push** `deployed-master` / `sales-gcp-migration`.
2. New quote/SKU fields are **additive**; no column rename or drop.
3. Quotes continue the existing lifecycle: `Draft → Sent → Accepted/Rejected/Expired`.
4. Revision model is unchanged: same `quotation_no`, `revision + 1`, unique
   `(quotation_no, revision)`.
5. The Jabil/Amber sample is **documentation only** — it carries no business
   inference beyond what is written in the notebook (§7).

Existing quote lifecycle for reference (`Kalika_ERP_Recent_Changes.md`):

```text
                        send               accept
  +---------+  --------->   +------+  --------->   +----------+
  |  DRAFT  |             | SENT |             | ACCEPTED |
  +---------+             +------+             +----------+
       ^                    |  |
       |                    |  +----- reject ---> +----------+
       |   revise           |                       | REJECTED |
       |  (revision + 1)    |  validity date passed +----------+
       |                    v
       |                +----------+
       +--------------  | EXPIRED  |
                        +----------+
```

---

## 7. Quote processing pipeline — Jabil / Amber sample (extracted)

> **Transcription rule:** these details are transcribed exactly from the
> handwritten notebook photos. Nothing has been inferred or added. Unclear
> words are marked `[unclear]`. Phone numbers are transcribed as written and
> must be verified before any contact.

### 7.1 Extracted items (no additions)

| No. | Section | Text / Name as written | Phone | Requirement / Note | Verification |
|---:|---|---|---|---|---|
| 1 | Top note | `Next Month want to… [unclear]` | — | handwriting continues, unclear | do not infer |
| 2 | Top note | `Mabagap pati Aluminium [unclear]` | — | spelling unclear | approximate |
| 3 | Top note | `Bhal...wan [unclear]` | — | name/word unclear | verify |
| 4 | Requirement | `Requirement` | — | Stretch Film (both words clear) | clear |
| 5 | Jabil / Electronics | `JABIL → Prathmesh Sir` | 9503572830 | Electronics; Exports also written | company matched via user-provided URL |
| 6 | Contact / supplier | `Pogent Khaira [unclear]` | 8007405814 | `No requirement` written below | spelling uncertain |
| 7 | Sample / supplier | `Pravin` | 9156031472 | Sample & requirement; Existing Supplier; Vendor code | relationships not fully explicit |
| 8 | Category | `Exports` | — | separate underlined label | clear |
| 9 | Category | `Electronics` | — | separate underlined label | clear |
| 10 | Amber | `Amber` | — | heading / lead name | clear |
| 11 | Amber | `Gajendra →` | 9026254746 | — | name + number as written |
| 12 | Amber | `Sample given` | 7350702334 | Rate or any issue; Trial success | verify whose number this is |

### 7.2 Jabil official info (user-provided URL only)

| Item | Information | Source |
|---|---|---|
| Website | `https://www.jabil.com/` | user-provided |
| Overview | engineering, supply chain, and manufacturing solutions provider | jabil.com |
| Electronics | electronics manufacturing services, PCBA, box build, system integration, test, engineering, software design | jabil.com/capability/electronics.html |
| Pune | Pune facilities in the Ranjangaon MIDC Zone | jabil.com/contact/locations/pune.html |
| Notebook contact | Prathmesh — 9503572830 | notebook; **not** independently verified as Jabil |
| Notebook contact | Pravin — 9156031472 | notebook; **not** independently verified as Jabil |

### 7.3 Quote processing flow (from notebook)

```text
                    +--------------------------+
                    | Requirement: Stretch Film |
                    +------------+-------------+
                                 |
                                 v
                    +--------------------------+
                    | JABIL / Electronics       |
                    | Prathmesh: 9503572830     |
                    +------------+-------------+
                                 |
                                 v
                    +--------------------------+
                    | Existing Supplier?        |
                    | Pogent Khaira*            |
                    | 8007405814                |
                    | Note: No requirement      |
                    +------------+-------------+
                                 |
                                 v
                    +--------------------------+
                    | Sample & requirement      |
                    | Pravin: 9156031472        |
                    | Vendor code               |
                    +------------+-------------+
                                 |
                                 v
                    +--------------------------+
                    | Exports / Electronics     |
                    +--------------------------+

  AMBER FOLLOW-UP:
  +--------------------------+
  | Amber → Gajendra          |
  | 9026254746                |
  +------------+-------------+
               v
  +--------------------------+
  | Sample given              |
  | 7350702334                |
  +------------+-------------+
               v
  +--------------------------+
  | Rate or any issue?        |
  +------------+-------------+
               v
  +--------------------------+
  | Trial success             |
  +--------------------------+

  *Name spelling / relationships are unclear in the handwritten note.
```

### 7.4 Follow-up tracker (no additions)

| Lead / contact | Phone | Current note/status as written | Next follow-up item | Status confirmation |
|---|---|---|---|---|
| JABIL / Prathmesh | 9503572830 | Requirement: Stretch Film; Electronics / Exports | confirm requirement details | not stated |
| Pogent Khaira [unclear] | 8007405814 | No requirement | check whether a requirement has arisen | no requirement written |
| Pravin | 9156031472 | Sample & requirement; Existing Supplier; Vendor code | confirm sample/requirement and vendor-code status | not stated |
| Amber / Gajendra | 9026254746 | Sample given; Rate or any issue; Trial success | follow up on rate/issues and trial success | trial success written; no date |
| Amber-related number [association unclear] | 7350702334 | written beside `Sample given` | verify whose number this is | needs verification |

---

## 8. Step-by-step deployment (human-verified) & merge

Domain-expert / human verification gates. Do **not** promote to a deployed
revision until every gate is signed off.

```text
  G0  Branch created from deployed HEAD .............. [ ]
   |    git switch -c docs/... <deployed-sha>
   v
  G1  Docs + sample generated locally ................ [ ]
   |    (this file, MCP file, inventory xlsx)
   v
  G2  Schema/API review: additive only ............... [ ]
   |    no rename/drop, no required new column
   v
  G3  Security checks §5.1 all pass .................. [ ]
   |    secrets, prefixes, isolation, PII, logs
   v
  G4  Data-integrity: re-parse R1..R11 sample ......... [ ]
   |    row counts match, no data loss
   v
  G5  KPI parity: endpoints return identical shape ... [ ]
   |    /api/kpi/* and /api/dashboard/*
   v
  G6  Human/domain sign-off (packaging + quotes) ...... [ ]
   |    spec microns, tape sizes, lead relationships
   v
  G7  Merge to integration branch, run CI ........... [ ]
   |    tests + lint green
   v
  G8  Deploy to staging, smoke test ................. [ ]
   v
  G9  Promote to deployed revision ................... [ ]
```

### 8.1 Commands (safe, reversible)

```bash
# 0. Cut the branch from the deployed revision (sales app)
git switch -c docs/gcs-kpi-packaging-and-mcp-local <deployed-sha>

# 1..5. Write docs, review diffs (no deployment side effects)
git diff --stat
git diff <deployed-sha> -- docs/

# 6. Commit only the intended doc + gitignore changes
git add docs/GCS_PACKAGING_KPI_DATA_PIPELINE.md \
        docs/MCP_POLYMER_PRICE_CALCULATOR.md \
        docs/gcs_data_inventory.xlsx .gitignore
git commit -m "docs: GCS packaging/KPI pipeline, quotes sample, MCP local feature"

# 7. Push the branch (review PR before merge)
git push -u origin docs/gcs-kpi-packaging-and-mcp-local

# 8. After review + human sign-off, merge via PR (no force-push, no rebase
#    of the deployed branch).
```

### 8.2 Rollback

```text
  Any gate fails ─► keep branch unmerged.
  Deployed revision unchanged ─► nothing to roll back.
  If a bad merge lands: revert the merge commit on the integration branch;
  do NOT force-push the deployed branch.
```

---

## 9. File index for this update

| File | Purpose | Tracking |
|---|---|---|
| `docs/GCS_PACKAGING_KPI_DATA_PIPELINE.md` | this document | committed on branch |
| `docs/MCP_POLYMER_PRICE_CALCULATOR.md` | local-only MCP feature spec (not deployed) | committed on branch |
| `docs/gcs_data_inventory.xlsx` | GCS object inventory + stats (2 sheets) | committed on branch |
| `sample_data/` | raw Jabil/Amber + workbook extracts | **gitignored, not pushed** |

---

*End of document. Generated as a branch-only update; the deployed ERP user is
not affected until §8 gates pass and the branch is merged.*
