"""Voice pipeline tests: audio probe, layered prompts, heuristics, API ingest,
lead provisioning, and status/stats endpoints. No network calls required.
"""

import io
import math
import struct
import wave

import pytest

from sales_fastapi.voice_analysis import (
    PROMPTS,
    analyze,
    heuristic_layers,
    probe_audio,
)

SAMPLE_TRANSCRIPT = (
    "Agent: Namaste sir, Kalika Enterprises se baat kar rahe hain. "
    "Customer: Haan ji, mujhe 500 kg VCI bags chahiye, 50 micron. Rate kya hai? "
    "Agent: VCI bags 182 rupees per kg. Customer: Theek hai, kal tak quotation bhej dijiye, urgent hai. "
    "Mera number 9822000000 hai. Agent: Ji bilkul, thank you."
)


def _wav_bytes(seconds=1.0, rate=16000, freq=440.0):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = b"".join(
            struct.pack("<h", int(12000 * math.sin(2 * math.pi * freq * t / rate)))
            for t in range(int(rate * seconds))
        )
        w.writeframes(frames)
    return buf.getvalue()


# ---------------------------------------------------------------- L0 probe
def test_probe_audio_reads_duration_and_volume():
    stats = probe_audio(_wav_bytes(1.0), ".wav")
    assert stats["duration_sec"] == pytest.approx(1.0, abs=0.2)
    assert stats["sample_rate"] == 16000
    assert stats["channels"] == 1
    assert stats["mean_volume_db"] < 0  # negative dBFS
    assert 0.0 <= stats["silence_ratio"] <= 1.0


def test_probe_audio_never_raises_on_garbage():
    stats = probe_audio(b"not-audio", ".wav")
    assert stats["duration_sec"] == 0.0 and stats["probe"] in ("unavailable", "ffprobe")


# ---------------------------------------------------------------- layers
def test_layer_prompts_defined():
    assert set(PROMPTS) == {"l1_transcribe", "l2_context", "l3_tone", "l4_lead"}
    for name, text in PROMPTS.items():
        assert len(text) > 60, name
    assert "{transcript}" in PROMPTS["l2_context"]
    assert "{acoustics}" in PROMPTS["l3_tone"]
    assert "{context}" in PROMPTS["l4_lead"]


def test_heuristic_layers_extract_lead_context_tone():
    audio = {
        "duration_sec": 40.0,
        "mean_volume_db": -22.0,
        "max_volume_db": -3.0,
        "silence_ratio": 0.18,
        "channels": 1,
        "sample_rate": 16000,
    }
    out = heuristic_layers(SAMPLE_TRANSCRIPT, audio)
    assert out["mode"] == "heuristic"
    ctx = out["l2_context"]
    assert "VCI bags" in ctx["products"]
    assert any("kg" in q for q in ctx["quantities"])
    assert ctx["rates_quoted"]
    tone = out["l3_tone"]
    assert tone["sentiment"] in ("positive", "neutral", "negative")
    assert tone["urgency"] == "high"  # "urgent"
    assert tone["interest"] == "high"
    assert tone["noise"] in ("clean", "some", "noisy")
    lead = out["l4_lead"]
    assert lead["phone"] == "9822000000"
    assert lead["intent"] == "order"
    assert "VCI bags" in lead["products"]
    assert lead["recommended_template"].startswith("WA-")


def test_analyze_falls_back_without_key():
    out = analyze(SAMPLE_TRANSCRIPT, {"duration_sec": 30}, api_key="")
    assert out["mode"] == "heuristic"


def test_negative_tone_and_intent():
    out = heuristic_layers(
        "Customer: no need, expensive hai, late delivery problem thi", {"silence_ratio": 0.05}
    )
    assert out["l3_tone"]["sentiment"] == "negative"
    assert out["l4_lead"]["intent"] in ("support", "not_interested", "other")


# ---------------------------------------------------------------- API
def test_voice_status(client, auth_headers):
    data = client.get("/api/voice/status", headers=auth_headers).json()
    assert data["bucket_prefix"].endswith("call_recording/Vaishnavi-samp/")
    assert data["model"]
    assert data["layers"][0].startswith("L0")


