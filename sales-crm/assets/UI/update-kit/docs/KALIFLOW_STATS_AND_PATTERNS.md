# Kaliflow — Stats & Patterns Reference

## A. ERP dashboard sample payload (uploaded JSON; not independently verified live)
- Last sync timestamp in sample: 21 Nov 2026, 14:30 IST.
- Sample GCS object: `gs://kalika-erp-prod-data/processed/dashboard-cache/overview_all.json`.
- Branch values: `ALL`, `AHMEDNAGAR_MIDC`, `PHALTAN_SATARA`, `PUNE_SHIRUR`.
- MTD revenue: ₹24,85,000.
- Pending ASN / dispatches: 14.
- Active RFQ threads: 9.
- Daily rate records: 4.
- Sales executive records: 3.
- Level-2 customer conversation records: 2.
- Executive sample: Pratik Nakade — 28 quotes, 64.3% conversion, 2.4h average response; Vaishnavi Bhingare — 19 quotes, 73.6% conversion, 1.8h average response; Narayan Dethe — 42 dispatches completed, 96.5% on-time dispatch.

## B. Sample daily product rates (uploaded JSON; rates and units exactly as supplied)
| Product | Specification | Rate | Unit |
|---|---|---:|---|
| Stretch Film (Hand Grade) | 500mm x 23 Micron | ₹108.00 | kg |
| Heavy Duty Stretch Film | 500mm x 51 Micron | ₹151.00 | kg |
| BOPP / Brown Packaging Tape | 48mm x 65m, 55 Micron | ₹34.20 | roll |
| HDPE Tarpaulin 300 GSM | With eyelets | ₹4.20 | sqft |

The overview JSON lists BOPP Tape as `each`, while the creative JSON says `roll`. Do not silently reconcile; preserve source-specific units and flag for review before public use.

## C. Global 12-region commercial model (user-supplied master archive; planning assumptions, not verified market quotes)
| Metric | Stretch Film $/kg | VCI $/kg | SaaS $/month | FCL + 3M SaaS | Transit |
|---|---:|---:|---:|---:|---:|
| Minimum | 1.30 | 2.35 | 360 | $15,600 | 3d road / 6d sea |
| Median | 1.52 | 2.78 | 650 | $19,725 | 16.0d |
| Mean | 1.54 | 2.81 | 654 | $19,642 | 18.3d |
| Maximum | 1.80 | 3.30 | 900 | $22,700 | 34d |
| Spread | 0.50 (+38.5%) | 0.95 (+40.4%) | 540 (+150%) | 7,100 (+45.5%) | 31d |

Gross-margin bands in the source archive: Stretch Film 24–34%; VCI 36–48%; SaaS 78–86%; blended FCL bundle 34–44%. Working-capital cycle stated as 21–45 days.

## D. Five strategic patterns from the source archive
1. **Zero-Duty + Fast-Cash Corridor:** REG-01 to REG-04; 6–14 day sailing pattern and stated 0–5% FTA tariff assumptions; bundle QR traceability and WhatsApp reorder workflows.
2. **Regulatory Mandate & Downgauging Premium:** REG-05, REG-06, REG-11; lead with 12–15µm downgauged film, nitrite-free VCI and telemetry/ESG reporting.
3. **Nearshoring & High-Humidity Port Protection:** REG-07 to REG-10; longer 18–34 day transit assumptions and VCI liners / UVI stretch / serialized QR certificates.
4. **Software Valuation Multiplier:** separate physical packaging business economics from recurring KalisoftAI SaaS economics; SaaS assumptions $550–$900/month and ~82% gross margin are stated in source.
5. **Personal Wealth & Tax Efficiency:** present in source archive but deliberately excluded from dashboard/business UI scope because it is personal financial planning, not factory operations.

## E. UI / video design patterns
- Sales-first overview: revenue, RFQ, dispatch, quote conversion.
- ERP rate cards with product specification, value, UOM, source and last-updated time.
- Factory process sequence: material feeding → extrusion → cooling/thickness control → winding → packing → recycling.
- Executive performance: quotes, conversion, response time, completed dispatch, on-time percentage.
- Customer drilldown: account, contact, Kalika POC, subject, status, last updated; preserve access control.
- GCS sync state: object key, branch, timestamp, freshness, cache/live source, error state.
- Video studio: scene/pattern selector, camera preset, duration, aspect ratio, capture/render status and output path.

## Data integrity
The uploaded JSON records are sample snapshots. The regional export numbers and patterns are planning assumptions from the uploaded master archive. Verify tariffs, transit times, rates, margins, regulations and current customer status independently before quoting or publishing. Do not expose credentials or sensitive personal/banking data in HTML, JSON or rendered videos.
