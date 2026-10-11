# MCP Connector — Real-Time Polymer Price Calculator (LOCAL TEST ONLY)

> ⚠️ **DO NOT DEPLOY.** This document specifies a **local-only** experiment.
> It must never be enabled on a deployed Cloud Run revision, never added to
> `cloudbuild.*.yaml`, and never wired into production environment variables
> until it has passed a separate security + legal review.
>
> Reference source (read-only): `https://www.plastemart.com/polymer-pricelist/ldpe-reliance/1/9`

---

## 1. Purpose

Provide packaging/quotes users a **real-time LDPE (Reliance) price** lookup and a
simple price calculator, exposed to the sales app through an **MCP (Model
Context Protocol)** server. This lets an LLM/agent fetch a live polymer price and
compute an indicative quote for stretch/PE film products.

Scope is deliberately narrow:

```text
  +----------------------+      MCP (stdio/http)      +----------------------+
  |  Local dev host      | <------------------------> |  MCP price server    |
  |  (developer machine) |                          |  (localhost only)    |
  +----------+-----------+                          +----------+-----------+
             |                                                 |
             | not wired to any deployed revision             | scrape (read-only)
             v                                                 v
  +----------------------+                          +----------------------+
  |  Local dashboard tab |                          |  plastemart.com       |
  |  "Price Calculator"  |                          |  /polymer-pricelist/  |
  +----------------------+                          |  ldpe-reliance/1/9    |
                                                    +----------------------+
```

---

## 2. Why local-only

| Concern | Reason for keeping it local |
|---|---|
| External scraping | plastemart.com is a third-party site; no ToS/robots review done yet |
| Data freshness | price pages are unstructured; parsing can break silently |
| Legal/licensing | redistribution of a third party's price list is not cleared |
| Ops risk | a scraper failure must not affect the deployed sales pipeline |
| Cost | avoids egress/compute on production revisions |

---

## 3. Proposed MCP tools (interface only)

```text
  Tool: get_polymer_price
  Input : { grade: "LDPE", brand: "Reliance" }
  Output: { grade, brand, price, currency, unit, as_of, source, stale }
          - stale: true when live fetch failed and a cached/local sample is used

  Tool: list_polymer_grades
  Input : {}
  Output: [ "LDPE", ... ]   # local seed list

  Tool: calculate_price
  Input : { price_per_kg, quantity_kg, wastage_pct, margin_pct }
  Output: { base_cost, wastage_cost, margin, total, currency }
```

### 3.1 Calculator formula (indicative only)

```text
  base_cost    = price_per_kg × quantity_kg
  wastage_cost = base_cost × wastage_pct / 100
  subtotal     = base_cost + wastage_cost
  margin       = subtotal × margin_pct / 100
  total        = subtotal + margin
```

---

## 4. Data flow (local)

```text
  [Local dashboard input]
        |  grade=LDPE brand=Reliance qty=5000kg
        v
  [Local MCP client] --- MCP call ---> [Local MCP server :PORT]
                                              |
                                              v
                                     [plastemart fetch adapter]
                                       - read-only GET
                                       - parse price table
                                       - normalize {price, unit}
                                       - TTL cache (e.g. 15 min)
                                              |
                        live ok ──────────────┤────────────── fetch fail
                             |                                 |
                             v                                 v
                     { live price }                   { stale sample + stale:true }
                             \                                 /
                              v                               v
                       [calculate_price] -> total -> local dashboard tile
```

---

## 5. Local configuration (NOT committed with real values)

| Key | Example | Notes |
|---|---|---|
| `MCP_PRICE_ENABLED` | `false` | must default to `false` |
| `MCP_PRICE_SOURCE_URL` | `https://www.plastemart.com/polymer-pricelist/ldpe-reliance/1/9` | read-only |
| `MCP_PRICE_CACHE_TTL` | `900` | seconds |
| `MCP_PRICE_PORT` | `8790` | localhost only |

Rules:

1. Bind the server to `127.0.0.1` only.
2. Default `MCP_PRICE_ENABLED=false`.
3. Never add these to `.env.example` production sections, `cloudbuild.*`, or
   Cloud Run env.
4. Keep any cached price samples under `sample_data/` (gitignored).

---

## 6. Verification checklist (local only)

```text
  [ ] MCP server starts on 127.0.0.1 and refuses non-local binds
  [ ] get_polymer_price returns a structured payload or stale:true
  [ ] calculate_price math matches §3.1 for a known input
  [ ] dashboard tab shows price + as_of + stale badge
  [ ] no production file references MCP_PRICE_* keys
  [ ] grep confirms no scrape target added to deploy configs
```

### 6.1 Local test commands (do not run against production)

```bash
# start the local MCP price server (example)
python -m mcp_price_server --host 127.0.0.1 --port 8790

# call it as an MCP client (developer machine only)
# (tool call: get_polymer_price { grade: "LDPE", brand: "Reliance" })
```

---

## 7. Explicit non-goals

- No public endpoint.
- No writes to GCS or the production database.
- No change to any deployed branch.
- No scheduled job in production.
- No redistribution of plastemart data.

---

## 8. Deployment status

```text
  Branch   : docs/gcs-kpi-packaging-and-mcp-local
  Deploy   : NEVER (local test only)
  Promote  : requires a new, separate review + explicit approval
```

---

*End of document. This feature is intentionally isolated to local development.*
