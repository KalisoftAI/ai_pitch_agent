# Kalika Enterprises — Media & Content Pipeline (Companion Doc)

> Companion to `Kalika_Real_Time_Customer_Feedback_System.md` (sections 16–17).
> Covers: content flow diagrams (ASCII), ready image-generation prompts (ChatGPT / other tools),
> LinkedIn post copy, and the video pipeline future scope (ffmpeg + YouTube Data API from the backend,
> with Claude Desktop as the content-review station).
> Data basis: live stats as of 30-Oct-2026 (contacts 8,795 · chats 85 · messages 4,419 · attachments 528 ·
> sales Jan–Sep-2026: 5,149 invoices, ₹27.58 Cr gross, 124 customers).

---

## 1. Content Flow — Current State (ASCII)

```text
+-------------------- LIVE DATA ----------------------+
| GCS: contacts (8,795) | sales registers (5,149 inv) |
| chats dump (4,419 msgs, 528 attachments)            |
| ERP reports (orders/dispatch) | rate list (13)      |
+-------------------------+---------------------------+
                          v
              PRE-PROCESSING (backend)
     interaction_dump.json | graph (networkx) | segments
                          v
              PERSONALIZED MESSAGES (templates WA-*)
                 user selects template per segment
                          v
              SEND: wa.me click-to-send / queue
                          v
              FEEDBACK LOOP: webhook -> intent -> next action
                          v
              DASHBOARD KPIs (/api/kpi/*, pipeline stats)
```

## 2. Image Generation Prompts (ready to paste)

Use in ChatGPT (DALL·E), Midjourney, or similar. Brand: Kalika Enterprises — industrial packaging
manufacturer, Ahmednagar, India. Palette: deep blue #1F4E79 + orange accent; clean industrial style.

| # | Purpose | Prompt |
|---|---|---|
| IMG-1 | Product hero (catalogue cover) | "Professional product photography of industrial packaging materials arranged on a clean warehouse floor: rolls of stretch film, BOPP tape, VCI bags, tarpaulin, knitted hand gloves — soft daylight, deep blue and orange brand accents, shallow depth of field, 4k, no text" |
| IMG-2 | Stretch film close-up | "Macro shot of a clear stretch film roll unwinding, light refracting through the film layers, industrial background softly blurred, blue-grey tones, product-advertising quality" |
| IMG-3 | WhatsApp follow-up banner | "Flat-design banner for a B2B WhatsApp follow-up message from an industrial packaging company: subtle film-roll and tape icons, lots of white space, deep blue header band with orange accent line, minimal, no text" |
| IMG-4 | LinkedIn company banner | "LinkedIn banner 1584x396 style composition: modern packaging factory line with rolls of film moving through machinery, cinematic depth, deep blue color grade with warm orange highlights, professional B2B mood, space on the left for headline text" |
| IMG-5 | Customer feedback infographic | "Clean infographic illustration: a delivery truck, a star rating row, and a chat bubble connected by a circular arrow loop, flat vector style, deep blue and orange palette, white background, no text" |
| IMG-6 | Expo follow-up card (Packvision) | "Friendly B2B thank-you card graphic for an exhibition follow-up: abstract exhibition booth shapes, packaging product silhouettes, flat vector, blue/orange, generous white space, no text" |
| IMG-7 | Gloves product line | "Studio photo of knitted industrial hand gloves in three sizes (40/60/80 gm) standing in a row on seamless grey background, crisp lighting, safety-catalog style" |
| IMG-8 | Video thumbnail frame | "YouTube thumbnail background: dramatic side-lit stretch film roll in the foreground, factory bokeh behind, bold empty space at top for title text, high contrast, cinematic" |

## 3. LinkedIn Post Copy (ready)

**Post 1 — Feedback system launch (with IMG-5):**

