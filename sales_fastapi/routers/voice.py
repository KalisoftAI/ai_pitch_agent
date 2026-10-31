"""Voice transcription API (API-only surface).

Endpoints:
  GET  /api/voice/status                 config + file counts
  GET  /api/voice/files                  list audio under the GCS prefix
  POST /api/voice/transcribe             run L0 probe + L1 (Gemini if key) + L2-L4
  POST /api/voice/ingest                 accept an external ASR transcript -> L2-L4
  GET  /api/voice/transcripts            list results
  GET  /api/voice/transcripts/{id}       full result
  POST /api/voice/provision/{id}         create/refresh contact + journey event (lead provisioning)
  GET  /api/voice/stats                  aggregate numbers
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..customer_journey import record_event
from ..database import get_db
from ..models import Contact, JourneyEvent, SyncRun, User, VoiceTranscript
from ..security import get_current_user
from ..voice_analysis import (
    MODEL_DEFAULT, SUPPORTED_SUFFIXES, analyze, heuristic_layers, ollama_available, ollama_models,
    probe_audio, transcribe_with_gemini,
)

router = APIRouter(prefix="/voice", tags=["voice"])

BUCKET = "kalika_enterprises"
PREFIX = settings.VOICE_GCS_PREFIX


class TranscribeIn(BaseModel):
    file: str = Field(default="all", description="exact blob name or 'all'")
    force: bool = False


class IngestIn(BaseModel):
    gcs_path: str = ""
    file_name: str = ""
    transcript: str = Field(..., min_length=5)
    language: str = "mixed"
    duration_sec: float = 0


def _gcs():
    import google.auth
    from google.cloud import storage
    return storage.Client(credentials=google.auth.default()[0]).bucket(BUCKET)


def _audio_blobs():
    return [b for b in _gcs().client.list_blobs(_gcs(), prefix=PREFIX)
            if b.name.lower().endswith(SUPPORTED_SUFFIXES)]


def _row_for(db: Session, path: str) -> VoiceTranscript | None:
    return db.query(VoiceTranscript).filter(VoiceTranscript.gcs_path == path).first()


@router.get("/status")
def status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    blobs = _audio_blobs()
    rows = db.query(VoiceTranscript).filter(VoiceTranscript.gcs_path.like(f"{PREFIX}%")).all()
    return {
        "bucket_prefix": f"gs://{BUCKET}/{PREFIX}",
        "audio_files": len(blobs),
        "processed": sum(1 for r in rows if r.status in ("done", "done_heuristic")),
        "pending_ai": sum(1 for r in rows if r.status == "pending_ai"),
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "model": MODEL_DEFAULT,
        "slm": {
            "preferred": "gemma" if settings.VOICE_SLM_FIRST else "gemini",
            "gemma_model": settings.voice_slm_model,
            "ollama_reachable": ollama_available(settings.LLM_LOCAL_BASE_URL),
            "ollama_models": ollama_models(settings.LLM_LOCAL_BASE_URL),
        },
        "layers": ["L0 audio_probe", "L1 transcribe", "L2 context", "L3 tone", "L4 lead_extract"],
        "sample_files": [b.name for b in blobs[:5]],
    }


@router.get("/files")
def files(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    out = []
    for b in _audio_blobs():
        row = _row_for(db, b.name)
        out.append({"name": b.name, "size_bytes": int(b.size or 0),
                    "updated": str(b.updated), "processed": bool(row),
                    "status": row.status if row else "new"})
    return sorted(out, key=lambda x: x["name"])


def _process_blob(db: Session, user: User, blob, force: bool = False) -> VoiceTranscript:
    row = _row_for(db, blob.name)
    if row and row.status in ("done", "done_heuristic") and not force:
        return row
    if row is None:
        row = VoiceTranscript(gcs_path=blob.name, user_id=user.id)
        db.add(row)
    row.file_name = blob.name.split("/")[-1]
    row.size_bytes = int(blob.size or 0)
    row.gcs_updated = str(blob.updated or "")
    data = blob.download_as_bytes()
    suffix = "." + row.file_name.rsplit(".", 1)[-1].lower()

    audio = probe_audio(data, suffix)          # L0
    row.duration_sec = audio.get("duration_sec", 0)
    row.sample_rate = audio.get("sample_rate", 0)
    row.channels = audio.get("channels", 0)
    row.mean_volume_db = audio.get("mean_volume_db", 0)
    row.max_volume_db = audio.get("max_volume_db", 0)
    row.silence_ratio = audio.get("silence_ratio", 0)

    transcript = ""
    if settings.GEMINI_API_KEY:
        try:                                    # L1
            l1 = transcribe_with_gemini(data, suffix, settings.GEMINI_API_KEY, MODEL_DEFAULT)
            transcript = l1.get("transcript", "")
            row.language = l1.get("language", "")
            row.speakers = {"turns": l1.get("turns", [])}
            row.model = MODEL_DEFAULT
            status_ = "done"
        except Exception as exc:
            row.error = str(exc)[:500]
    else:
        row.error = "GEMINI_API_KEY not configured — audio probed, transcription pending"

    layers = analyze(transcript, audio, settings.GEMINI_API_KEY, MODEL_DEFAULT,
                     slm_first=settings.VOICE_SLM_FIRST,
                     slm_base_url=settings.LLM_LOCAL_BASE_URL,
                     slm_model=settings.voice_slm_model) if transcript else heuristic_layers("", audio)
    row.layers = {"l0_audio": audio, **layers}
    row.tone = layers.get("l3_tone", {})
    row.lead = layers.get("l4_lead", {})
    row.transcript = transcript
    mode = layers.get("mode", "heuristic")
    row.status = "done" if mode in ("gemma", "gemini") else ("done_heuristic" if transcript else "pending_ai")
    if mode == "gemma":
        row.model = layers.get("model", settings.voice_slm_model)
    db.add(SyncRun(job="voice_transcription_sync", status="ok",
                   detail=json.dumps({"file": row.file_name, "status": row.status}),
                   finished_at=datetime.now(timezone.utc)))
    db.commit()
    db.refresh(row)
    return row


@router.post("/transcribe")
def transcribe(payload: TranscribeIn, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    blobs = _audio_blobs()
    if not blobs:
        raise HTTPException(status_code=404, detail=f"no audio files under {PREFIX}")
    targets = blobs if payload.file == "all" else [b for b in blobs if b.name == payload.file]
    if not targets:
        raise HTTPException(status_code=404, detail=f"file not found under {PREFIX}")
    results = [_process_blob(db, user, b, force=payload.force) for b in targets]
    return {"processed": len(results), "gemini_configured": bool(settings.GEMINI_API_KEY),
            "items": [{"id": r.id, "file": r.file_name, "status": r.status,
                       "duration_sec": r.duration_sec, "error": r.error} for r in results]}


@router.post("/ingest")
def ingest(payload: IngestIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """API-only path: accept an external ASR transcript and run L2-L4."""
    path = payload.gcs_path or f"{PREFIX}{payload.file_name or 'external-asr'}"
    row = _row_for(db, path)
    if row is None:
        row = VoiceTranscript(gcs_path=path, user_id=user.id)
        db.add(row)
    row.file_name = payload.file_name or path.split("/")[-1]
    row.duration_sec = payload.duration_sec
    row.language = payload.language
    row.transcript = payload.transcript
    audio = {"duration_sec": payload.duration_sec, "silence_ratio": 0.2}
    layers = analyze(payload.transcript, audio, settings.GEMINI_API_KEY, MODEL_DEFAULT,
                     slm_first=settings.VOICE_SLM_FIRST,
                     slm_base_url=settings.LLM_LOCAL_BASE_URL,
                     slm_model=settings.voice_slm_model)
    row.layers = {"l0_audio": audio, **layers}
    row.tone = layers.get("l3_tone", {})
    row.lead = layers.get("l4_lead", {})
    mode = layers.get("mode", "heuristic")
    row.status = "done" if mode in ("gemma", "gemini") else "done_heuristic"
    row.model = layers.get("model") or ("heuristic" if mode == "heuristic" else MODEL_DEFAULT)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "status": row.status, "tone": row.tone, "lead": row.lead,
            "context": row.layers.get("l2_context", {})}


@router.get("/providers")
def providers(user: User = Depends(get_current_user)):
    """Provider chain used for the layered prompts (Gemma SLM first)."""
    reachable = ollama_available(settings.LLM_LOCAL_BASE_URL)
    models = ollama_models(settings.LLM_LOCAL_BASE_URL) if reachable else []
    return {
        "chain": (["gemma", "gemini", "heuristic"] if settings.VOICE_SLM_FIRST
                  else ["gemini", "gemma", "heuristic"]),
        "gemma": {"model": settings.voice_slm_model, "base_url": settings.LLM_LOCAL_BASE_URL,
                  "reachable": reachable, "models": models,
                  "ready": reachable and settings.voice_slm_model in models},
        "gemini": {"model": MODEL_DEFAULT, "configured": bool(settings.GEMINI_API_KEY)},
        "heuristic": {"ready": True},
    }


@router.get("/transcripts")
def list_transcripts(status: str | None = None, limit: int = Query(default=50, ge=1, le=200),
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(VoiceTranscript)
    if status:
        q = q.filter(VoiceTranscript.status == status)
    rows = q.order_by(VoiceTranscript.id.desc()).limit(limit).all()
    return [{"id": r.id, "file": r.file_name, "status": r.status, "duration_sec": r.duration_sec,
             "language": r.language, "tone": r.tone, "lead": r.lead, "created_at": str(r.created_at)}
            for r in rows]


@router.get("/transcripts/{transcript_id}")
def get_transcript(transcript_id: int, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    r = db.get(VoiceTranscript, transcript_id)
    if not r:
        raise HTTPException(status_code=404, detail="transcript not found")
    return {"id": r.id, "gcs_path": r.gcs_path, "file": r.file_name, "status": r.status,
            "duration_sec": r.duration_sec, "sample_rate": r.sample_rate, "channels": r.channels,
            "mean_volume_db": r.mean_volume_db, "max_volume_db": r.max_volume_db,
            "silence_ratio": r.silence_ratio, "language": r.language, "transcript": r.transcript,
            "speakers": r.speakers, "layers": r.layers, "tone": r.tone, "lead": r.lead,
            "model": r.model, "error": r.error, "created_at": str(r.created_at)}


@router.post("/provision/{transcript_id}")
def provision(transcript_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create (or refresh) a contact/lead from the extracted lead JSON + journey event."""
    r = db.get(VoiceTranscript, transcript_id)
    if not r:
        raise HTTPException(status_code=404, detail="transcript not found")
    lead = r.lead or {}
    phone = (lead.get("phone") or "").strip()
    company = (lead.get("company") or "").strip() or f"Voice lead {r.file_name}"
    name = (lead.get("name") or "").strip()
    email = (lead.get("email") or "").strip()
    if not email:
        import hashlib
        email = f"unknown-{hashlib.md5((company + r.gcs_path).encode(), usedforsecurity=False).hexdigest()[:12]}@placeholder.local"

    contact = None
    if phone:
        contact = (db.query(Contact).filter(Contact.user_id == user.id,
                                            Contact.phone.contains(phone[-10:])).first())
    if contact is None:
        contact = db.query(Contact).filter(Contact.user_id == user.id, Contact.email == email).first()
    created = False
    if contact is None:
        contact = Contact(user_id=user.id, company=company, name=name, email=email, phone=phone,
                          intent="sales", context=f"voice:{r.file_name}", source="voice",
                          gcs_path=r.gcs_path,
                          notes=f"Voice lead: {json.dumps(lead, ensure_ascii=False)[:900]}")
        db.add(contact)
        db.commit(); db.refresh(contact)
        created = True

    stage = {"order": "evaluation", "rate": "interest", "sample": "interest", "support": "retention",
             "not_interested": "retention"}.get(lead.get("intent", ""), "awareness")
    ev = record_event(db, user_id=user.id, contact_id=contact.id,
                      customer_type="new_customer", stage=stage, event="voice_call_analyzed",
                      channel="call", detail=r.transcript[:500],
                      meta={"transcript_id": r.id, "tone": r.tone, "products": lead.get("products", [])})
    return {"contact_id": contact.id, "created": created, "journey_event_id": ev.id,
            "stage": stage, "recommended_template": lead.get("recommended_template", ""),
            "next_action": lead.get("next_action", "")}


@router.get("/stats")
def stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total = db.query(func.count(VoiceTranscript.id)).scalar() or 0
    by_status = {s: c for s, c in db.query(VoiceTranscript.status, func.count())
                 .group_by(VoiceTranscript.status).all()}
    mins = db.query(func.coalesce(func.sum(VoiceTranscript.duration_sec), 0)).scalar() or 0
    sentiments = {}
    for r in db.query(VoiceTranscript).all():
        s = (r.tone or {}).get("sentiment", "unknown")
        sentiments[s] = sentiments.get(s, 0) + 1
    intents = {}
    for r in db.query(VoiceTranscript).all():
        i = (r.lead or {}).get("intent", "unknown")
        intents[i] = intents.get(i, 0) + 1
    return {"transcripts": total, "by_status": by_status,
            "audio_minutes": round(float(mins) / 60.0, 2),
            "sentiment_mix": sentiments, "intent_mix": intents,
            "provisioned": db.query(JourneyEvent).filter(JourneyEvent.event == "voice_call_analyzed").count()}
