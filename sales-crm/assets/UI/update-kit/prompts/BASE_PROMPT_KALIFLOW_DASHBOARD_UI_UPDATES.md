# BASE PROMPT — Kaliflow Dashboard UI Refinement (Existing HTML + GCS)

You are working inside the existing Kalika ERP / Sales CRM repository. Your task is to refine the existing Kaliflow HTML dashboard and integrate it into the current UI, not create a separate application.

## 1. First inspect; do not modify blindly
- Inspect the current Git branch, recent commits, project tree, existing React app, current HTML dashboard, current HTML video templates, routing, CSS conventions, auth/role model, backend API, GCS client and deployment setup.
- Find and read the existing HTML templates under `sales-crm/assets/UI/html-templates/` and existing dashboard source. Compare them with the supplied reference files in this package.
- Identify which file is currently loaded by the application and how it is loaded (React component, iframe, WebView, template loader, or route).
- Locate existing GCS conventions and the exact bucket/object paths already used. Do not assume a bucket or overwrite any existing object.
- Write an inspection report before editing: files to change, files to preserve, current data flow, dependencies, and risks.
- Preserve current working UI, React functionality, login, routing, navigation, role permissions and backend architecture. No broad refactor.

## 2. Target dashboard
Refine the existing HTML into a single-file interactive app (HTML + CSS + JS) using Three.js from a CDN. Dashboard title: “Kaliflow”; company: “Kalika Enterprises, MIDC Ahmednagar / Ahilyanagar”.
Use the approved Kalika logo (navy wordmark, teal K mark, “Industrial E-Commerce”) in the top bar and factory signboard. Embed the exact approved logo as a base64 data URI. If no approved source logo exists in the repository, do not invent a final logo; retain a clearly marked placeholder and request the approved asset.

### Exact palette — CSS variables and JS palette must match
Brand: navy #1F3A8A; deep navy #14265C; teal #3CC4CC; light teal #A8E6EA.
Environment: concrete #E9E4DA; safety yellow #FFC727; walls #F6F2EA; roof edge #D8D2C4; yard #5B6270; grass #9CCB7A; tree greens #5FA55A and #7CBF6A; day sky #BFE6F7 to #FFF3E0; night sky #0B1330 to #1B2A5E.
Machinery: extrusion orange #F26A1B; white #FFFFFF; dark grey #3A404B.

### Visual language
Premium, modern, toy-like clay / low-poly isometric, built entirely in code with no external 3D models. Rounded bevelled geometry; clean surfaces; no noisy textures. Use PCF soft shadows, one warm directional key light and cool hemisphere fill, contact-shadow feel under machines, subtle emissive glow/sprites for screens and lights, soft fog and restrained depth-of-field/tilt-shift impression. Avoid heavy post-processing and keep GPU use reasonable.

## 3. Dashboard UI hierarchy — Sales first
1. Sales overview: MTD revenue, open RFQs, pending dispatch, quote conversion, branch selector, last-sync badge.
2. ERP daily rate cards: product, exact specification, rate, unit, change %, source, effective/updated time. Do not normalize or change UOM silently. Flag source conflicts for review.
3. Manufacturing: material feeding → extrusion → cooling/thickness control → winding → packing → in-house recycling. Show line state, output, target, efficiency and thickness only when live data exists.
4. Inventory and dispatch: available stock, reserved stock, pending orders, ASN, dispatch status and weighing/label integration.
5. Sales executive metrics: assigned accounts, quotes, conversion, response time, completed dispatch and on-time percentage.
6. CRM/Gmail customer drilldown: account, contact, Kalika POC, subject, status, last updated, source thread link where authorized. Do not expose message bodies or attachments to unauthorized roles.
7. GCS sync and data health: bucket/object reference, branch, cache/live source, timestamp, freshness, retry/error state.
8. Video Studio: pattern selector, camera preset, scene list, duration, aspect ratio, preview/capture status and output destination.

## 4. Existing GCS data and API
The supplied sample overview JSON references:
`gs://kalika-erp-prod-data/processed/dashboard-cache/overview_all.json`
and branches:
`ALL`, `AHMEDNAGAR_MIDC`, `PHALTAN_SATARA`, `PUNE_SHIRUR`.
The sample creative JSON references:
`gs://kalika-erp-prod-data/renders/2026-11-21/daily_rates_reel.mp4`.
Treat these as sample references only. Inspect actual repository configuration and GCS objects before using them. Never put service-account credentials, signed private URLs or unrestricted bucket access in client HTML.

