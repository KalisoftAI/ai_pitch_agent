# AI Film Studio

Local-first production studio for short business videos. Pick a category, choose a topic, generate a script, shape a storyboard, and render a motion-graphics preview with the local motion engine or a fast card fallback. Everything runs locally; cloud storage and live AI are optional.

This is Phase 1: a working local product, not a cloud deployment.

## What is included

- Premium dark React interface (Vite, TypeScript, Tailwind, Framer Motion, TanStack Query, Zustand).
- FastAPI backend with SQLite, SQLAlchemy 2, and versioned `/api/v1` routes.
- Three content categories: Business Tips, ERP & Production App Walkthroughs, Financial Education.
- Script drafting, paragraph rewrites, approval gates.
- Storyboard generation, inline scene editing, reordering, per-scene regeneration, approval.
- Background motion-graphics rendering with a local Node/Chrome/FFmpeg engine, plus a Pillow card fallback. Live progress via SSE, logs, cancel, preview and 720p export.
- Procedural sound design and loudness-normalised audio mux, optional per render.
- Optional Google Cloud Storage publishing for renders and library assets, with a cloud gallery.
- Asset library with uploads, tags, favorites, and local file serving.
- AI model catalog: Mock, local Gemma via llama.cpp, Gemini, Claude. Mock is the default in development.
- Token and cost tracking with a monthly budget.
- Seed data: three sample projects, topics, and a sample asset.

## Quick start

Prerequisites: Python 3.12+ (3.14 works), Node 20+, npm, FFmpeg on `PATH`, and Chrome or Edge.

```powershell
cd ai-film-studio
powershell -ExecutionPolicy Bypass -File scripts\setup_renderer.ps1
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
```

- UI: http://localhost:5173
- API: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs

The backend seeds sample data on first start. The frontend proxies `/api` to port 8000.

### Manual start

```powershell
cd ai-film-studio
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt

cd backend
..\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

```powershell
cd ai-film-studio
powershell -ExecutionPolicy Bypass -File scripts\setup_renderer.ps1

cd frontend
npm install
npm run dev
```

## Motion renderer

Motion is the default render mode. The backend generates a local scene page from the approved storyboard, serves it to headless Chrome through the vendored Lemo-Opuscar capture pipeline, and pipes JPEG frames into FFmpeg.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_renderer.ps1
```

The setup script checks Node 20+, npm, FFmpeg, and Chrome/Edge, then installs `playwright-core` and Three.js in `renderer`. Use `-SkipInstall` to run only the checks.

- Twelve style presets and twelve scene patterns, including `cinematic`, `editorial`, `neon`, `swiss`, `data`, `isometric`, `typographic`, `infographic`, `walkthrough`, `documentary`, and `story`.
- Eleven transitions (`fade`, `slide`, `wipe`, `zoom`, `cut`, `dissolve`, `glitch`, `whip`, `push`, `iris`, `blur`), ten post effects, and seven camera moves.
- WebGL/Three.js scenes for `isometric` and chart-led patterns, with the 2D canvas as the fallback.
- Procedural sound effects, a normalised bed, and AAC muxing; disable with `audio=false` or `MOTION_AUDIO=false`.
- With live AI enabled, the selected model can direct palette, pattern, camera, effects, and kicker text. Mock mode uses a deterministic local plan.
- If motion is unavailable or fails, the backend falls back to the card renderer unless `MOTION_FALLBACK_TO_CARDS=false`.
- `quality=both` renders the export once and downscales it for the preview.
- Only the MIT-licensed capture core is vendored. Lemo's CC BY-NC documentation and style prompts are not included.

## Cloud storage

GCS is optional. Enable it with Application Default Credentials (`gcloud auth application-default login`) and these settings:

```env
GCS_ENABLED=true
GCS_BUCKET=sales-crm
GCS_PREFIX=marketing-videos
GCS_AUTO_PUBLISH=true
```

Published renders land under `marketing-videos/renders/{project}/{job}/` with a manifest and metadata. Library uploads are mirrored under `marketing-videos/assets/`. The Render page shows the cloud gallery and can publish completed jobs manually.

