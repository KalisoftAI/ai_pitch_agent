# API quick reference

Base URL: `http://127.0.0.1:8000/api/v1`

Interactive docs: `http://127.0.0.1:8000/docs`

## Health

```http
GET /health
```

```json
{
  "status": "ok",
  "app": "AI Film Studio",
  "mode": "development",
  "mock_ai": true,
  "render_mode": "motion",
  "ffmpeg_available": true,
  "storage": "D:\\...\\ai-film-studio\\storage",
  "gemma_base_url": "http://127.0.0.1:8081/v1",
  "gcs_enabled": false,
  "gcs_bucket": "sales-crm",
  "gcs_prefix": "marketing-videos"
}
```

## Projects

```http
POST /projects
Content-Type: application/json

{
  "title": "Why cash flow matters",
  "category": "business-tips",
  "topic": "Why cash flow matters for a small business",
  "description": "Explain the one metric owners should watch weekly.",
  "visual_style": "cinematic",
  "template": "insight",
  "duration_seconds": 45,
  "aspect_ratio": "16:9"
}
```

```http
GET    /projects
GET    /projects/{project_id}
PATCH  /projects/{project_id}
DELETE /projects/{project_id}
POST   /projects/{project_id}/progress
```

Categories are `business-tips`, `erp-walkthrough`, and `financial-education`.

## Topics

```http
GET  /topics/categories
GET  /topics?category=business-tips
GET  /topics/suggest?category=business-tips&limit=6
POST /topics/custom
```

```json
{
  "category": "financial-education",
  "title": "How to build a 13-week cash forecast",
  "description": "A practical weekly routine."
}
```

## Script

```http
GET  /projects/{project_id}/script
POST /projects/{project_id}/script/generate
PUT  /projects/{project_id}/script
POST /projects/{project_id}/script/regenerate-paragraph
POST /projects/{project_id}/script/approve
```

Generate:

```json
{
  "tone": "confident",
  "audience": "small business owners",
  "instructions": "Keep it under 120 words and use one concrete example."
}
```

Update:

```json
{ "content": "Paragraph one.\n\nParagraph two." }
```

Regenerate one paragraph:

```json
{ "paragraph_index": 1, "instruction": "Make it more concrete." }
```

Approve or unapprove:

```json
{ "approved": true }
```

## Storyboard

```http
GET   /projects/{project_id}/storyboard
POST  /projects/{project_id}/storyboard/generate
PATCH /projects/{project_id}/storyboard/scenes/{scene_id}
POST  /projects/{project_id}/storyboard/scenes/reorder
POST  /projects/{project_id}/storyboard/scenes/{scene_id}/regenerate
POST  /projects/{project_id}/storyboard/approve
```

Generate:

```json
{ "scene_count": 6, "style": "cinematic" }
```

Update a scene (any subset):

```json
{
  "title": "The hidden cost",
  "narration": "Most owners track revenue, not the gap between promise and payment.",
  "visual_prompt": "A dark dashboard with one red metric pulsing.",
  "duration_seconds": 6,
  "transition": "fade"
}
```

Reorder:

```json
{
  "scenes": [
    { "id": "scene-id-1", "order_index": 0 },
    { "id": "scene-id-2", "order_index": 1 }
  ]
}
```

## AI

```http
GET  /ai/models
POST /ai/models/select
POST /ai/models/{model_id}/test
POST /ai/generate
GET  /ai/usage
```

Select:

```json
{ "model_id": "mock-ai" }
```

Generate:

```json
{
  "task": "script",
  "prompt": "Write a 30-second hook about invoice delays.",
  "system": "You are a concise business scriptwriter.",
  "max_tokens": 400
}
```

Tasks used by the app: `classification`, `cleanup`, `tagging`, `short-draft`, `metadata`, `script`, `storyboard`, `motion`, `complex`, `technical`, `quality`, `escalation`.

## Rendering

```http
POST /projects/{project_id}/renders
GET  /projects/{project_id}/renders
GET  /renders/{job_id}
GET  /renders/{job_id}/logs
POST /renders/{job_id}/cancel
GET  /renders/{job_id}/events
GET  /renders/{job_id}/preview
GET  /renders/{job_id}/export
```

Create:

```json
{
  "quality": "both",
  "include_captions": true,
  "engine": "motion",
  "motion_style": "isometric",
  "effects": ["grain", "vignette", "bokeh"],
  "audio": true,
  "scene_patterns": {
    "0": "isometric",
    "1": "infographic"
  }
}
```

`quality` is `preview`, `export`, or `both`. `engine` is `motion` or `cards`; it defaults to the server's `RENDER_MODE`. `motion_style` is one of `cinematic`, `editorial`, `neon`, `minimal`, `swiss`, `data`, `isometric`, `typographic`, `infographic`, `walkthrough`, `documentary`, or `story`. `scene_patterns` maps a zero-based scene index to a pattern; omitted scenes use the style plan. The storyboard must exist and be approved. Motion falls back to cards when unavailable unless `MOTION_FALLBACK_TO_CARDS=false`.

`/events` is a server-sent event stream:

```text
event: progress
data: {"id":"...","status":"running","stage":"rendering frame 3/6","progress":42,"error":null}
```

Preview and export return MP4 files when ready. `POST /renders/{job_id}/publish` uploads the finished files, manifest, and metadata to GCS when storage is enabled.

## Storage

```http
GET    /storage/status
GET    /storage/objects?prefix=renders/&limit=50
GET    /storage/gallery?limit=24
POST   /storage/upload            multipart/form-data: file, folder?, tags?
POST   /renders/{job_id}/publish
DELETE /storage/object?name=renders/...
```

`/storage/status` returns availability plus bucket/prefix information. When GCS is disabled or credentials are missing, storage endpoints return `503` with a readable message and local rendering continues normally.

## Assets

```http
POST   /assets            multipart/form-data: file, tags
GET    /assets?search=&media_type=&tag=&favorite=
GET    /assets/{asset_id}
PATCH  /assets/{asset_id}
DELETE /assets/{asset_id}
GET    /assets/{asset_id}/file
```

Update:

```json
{ "tags": ["product", "dashboard"], "favorite": true }
```

## Dashboard

```http
GET /dashboard
GET /activity?limit=50
```

`/dashboard` returns counts, category counts, recent projects, recent activity, and the AI usage summary.

## Errors

```json
{
  "detail": "Approve the storyboard before rendering.",
  "code": "render_error"
}
```

Common statuses:

- `400`: domain validation such as an unapproved storyboard.
- `404`: missing project, script, storyboard, render, or asset.
- `422`: request validation.
- `502`: provider returned an error.
- `503`: provider is not configured or not reachable.
