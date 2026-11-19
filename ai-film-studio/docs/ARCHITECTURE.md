# Architecture

## Goals

Phase 1 is a local, self-contained studio. It must be useful on a single laptop, work without cloud keys, and leave the existing Kalika Outreach application untouched.

## Runtime topology

```text
Browser (React + Vite, port 5173)
    |
    |  /api proxy
    v
FastAPI (uvicorn, port 8000)
    |-- SQLite: storage/ai_film_studio.db
    |-- Assets: storage/assets
    |-- Renders: storage/previews, storage/exports
    |-- Render worker: background thread
    |     |-- Motion: Node capture pipeline + headless Chrome + FFmpeg
    |     |-- Audio: procedural SFX + loudness-normalised AAC mux
    |     +-- Fallback: Pillow cards + FFmpeg
    |
    +--> Google Cloud Storage (optional publish/gallery)
    +--> Mock AI (in-process, default)
    +--> llama.cpp server (127.0.0.1:8081, optional)
    +--> Gemini API (optional)
    +--> Claude API (optional)
```

The browser never talks to AI providers directly. Keys stay in the backend `.env`.

## Backend layers

- `app/main.py`: application factory, CORS, exception mapping, lifespan seeding, router mounting under `/api/v1`.
- `app/api/routes/`: thin HTTP layer. It validates dependencies, translates domain errors to HTTP status codes, and delegates to services.
- `app/api/deps.py`: project, render, and asset lookups plus asset response shaping.
- `app/services/film/`: script and storyboard domain logic. Prompts live here, not in routes.
- `app/services/ai/`: provider adapters, model catalog, task routing, cache, and usage accounting.
- `app/services/media/`: render worker, motion renderer, audio mixer, card fallback, frame drawing, FFmpeg encoding, asset storage.
- `app/services/storage/`: optional GCS adapter for status, uploads, gallery, manifests, and render publishing.
- `app/models.py` and `app/schemas.py`: persistence and transport contracts.

Routes should not contain prompt text or render logic. Services should not raise `HTTPException`.

## Data model

- `Project` has one `Script`, one `Storyboard`, and many `RenderJob` records. Deleting a project cascades to all three.
- `Storyboard` has ordered `Scene` records. Scenes cascade on storyboard deletion.
- `Scene.asset_id` points at an optional library asset and is set to null if the asset is deleted.
- `AIUsage` records provider, model, task, tokens, estimated cost, and project.
- `Activity` powers the dashboard feed.
- `Setting` is reserved for future persisted preferences.

SQLite foreign keys are enabled on every connection. ORM cascades are also declared so deletes work through the session.

## AI routing

`AIService` reads the selected model from `Setting` or falls back to `mock-ai` when `MOCK_AI=true`. Each provider implements:

- `test_connection(model)` for the AI Usage page.
- `generate(prompt, system, max_tokens, temperature)` returning text plus token usage.

The router:

1. Resolves the selected model.
2. Caches deterministic requests when `AI_CACHE_TTL_SECONDS > 0`.
3. Calls the provider with retries.
4. Records `AIUsage` and returns a normalized `AIResult`.

Development mode defaults to MockProvider. It returns deterministic scripts and storyboard lines, so the full workflow works offline and costs nothing.

## Render pipeline

1. `POST /projects/{id}/renders` validates that a storyboard exists, is approved, and has scenes.
2. A `RenderJob` row is created and a daemon thread starts. The request selects `engine=motion` or `engine=cards`; the default comes from `RENDER_MODE`.
3. The worker loads the project, storyboard, and scenes in its own session.
4. In `motion` mode, the backend builds a generated page from the storyboard:
   - It chooses a palette, one of twelve style presets, a scene pattern, transition, camera move, and effect set.
   - It selects a scene asset or the best image-library match, normalises it with Pillow, and copies it into the page.
   - In live mode it can ask the selected model for palette/pattern/camera/effects direction, then validates and merges the JSON.
   - The vendored Lemo capture core serves the page to headless Chrome, calls `window.render(t)` for every frame, and pipes JPEG screenshots into FFmpeg.
   - `isometric` and chart-led scenes can render through a Three.js/WebGL canvas layered above the 2D canvas.