```http
GET  /storage/status
GET  /storage/objects?prefix=renders/&limit=50
GET  /storage/gallery?limit=24
POST /renders/{job_id}/publish
```

## Local AI with Gemma 4

The model download is already supported by `scripts/download_models.py`. The selected model is the official QAT Q4 GGUF:

- `gemma-4-12b-it-qat-q4_0.gguf` (6.5 GB)
- `mmproj-gemma-4-12b-it-qat-q4_0.gguf` (0.16 GB)

```powershell
cd ai-film-studio
.\.venv\Scripts\python scripts\download_models.py
powershell -ExecutionPolicy Bypass -File scripts\download_llama.ps1
powershell -ExecutionPolicy Bypass -File scripts\start_gemma.ps1
```

Then set live mode in `.env`:

```env
MOCK_AI=false
APP_MODE=live
GEMMA_BASE_URL=http://127.0.0.1:8081/v1
```

Restart the backend. The model appears as `local-gemma-4-12b` and can be tested from the AI Usage page.

### Hardware reality on this machine

Measured on the target laptop (8 GB RAM, Intel i5, NVIDIA GT 740 that cannot be used by modern llama.cpp CUDA builds):

- Model load: about 53 seconds.
- Prompt processing: about 1.2 tokens/second.
- Free RAM during inference: under 0.5 GB, so Windows swaps.
- A 48-token response did not finish within 180 seconds.

A 12B Q4 model does not fit comfortably in 8 GB. For real local generation, use the mock model while designing, keep prompts and context small (`-Context 512` or `1024`), or download a smaller Gemma variant such as a 4B QAT GGUF and point `GEMMA_MODEL_PATH` and `GEMMA_MODEL_ID` at it. The application itself does not care which GGUF is loaded.

## Configuration

Copy `.env.example` to `.env` and edit as needed. Important settings:

| Setting | Default | Purpose |
| --- | --- | --- |
| `APP_MODE` | `development` | `development` or `live` |
| `MOCK_AI` | `true` | Zero-cost deterministic AI responses |
| `RENDER_MODE` | `motion` | `motion`, `ffmpeg`, or `simulated` |
| `MOTION_CHROME_PATH` | empty | Optional Chrome/Edge executable override |
| `MOTION_FPS` | `24` | Motion render frame rate |
| `MOTION_WORKERS` | `2` | Parallel Chrome/FFmpeg workers |
| `MOTION_TIMEOUT_SECONDS` | `3600` | Hard timeout for a motion render |
| `MOTION_FALLBACK_TO_CARDS` | `true` | Use card rendering if motion fails |
| `MOTION_AI_DIRECTION` | `true` | Let the selected model direct motion style in live mode |
| `MOTION_AI_TIMEOUT_SECONDS` | `25` | AI direction timeout before local fallback |
| `MOTION_AUDIO` | `true` | Build and mux the procedural sound bed |
| `MOTION_AUDIO_SR` | `48000` | Audio sample rate |
| `MOTION_EFFECTS` | `grain,vignette,particles` | Default effect set when the request omits one |
| `GCS_ENABLED` | `false` | Publish renders and assets to Google Cloud Storage |
| `GCS_BUCKET` | `sales-crm` | Target bucket |
| `GCS_PREFIX` | `marketing-videos` | Root folder inside the bucket |
| `GCS_PROJECT` | empty | Optional GCP project override for ADC |
| `GCS_AUTO_PUBLISH` | `true` | Publish completed renders automatically |
| `GCS_TIMEOUT_SECONDS` | `60` | Upload/request timeout |
| `DATABASE_URL` | `sqlite:///./storage/ai_film_studio.db` | SQLite database |
| `STORAGE_DIR` | `./storage` | Projects, assets, previews, exports |
| `GEMMA_BASE_URL` | `http://127.0.0.1:8081/v1` | llama.cpp OpenAI-compatible server |
| `GEMINI_API_KEY` | empty | Enables Gemini models |
| `ANTHROPIC_API_KEY` | empty | Enables Claude models |
| `AI_MONTHLY_BUDGET_USD` | `25` | Budget indicator |

## API overview

All routes are under `/api/v1`.