> Every package we ship now asks a question back. 📦⭐
>
> Kalika Enterprises has started a real-time customer feedback flow: after each delivery our customers can rate the experience, report an issue, or request rates — directly on WhatsApp, in under a minute.
>
> What we measure now: delivery satisfaction, product-level feedback, complaint resolution time, and the most-requested improvements — all on one dashboard.
>
> Stretch film · BOPP tape · VCI bags · Tarpaulin · HDPE/Poly bags · Knitted gloves — manufactured in Ahmednagar, delivered across Maharashtra and beyond.
>
> #packaging #manufacturing #customerexperience #b2b #makeinindia

**Post 2 — Behind the scenes (with IMG-1 or IMG-2):**

> From our floor to your dispatch dock: stretch film at ₹168/kg, VCI bags at ₹182/kg, BOPP tape from ₹30/pc — with batch-tracked quality and delivery updates on WhatsApp.
> This quarter alone: 5,000+ invoices served to 120+ industrial customers.
> Reply RATE for today's rate card. #industrialpackaging #supplychain

## 4. Video Pipeline — FUTURE SCOPE (ffmpeg + YouTube Data API, backend-driven)

```text
+---------------------------- INGEST ---------------------------------+
| factory photos / clips (WhatsApp attachments dump: 528 media,        |
| 7 videos today) | product shots (IMG-1..8) | catalogue PDF           |
+----------------------------------+-----------------------------------+
                                   v
+---------------------------- ASSEMBLE (backend worker) --------------+
| ffmpeg service (sales_fastapi/media_service.py — future):            |
|  - normalize clips: -vf scale=1280:720 -r 30 -pix_fmt yuv420p        |
|  - title cards from templates (drawtext, brand colors)               |
|  - stitch: concat filter; captions from message templates            |
|  - audio bed: royalty-free track ducked -8dB under VO                |
+----------------------------------+-----------------------------------+
                                   v
+---------------------------- REVIEW GATE (human) ---------------------+
| draft mp4 + auto thumbnail -> Claude Desktop / internal review:      |
| script, captions, compliance check (rates, claims) before publish    |
+----------------------------------+-----------------------------------+
                                   v
+---------------------------- PUBLISH (YouTube Data API v3) -----------+
| backend: google-api-python-client (already in requirements)          |
|  videos.insert (resumable upload) -> thumbnails.set ->               |
|  playlistItems.insert ('Product demos' / 'Customer stories')         |
| OAuth scope: youtube.upload (+ youtube.readonly for analytics)       |
+----------------------------------+-----------------------------------+
                                   v
+---------------------------- MEASURE ---------------------------------+
| youtube.readonly: views, avg view duration -> kpi/website tile;      |
| link clicks back to wa.me feedback flow (UTM tagged)                 |
+----------------------------------------------------------------------+
```

| Component | Status | Notes |
|---|---|---|
| Media source | READY | 528 attachments already catalogued in interaction dump (420 images usable as b-roll/stills) |
| ffmpeg assembly service | FUTURE | `media_service.py` worker; job type via existing scheduler (`video_render` cron) |
| Review gate | FUTURE | Claude Desktop used manually today for copy review; automate later via llm tasks |
| YouTube API publish | FUTURE | google-api-python-client already a dependency; add youtube.upload OAuth scope |
| Shorts cut-downs | FUTURE | ffmpeg crop 9:16 from 16:9 masters; per-product 30s cuts |
| Analytics loop | FUTURE | YouTube Analytics API → /api/kpi/website tile |

## 5. Operating Cadence (combined)

| When | Action | Owner |
|---|---|---|
| Hourly | pipeline_feedback_due cron sends due messages | backend |
| Daily 02:00 | build_interaction_dump (chats+outbox → JSON) | backend |
| Daily 02:30 | rebuild_graph_preprocessing (networkx → exports) | backend |
| Weekly | 1 LinkedIn post (IMG-x + copy above) + review feedback KPIs | marketing |
| Monthly | 1 product video (ffmpeg assembly → review → YouTube) — future scope | marketing + backend |
