# Kaliflow Dashboard UI Update Kit

Copy this folder manually into the repository location requested by the owner:
`sales-crm/assets/UI/html-templates/`

Recommended structure:
- `html-templates/` — original HTML references copied from the supplied uploads. Keep these as references; do not overwrite existing app templates.
- `data/` — supplied JSON fixtures and exact palette.
- `docs/` — statistics, patterns and ASCII architecture.
- `prompts/` — reusable base prompt for the next coding-agent update.
- `references/` — uploaded regional planning master archive.

The existing large HTML reference already includes Three.js r128 from CDN, exact palette CSS variables, a 3D canvas, HUD, KPIs, palette controls and inspector controls. The compact reference is an alternate layout. The daily-rate template is a separate portrait video template with `window.renderCreativeData(data)`.

The uploaded sample JSON includes a sample GCS cache object and a daily-rate render path. These paths must be checked in the actual repository/GCP environment before any live connection. This package does not connect to GCS, deploy, or modify your application.