- `GET /health`
- `GET /dashboard`, `GET /activity`
- `GET/POST /projects`, `GET/PATCH/DELETE /projects/{id}`, `POST /projects/{id}/progress`
- `GET /topics/categories`, `GET /topics`, `GET /topics/suggest`, `POST /topics/custom`
- `GET/POST/PUT /projects/{id}/script`, `POST .../generate`, `POST .../regenerate-paragraph`, `POST .../approve`
- `GET/POST /projects/{id}/storyboard`, `POST .../generate`, `PATCH .../scenes/{scene_id}`, `POST .../scenes/reorder`, `POST .../scenes/{scene_id}/regenerate`, `POST .../approve`
- `GET /ai/models`, `POST /ai/models/select`, `POST /ai/models/{id}/test`, `POST /ai/generate`, `GET /ai/usage`
- `POST/GET /projects/{id}/renders` (`engine=motion|cards`, `motion_style`, `effects`, `audio`, `scene_patterns`), `GET /renders/{job_id}`, `GET /renders/{job_id}/logs`, `POST /renders/{job_id}/cancel`, `GET /renders/{job_id}/events`, `GET /renders/{job_id}/preview`, `GET /renders/{job_id}/export`, `POST /renders/{job_id}/publish`
- `GET /storage/status`, `GET /storage/objects`, `GET /storage/gallery`, `POST /storage/upload`, `DELETE /storage/object`
- `POST/GET /assets`, `GET/PATCH/DELETE /assets/{id}`, `GET /assets/{id}/file`

See `docs/API.md` for request examples.

## Tests and checks

```powershell
cd ai-film-studio\backend
..\.venv\Scripts\python -m pytest

cd ..\frontend
npm run typecheck
npm run build
```

The backend tests use a temporary SQLite database and simulated rendering.

## Project layout

```text
ai-film-studio/
  backend/
    app/
      api/routes/      projects, topics, scripts, storyboards, ai, rendering, assets, dashboard
      core/            settings and database
      services/ai/     providers, pricing, routing
      services/film/   script and storyboard logic
      services/media/  motion renderer, audio mixer, FFmpeg/card renderer, asset storage
      services/storage/ GCS publishing, gallery, and object operations
      models.py        SQLAlchemy models
      schemas.py       Pydantic contracts
      main.py          FastAPI app
    tests/
  frontend/
    src/
      components/      layout and UI primitives
      pages/           dashboard, wizard, script, storyboard, render, assets, AI, settings
      hooks/           TanStack Query hooks
      stores/          Zustand stores
      services/api.ts  typed API client
  renderer/            vendored MIT capture core, motion template, playwright-core
  scripts/             download, setup, start, and dev helpers
  storage/             local database, assets, previews, exports, models, tools
  docs/
```

## Phase 1 boundaries

- No GCP deployment and no changes to the existing Kalika Outreach production app.
- The motion engine vendors only the MIT-licensed Lemo capture core. Lemo's CC BY-NC documentation and style prompts are not embedded.
- The renderer uses local images, procedural graphics, typography, and motion. It does not generate AI imagery or voiceover yet.
- The development branch is intentionally separate and should not be merged into `main`.

## Troubleshooting

- `npm run dev` cannot reach the API: confirm the backend is on port 8000.
- `FFmpeg missing`: install FFmpeg and ensure `ffmpeg -version` works, or set `FFMPEG_BIN` to the full path.
- Motion renderer unavailable: run `scripts\setup_renderer.ps1`; confirm Node 20+, `renderer\node_modules\playwright-core`, Chrome/Edge, and FFmpeg.
- Motion render fails and cards appear instead: this is the configured fallback. Set `MOTION_FALLBACK_TO_CARDS=false` to surface the motion error instead.
- Port already in use: change the backend port and update `vite.config.ts`, or stop the old process.
- Reset the studio: stop the backend, delete `storage/ai_film_studio.db`, and restart. Seeded data is recreated.
- PowerShell blocks scripts: use `powershell -ExecutionPolicy Bypass -File <script>`.
- Local Gemma times out: this is expected on 8 GB RAM with the 12B model. Use mock mode or a smaller GGUF.