def test_voice_ingest_and_provision(client, auth_headers):
    r = client.post(
        "/api/voice/ingest",
        headers=auth_headers,
        json={
            "file_name": "sample-call.m4a",
            "transcript": SAMPLE_TRANSCRIPT,
            "language": "mixed",
            "duration_sec": 42,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] > 0
    assert body["lead"]["intent"] == "order"
    assert body["tone"]["urgency"] == "high"
    tid = body["id"]

    full = client.get(f"/api/voice/transcripts/{tid}", headers=auth_headers).json()
    assert full["transcript"] == SAMPLE_TRANSCRIPT
    assert full["layers"]["l1_transcribe"] if "l1_transcribe" in full["layers"] else True
    assert full["lead"]["products"]

    prov = client.post(f"/api/voice/provision/{tid}", headers=auth_headers).json()
    assert prov["created"] is True
    assert prov["stage"] == "evaluation"  # intent=order
    assert prov["recommended_template"]
    # idempotent: second provision reuses the contact
    prov2 = client.post(f"/api/voice/provision/{tid}", headers=auth_headers).json()
    assert prov2["contact_id"] == prov["contact_id"]
    assert prov2["created"] is False

    stories = client.get("/api/journey/stories?limit=5", headers=auth_headers).json()
    assert any(s["contact_id"] == prov["contact_id"] for s in stories)


def test_voice_transcripts_and_stats(client, auth_headers):
    client.post(
        "/api/voice/ingest",
        headers=auth_headers,
        json={"file_name": "a.m4a", "transcript": SAMPLE_TRANSCRIPT},
    )
    lst = client.get("/api/voice/transcripts", headers=auth_headers).json()
    assert len(lst) >= 1 and lst[0]["lead"]["intent"] == "order"
    st = client.get("/api/voice/stats", headers=auth_headers).json()
    assert st["transcripts"] >= 1
    assert "intent_mix" in st and "sentiment_mix" in st


def test_voice_transcript_404(client, auth_headers):
    assert client.get("/api/voice/transcripts/99999", headers=auth_headers).status_code == 404
    assert client.post("/api/voice/provision/99999", headers=auth_headers).status_code == 404


# ---------------------------------------------------------------- Gemma SLM chain
def test_gemma_chain_used_first(monkeypatch):
    import sales_fastapi.voice_analysis as va

    calls = {"n": 0}

    def fake_ollama(base_url, model, prompt, **kw):
        calls["n"] += 1
        if "extract context as JSON" in prompt:
            return {
                "purpose": "rate enquiry",
                "products": ["VCI bags"],
                "quantities": ["500 kg"],
                "rates_quoted": [],
                "objections": [],
                "competitors": [],
                "commitments": [],
                "summary": "wants 500kg VCI",
            }
        if "Analyse the customer" in prompt:
            return {
                "sentiment": "positive",
                "urgency": "high",
                "politeness": "high",
                "interest": "high",
                "noise": "clean",
                "speech_pace": "normal",
                "notes": "gemma",
            }
        return {
            "name": "Patil",
            "company": "ACME",
            "phone": "9822000000",
            "email": "",
            "intent": "order",
            "products": ["VCI bags"],
            "estimated_qty": "500 kg",
            "next_action": "send quote",
            "recommended_template": "WA-ORD-01",
            "confidence": 0.81,
        }

    monkeypatch.setattr(va, "ollama_json", fake_ollama)
    out = va.analyze(
        SAMPLE_TRANSCRIPT,
        {"duration_sec": 40},
        api_key="",
        slm_first=True,
        slm_model="gemma-4-27b-it",
    )
    assert out["mode"] == "gemma"
    assert out["model"] == "gemma-4-27b-it"
    assert out["l4_lead"]["confidence"] == 0.81
    assert calls["n"] == 3


def test_gemma_failure_falls_back_to_heuristic(monkeypatch):
    import sales_fastapi.voice_analysis as va

    monkeypatch.setattr(
        va, "ollama_json", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down"))
    )
    out = va.analyze(SAMPLE_TRANSCRIPT, {"duration_sec": 20}, api_key="", slm_first=True)
    assert out["mode"] == "heuristic"
    assert out["l4_lead"]["phone"] == "9822000000"


def test_voice_providers_endpoint(client, auth_headers):
    data = client.get("/api/voice/providers", headers=auth_headers).json()
    assert data["chain"][0] in ("gemma", "gemini")
    assert data["gemma"]["model"]
    assert "reachable" in data["gemma"] and "configured" in data["gemini"]
    assert data["heuristic"]["ready"] is True


def test_voice_status_includes_slm_block(client, auth_headers):
    data = client.get("/api/voice/status", headers=auth_headers).json()
    assert data["slm"]["gemma_model"]
    assert data["slm"]["preferred"] in ("gemma", "gemini")