Prefer the existing authenticated backend endpoint and session/auth mechanism. If the repository already exposes `/api/v1/dashboard/overview?branch=...`, reuse and verify it; otherwise implement the smallest compatible backend route in the existing framework. Do not assume FastAPI or replace the current backend. The frontend should call a same-origin authenticated API and render explicit loading, stale, empty and error states. GCS access stays server-side.

## 5. Data provenance and correctness
Use supplied JSON samples as fixtures, not live truth. The sample overview has MTD revenue ₹24,85,000, 14 pending ASN/dispatches, 9 RFQ threads, four daily rates, three executive records and two customer conversation records. Sample sync timestamp is 2026-11-21 14:30 IST.
The creative JSON lists Stretch Film 500mm×23µm ₹108/kg; Heavy Duty Stretch Film 500mm×51µm ₹151/kg; BOPP/Brown Tape 48mm×65m ₹34.20/roll; HDPE Tarpaulin 300 GSM ₹4.20/sqft. The overview JSON labels BOPP unit `each`, while creative JSON says `roll`; flag this discrepancy, do not silently resolve it.
Regional commercial stats in the master archive are planning assumptions, not verified quotations or audited financial results. Keep them in a separate “Regional Planning” view and label them “planning assumptions”. Exclude personal investment/tax content from the factory dashboard.

## 6. Visual patterns and refresh controls
Implement selectable presets:
- Fresh Daylight — clean default.
- Midnight Factory — navy/night sky, teal screen glow.
- Cinematic Warm — warm hero lighting.
- Blueprint — technical process walkthrough.
- Teal Studio — clean product/sustainability presentation.
Add camera presets (isometric hero, wide factory, process close-up), day/night, pause/resume, auto-rotate, labels on/off, hide HUD/record mode, and reset camera. Keep controls keyboard accessible and mobile-friendly.
Allow controlled palette tweaking in a settings drawer, with reset-to-brand-default. Never let custom palette edits mutate the canonical palette file.

## 7. HTML template and video integration
- Keep the existing daily-rate template's data contract (`window.renderCreativeData(data)`) compatible unless repository inspection proves a safe versioned migration is needed.
- Preserve current 1080×1920 portrait template and provide landscape 1920×1080 dashboard capture separately. Do not break existing callers.
- Use safe DOM APIs / textContent for untrusted CRM, product or customer strings; do not interpolate untrusted data into innerHTML.
- Keep video templates in `sales-crm/assets/UI/html-templates/` and use the app's existing template discovery/loading mechanism.
- Local rendering must use the existing approved pipeline where available. If needed, use Playwright/Chromium for HTML/Three.js capture and local FFmpeg for encoding. Do not claim rendering succeeded until an MP4 exists and is reviewed.
- Suggested sales-first story: 0–8s Sales KPIs; 8–16s ERP rates; 16–26s 3D production; 26–34s packing/dispatch; 34–42s CRM/Gmail + GCS sync; 42–50s video close/brand frame.

## 8. Implementation safeguards
- Work on a new feature branch or the branch explicitly requested by the owner; never commit directly to main without instruction.
- Before edits, create a safe diff/backup. Make focused changes only.
- No database schema migration unless demonstrably necessary and approved.
- No auth/role model changes.
- No external email, WhatsApp, customer communication, GCS write/delete or deployment without explicit per-action approval.
- Do not overwrite the existing HTML templates; add versioned template files and preserve old ones.
- Do not fabricate live values, production tonnage, OEE, machine speed, inventory, customer status or timestamps.
- Keep demo/sample labels visible until API values are verified.

## 9. Required deliverables
1. `KALIFLOW_UI_REFINEMENT_REPORT.md` — before/after, files changed, files preserved, branch and risks.
2. `KALIFLOW_DATA_MAPPING.md` — every UI metric → API field → source → unit → freshness.
3. Updated HTML template(s) under `sales-crm/assets/UI/html-templates/`.
4. CSS/JS palette and visual pattern config, with exact hex verification.
5. GCS/API integration notes and error-state screenshots.
6. Local FFmpeg render instructions and a reviewed sample MP4 only if rendering succeeds.
7. Test report: desktop, mobile, WebGL fallback, branch switching, stale cache, API failure, permissions, XSS-safe rendering.
8. A concise summary of what is implemented versus pending live credentials/verification.

## 10. Final execution order
Inspect → report → create branch/backup → refine HTML → wire existing API → test data + permissions → validate visual patterns → run local browser capture → FFmpeg encode → review MP4 → report. Stop before any deployment or external write unless separately approved.