5. When audio is enabled, `AudioMixer` builds a deterministic procedural bed from scene patterns and transitions, then muxes it with AAC and `loudnorm`. Audio failures fall back to the silent render.
6. If motion is unavailable or fails, the worker logs the reason and falls back to cards when `MOTION_FALLBACK_TO_CARDS=true`.
7. In `ffmpeg`/card mode, Pillow draws one gradient scene card per scene and FFmpeg concatenates them at preview (640x360) or export (1280x720) resolution.
8. `quality=both` renders motion once at export resolution and downscales it for the preview; card mode encodes each quality separately.
9. Progress and logs are committed to the job row. The frontend subscribes to `/renders/{id}/events` (SSE) and also polls while a job is active.
10. On success the project status becomes `rendered`, outputs are probed with `ffprobe`, and GCS publishing runs when enabled.
11. On failure the error is stored and shown in the UI.

`RENDER_MODE=simulated` skips media encoding and walks through stages quickly. It is used by the test suite and is useful when FFmpeg is unavailable.

Cancellation is cooperative: the worker checks the job status while rendering. The motion worker terminates its Node process tree and FFmpeg children on cancel or timeout. In card mode an FFmpeg subprocess already running is allowed to finish, then the next status check stops further work.

## Motion renderer

`renderer/core/render/` is vendored from Lemo-Opuscar under the MIT license. It provides the browser capture, frame pacing, segment encoding, and segment concatenation. AI Film Studio owns `renderer/template/` and generates the page data; no Lemo documentation or style prompts are copied.

The generated page exposes a small contract:

- `window.READY = true` when assets and fonts are ready.
- `window.DUR` is the total duration in seconds.
- `window.render(t)` draws the frame at time `t`.

The page lives outside the renderer directory and is mounted at `/@film/` by the capture server. Scene images are copied into `assets/` under that page, so the renderer never needs network access.

The template is layered: `#three` hosts an optional Three.js scene and `#stage` hosts the 2D canvas. Film.js loads Three.js through an import map, builds bars/slabs/grids/rings from chart data for `isometric` scenes, and applies the requested camera move. The 2D canvas remains the fallback when WebGL is unavailable.

The backend requires Node 20+, `playwright-core`, Three.js, Chrome or Edge, and FFmpeg. `scripts/setup_renderer.ps1` checks the binaries and installs the Node dependencies. Chrome is launched headlessly with the local page; keys and project data are never sent to a browser vendor.

## Cloud storage

`app/services/storage/gcs_service.py` wraps `google-cloud-storage` with Application Default Credentials. Publishing writes the preview/export, a manifest, and metadata under `GCS_PREFIX/renders/{project}/{job}/`; asset uploads mirror under `GCS_PREFIX/assets/`. Status and gallery endpoints degrade to `503` when credentials or the SDK are unavailable, and auto-publish failures are logged without failing the render.

## Frontend structure

- React Router with an app shell and nested project workspace routes.
- TanStack Query owns server state: dashboard, projects, scripts, storyboards, renders, assets, models, usage.
- Zustand owns local UI state: toasts, sidebar, and the persisted creation wizard.
- `services/api.ts` is the only place that knows URLs and response shapes.
- `components/ui` contains small shadcn-style primitives built with Tailwind and class-variance-authority. No component library runtime is required.
- Pages compose primitives and query hooks. They do not call `fetch` directly.

The visual system uses CSS variables for colors, a dark radial background, glass panels, violet primary actions, and cyan accents. Motion is limited to page transitions, card layout, modals, and toasts.

## Security and privacy

- No cloud calls in mock mode.
- Keys live in `.env`, which is gitignored.
- Uploads are size-limited to 100 MB and stored under `storage/assets`.
- The local API has no authentication because it binds to localhost. Do not expose it to a network without adding auth and restricting CORS.
- The llama.cpp server is started on `127.0.0.1` only.
- The motion renderer uses a local headless Chrome process and a local page. It does not upload assets or call AI providers from the browser.

## Phase 1 boundaries

- No deployment workflow or containers.
- Cloud storage is optional and uses local Application Default Credentials; the studio still runs fully offline.
- The motion engine vendors only the MIT-licensed Lemo capture core; CC BY-NC Lemo documentation and style prompts are excluded.
- No AI image generation, voiceover, or timeline compositing. Motion uses local images, procedural graphics, Three.js geometry, and typography.
- No multi-user accounts or collaboration.
