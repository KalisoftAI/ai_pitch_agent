# Kalika Voice Transcription & Gemma SLM Pipeline (30-Oct-2026)

> Backend job + API-only surface for call-recording intelligence on
> `gs://kalika_enterprises/call_recording/Vaishnavi-samp/`.
> Provider chain: **Gemma SLM (Ollama) → Gemini 2.5 Flash → deterministic heuristics**.
> Human review stays on for anything customer-facing. ERP remains untouched/prod.

---

## 1. Layered prompt pipeline (ASCII)

```text
 GCS: call_recording/Vaishnavi-samp/  (3 files: 60s m4a, 76s wav, 32s wav)
        │
        v
 L0  AUDIO PROBE      ffprobe + ffmpeg volumedetect/silencedetect
     duration · sample rate · channels · mean/max dB · silence ratio
        │
        v
 L1  TRANSCRIBE       Gemini 2.5 Flash (audio inline) → language + turns
     (needs GEMINI_API_KEY)                    │
        │                                      └─ no key → status pending_ai
        v
 L2  CONTEXT          products · quantities · rates · objections · summary
 L3  TONE             sentiment · urgency · politeness · interest · noise · pace
 L4  LEAD EXTRACT     name/company/phone · intent · products · next action · template
        │
        ├── provider chain: gemma (Ollama) → gemini → heuristic  (mode recorded)
        v
 voice_transcripts  ──> POST /api/voice/provision/{id}
        │                 contact + journey event (stage from intent)
        v
 DASHBOARD / JOURNEY   stories + sentiment/intent mix + recommended template
```

## 2. Provider chain & enablement

| Provider | Needs | Notes |
|---|---|---|
| **Gemma SLM (Ollama)** | `ollama serve` + `ollama pull gemma-4-27b-it` (or configured tag) | preferred (`VOICE_SLM_FIRST=true`), data stays on-device, zero cost |
| Gemini 2.5 Flash | `GEMINI_API_KEY` | required for L1 audio transcription; also fallback for L2–L4 |
| Heuristic | nothing | deterministic; always available; used for CI/tests |

Current runtime: `ollama reachable=false`, `gemini configured=false` → L0 runs for real,
rows stored as `pending_ai` with a clear error, and any ingested transcript is processed
heuristically (verified: lead + tone + provisioning all work).

## 3. API (API-only; no UI required)

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/voice/status` | prefix, file counts, SLM/provider status |
| GET | `/api/voice/files` | list audio + processed flag |
| GET | `/api/voice/providers` | chain order + reachability |
| POST | `/api/voice/transcribe` | run job (`{"file":"all","force":true}`) |
| POST | `/api/voice/ingest` | external ASR transcript → L2–L4 |
| GET | `/api/voice/transcripts` | list results (tone/lead) |
| GET | `/api/voice/transcripts/{id}` | full record incl. audio facts + layers |
| POST | `/api/voice/provision/{id}` | create/refresh contact + journey event |
| GET | `/api/voice/stats` | totals, audio minutes, sentiment/intent mix |

## 4. Scheduler

| Job | IST | UTC |
|---|---|---|
| `voice_transcription_sync` | 09:00 | `30 3 * * *` |

Executor: `python scripts/voice_sync.py [--force]` (same code path as the API).
18 cron tasks registered; the job uses the Gemma-first chain automatically.

## 5. Current numbers (live)

| File | Duration | Status |
|---|---|---|
| AUD-20260109-WA0005.m4a | 60.05 s | pending_ai (audio probed) |
| record-1793186132125.wav | 76.22 s | pending_ai (audio probed) |
| record-1793187022137.wav | 31.62 s | pending_ai (audio probed) |

Demo ingest → lead: phone 9822000000, products [VCI bags], 500 kg, intent `order`,
tone positive/high urgency → provisioning created contact **8796**, journey stage `evaluation`,
recommended template **WA-ORD-01**.

## 6. Enable Gemma SLM (deploy steps)

```bash
# on the host / Cloud Run sidecar
ollama serve &
ollama pull gemma-4-27b-it
# env
VOICE_SLM_FIRST=true
VOICE_SLM_MODEL=gemma-4-27b-it
LLM_LOCAL_BASE_URL=http://localhost:11434
# optional cloud: GEMINI_API_KEY=...  (needed for L1 transcription of audio)
```

Then `python scripts/voice_sync.py --force` or `POST /api/voice/transcribe`.
