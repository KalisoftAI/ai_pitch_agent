r"""Voice/call-recording analysis: transcription + layered prompts.

Pipeline (layers of prompts, Gemini SLM/flash, human review on outputs):

  L0  AUDIO PROBE     ffprobe/ffmpeg -> duration, sample rate, channels,
                      mean/max volume (dB), silence ratio  [always runs]
  L1  TRANSCRIBE      Gemini audio -> verbatim transcript with speaker turns
  L2  CONTEXT         who/what/why, products, quantities, rates, objections
  L3  TONE            sentiment, urgency, politeness, noise, speech pace
  L4  LEAD EXTRACT    structured lead JSON + Kalika product mapping + next actions

Provider: Gemini REST (GEMINI_API_KEY). Without a key the job still stores L0
audio characteristics and marks the row `pending_ai`; `ingest` accepts an
external ASR transcript so layers L2-L4 run deterministically.
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone

MODEL_DEFAULT = "gemini-2.5-flash"
SUPPORTED_SUFFIXES = (".wav", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".flac")
MIME = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
    ".flac": "audio/flac",
}

# ---------------------------------------------------------------- layer prompts
PROMPTS = {
    "l1_transcribe": (
        "Transcribe this phone call between a Kalika Enterprises salesperson and a customer. "
        'Return strict JSON: {"language":"hi|en|mr|mixed","transcript":"...",'
        '"turns":[{"speaker":"agent|customer","text":"...","approx_sec":0}]}. '
        "Keep product names, numbers, quantities and rates exactly as spoken. Do not invent content."
    ),
    "l2_context": (
        "You are a Kalika Enterprises (industrial packaging manufacturer) sales analyst. "
        'From this call transcript, extract context as JSON: {"purpose":str,"products":[str],'
        '"quantities":[str],"rates_quoted":[str],"objections":[str],"competitors":[str],'
        '"commitments":[str],"summary":str}. Transcript: {transcript}'
    ),
    "l3_tone": (
        "Analyse the customer's tone in this sales call. Use the transcript plus acoustic facts. "
        'Return JSON: {"sentiment":"positive|neutral|negative","urgency":"low|medium|high",'
        '"politeness":"low|medium|high","interest":"low|medium|high","noise":"clean|some|noisy",'
        '"speech_pace":"slow|normal|fast","notes":str}. '
        "Acoustics: {acoustics}. Transcript: {transcript}"
    ),
    "l4_lead": (
        "Extract a CRM lead from this Kalika Enterprises call. Map requirements to Kalika products "
        "(stretch film, shrink film, BOPP tape, masking tape, VCI bags, tarpaulin, HDPE/poly bags, shade net, "
        'gloves, sleeves, straps). Return JSON: {"name":str,"company":str,"phone":str,"email":str,'
        '"intent":"order|rate|sample|support|not_interested|other","products":[str],'
        '"estimated_qty":str,"next_action":str,"recommended_template":str,"confidence":0.0}. '
        "Transcript: {transcript}. Context: {context}"
    ),
}

PRODUCT_KEYWORDS = {
    "stretch film": ["stretch", "stretch film", "wrap film", "pallet wrap"],
    "shrink film": ["shrink"],
    "BOPP tape": ["bopp", "tape", "transparent tape", "brown tape"],
    "masking tape": ["masking"],
    "VCI bags": ["vci", "vci bag"],
    "tarpaulin": ["tarpaulin", "tarpauli", "tadpatri"],
    "HDPE/poly bags": ["hdpe", "poly bag", "polybag", "poly bag"],
    "shade net": ["shade net", "shadenet"],
    "hand gloves": ["glove", "gloves", "hath"],
    "hand sleeves": ["sleeve"],
    "straps & buckles": ["strap", "buckle"],
    "poly box": ["poly box", "plastic box"],
}

NEGATIVE_WORDS = [
    "not interested",
    "nahi",
    "no need",
    "problem",
    "late",
    "delay",
    "complaint",
    "damaged",
    "expensive",
    "costly",
    "mehnga",
    "galat",
    "issue",
]
POSITIVE_WORDS = [
    "yes",
    "haan",
    "ok",
    "order",
    "confirm",
    "good",
    "thank",
    "dhanyavad",
    "send",
    "chahiye",
    "required",
    "urgent",
]
URGENT_WORDS = ["urgent", "today", "immediately", "turant", "kal tak", "asap", "jaldi"]


# ---------------------------------------------------------------- L0 probe
def _run(cmd: list[str], timeout: int = 60) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (out.stdout or "") + (out.stderr or "")
    except Exception:
        return ""


def probe_audio(data: bytes, suffix: str = ".wav") -> dict:
    """Acoustic facts via ffprobe/ffmpeg. Never raises."""
    stats = {
        "duration_sec": 0.0,
        "sample_rate": 0,
        "channels": 0,
        "mean_volume_db": 0.0,
        "max_volume_db": 0.0,
        "silence_ratio": 0.0,
        "probe": "unavailable",
    }
    fd, path = tempfile.mkstemp(suffix=suffix if suffix in MIME else ".wav")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        info = _run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                path,
            ]
        )
        try:
            parsed = json.loads(info)
            fmt = parsed.get("format", {})
            stream = next(
                (s for s in parsed.get("streams", []) if s.get("codec_type") == "audio"), {}
            )
            stats["duration_sec"] = round(
                float(fmt.get("duration") or stream.get("duration") or 0), 2
            )
            stats["sample_rate"] = int(stream.get("sample_rate") or 0)
            stats["channels"] = int(stream.get("channels") or 0)
            stats["probe"] = "ffprobe"
        except Exception:
            pass
        vol = _run(
            [
                "ffmpeg",
                "-hide_banner",
                "-nostats",
                "-i",
                path,
                "-af",
                "volumedetect",
                "-f",
                "null",
                "-",
            ]
        )
        m_mean = re.search(r"mean_volume:\s*(-?[\d.]+) dB", vol)
        m_max = re.search(r"max_volume:\s*(-?[\d.]+) dB", vol)
        if m_mean:
            stats["mean_volume_db"] = float(m_mean.group(1))
        if m_max:
            stats["max_volume_db"] = float(m_max.group(1))
        sil = _run(
            [
                "ffmpeg",
                "-hide_banner",
                "-nostats",
                "-i",
                path,
                "-af",
                "silencedetect=noise=-35dB:d=0.5",
                "-f",
                "null",
                "-",
            ]
        )
        sil_durations = [float(x) for x in re.findall(r"silence_duration:\s*([\d.]+)", sil)]
        if stats["duration_sec"]:
            stats["silence_ratio"] = round(min(1.0, sum(sil_durations) / stats["duration_sec"]), 3)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return stats


# ---------------------------------------------------------------- Gemini REST
class MissingKey(RuntimeError):
    pass


# ---------------------------------------------------------------- Gemma SLM (Ollama)
def ollama_available(base_url: str, timeout: float = 1.5) -> bool:
    try:
        import requests

        requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout)
        return True
    except Exception:
        return False


def ollama_models(base_url: str, timeout: float = 1.5) -> list[str]:
    try:
        import requests

        data = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout).json()
        return [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        return []


def ollama_json(base_url: str, model: str, prompt: str, *, timeout: int = 180) -> dict:
    """Run a JSON-mode prompt on a local Gemma SLM via Ollama."""
    import requests

    resp = requests.post(
        f"{base_url.rstrip('/')}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2, "num_predict": 1024},
        },
        timeout=timeout,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"ollama {resp.status_code}: {resp.text[:200]}")
    raw = (resp.json().get("response") or "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            return json.loads(m.group(0))
        raise RuntimeError("gemma returned non-JSON output")


def gemini_json(
    api_key: str, model: str, parts: list[dict], *, temperature: float = 0.2, max_tokens: int = 2048
) -> dict:
    if not api_key:
        raise MissingKey("GEMINI_API_KEY is not configured")
    import requests

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }
    resp = requests.post(url, params={"key": api_key}, json=payload, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    text = "".join(
        p.get("text", "")
        for c in data.get("candidates", [])
        for p in c.get("content", {}).get("parts", [])
    )
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text or "")
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        raise RuntimeError("Gemini returned non-JSON output")


def transcribe_with_gemini(
    data: bytes, suffix: str, api_key: str, model: str = MODEL_DEFAULT
) -> dict:
    mime = MIME.get(suffix.lower(), "audio/wav")
    parts = [
        {"text": PROMPTS["l1_transcribe"]},
        {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode()}},
    ]
    return gemini_json(api_key, model, parts, temperature=0.1, max_tokens=4096)


# ---------------------------------------------------------------- deterministic layers
def _acoustics_text(a: dict) -> str:
    return (
        f"duration={a.get('duration_sec', 0)}s, mean_volume={a.get('mean_volume_db', 0)}dB, "
        f"max_volume={a.get('max_volume_db', 0)}dB, silence_ratio={a.get('silence_ratio', 0)}, "
        f"channels={a.get('channels', 0)}, sample_rate={a.get('sample_rate', 0)}"
    )


def heuristic_layers(transcript: str, audio: dict) -> dict:
    """Deterministic fallback (no AI key): keyword + acoustic heuristics."""
    low = (transcript or "").lower()
    products = [name for name, keys in PRODUCT_KEYWORDS.items() if any(k in low for k in keys)]
    phones = re.findall(r"(?:\+?91[\s-]?)?[6-9]\d{9}|\b0\d{2,4}[\s-]?\d{6,8}\b", transcript or "")
    qty = re.findall(
        r"\b\d+(?:\.\d+)?\s?(?:kg|kgs|box|boxes|roll|rolls|piece|pieces|pcs|ton|tons)\b", low
    )
    rates = re.findall(
        r"(?:\d+(?:\.\d+)?\s?(?:rs\.?|rupees?|/-))"
        r"|(?:(?:rs\.?|₹|rupees?)\s?\d+(?:\.\d+)?)"
        r"(?:\s?(?:per|/)\s?(?:kg|pc|piece|roll))?",
        low,
    )
    neg = sum(1 for w in NEGATIVE_WORDS if w in low)
    pos = sum(1 for w in POSITIVE_WORDS if w in low)
    urgent = any(w in low for w in URGENT_WORDS)
    sentiment = "negative" if neg > pos else ("positive" if pos > 0 else "neutral")
    silence = float(audio.get("silence_ratio") or 0)
    noise = "noisy" if silence < 0.12 else ("some" if silence < 0.3 else "clean")
    words = len(re.findall(r"\w+", low))
    pace = (
        "fast"
        if audio.get("duration_sec") and words / max(1.0, audio["duration_sec"]) > 3
        else "normal"
    )
    context = {
        "products": products or ["unspecified"],
        "quantities": qty[:6],
        "rates_quoted": rates[:6],
        "objections": [w for w in NEGATIVE_WORDS if w in low][:4],
        "competitors": [],
        "commitments": [],
        "summary": (transcript or "")[:280],
        "purpose": "sales call",
    }
    tone = {
        "sentiment": sentiment,
        "urgency": "high" if urgent else "medium" if sentiment == "positive" else "low",
        "politeness": "high"
        if any(w in low for w in ["ji", "please", "namaste", "thank"])
        else "medium",
        "interest": "high" if pos and not neg else "low" if neg > pos else "medium",
        "noise": noise,
        "speech_pace": pace,
        "notes": "heuristic (no AI key)",
    }
    intent = (
        "order"
        if ("order" in low or qty)
        else "rate"
        if rates or "rate" in low
        else "sample"
        if "sample" in low
        else "support"
        if any(w in low for w in ["complaint", "issue", "damaged", "late"])
        else "not_interested"
        if neg > pos and not pos
        else "other"
    )
    lead = {
        "name": "",
        "company": "",
        "phone": phones[0] if phones else "",
        "email": "",
        "intent": intent,
        "products": products,
        "estimated_qty": qty[0] if qty else "",
        "next_action": ("Send quotation for " + ", ".join(products))
        if products
        else "Ask requirement details",
        "recommended_template": {
            "order": "WA-ORD-01",
            "rate": "WA-RT-01",
            "sample": "WA-EXP-01",
            "support": "WA-FBK-02",
            "not_interested": "WA-FU-03",
        }.get(intent, "WA-FU-01"),
        "confidence": 0.55,
    }
    return {"l2_context": context, "l3_tone": tone, "l4_lead": lead, "mode": "heuristic"}


def ai_layers(transcript: str, audio: dict, api_key: str, model: str = MODEL_DEFAULT) -> dict:
    acoustics = _acoustics_text(audio)
    ctx = gemini_json(
        api_key, model, [{"text": PROMPTS["l2_context"].replace("{transcript}", transcript or "")}]
    )
    tone = gemini_json(
        api_key,
        model,
        [
            {
                "text": PROMPTS["l3_tone"]
                .replace("{transcript}", transcript or "")
                .replace("{acoustics}", acoustics)
            }
        ],
    )
    lead = gemini_json(
        api_key,
        model,
        [
            {
                "text": PROMPTS["l4_lead"]
                .replace("{transcript}", transcript or "")
                .replace("{context}", json.dumps(ctx, ensure_ascii=False))
            }
        ],
    )
    return {"l2_context": ctx, "l3_tone": tone, "l4_lead": lead, "mode": "gemini", "model": model}


def slm_layers(transcript: str, audio: dict, base_url: str, model: str) -> dict:
    """Layered prompts on the local Gemma SLM via Ollama (data stays on-device)."""
    acoustics = _acoustics_text(audio)
    ctx = ollama_json(
        base_url, model, PROMPTS["l2_context"].replace("{transcript}", transcript or "")
    )
    tone = ollama_json(
        base_url,
        model,
        PROMPTS["l3_tone"]
        .replace("{transcript}", transcript or "")
        .replace("{acoustics}", acoustics),
    )
    lead = ollama_json(
        base_url,
        model,
        PROMPTS["l4_lead"]
        .replace("{transcript}", transcript or "")
        .replace("{context}", json.dumps(ctx, ensure_ascii=False)),
    )
    return {"l2_context": ctx, "l3_tone": tone, "l4_lead": lead, "mode": "gemma", "model": model}


def analyze(
    transcript: str,
    audio: dict,
    api_key: str = "",
    model: str = MODEL_DEFAULT,
    *,
    slm_first: bool = True,
    slm_base_url: str = "",
    slm_model: str = "",
) -> dict:
    """Provider chain: Gemma SLM (Ollama) -> Gemini -> deterministic heuristics.

    Gemma is preferred so customer audio context can be processed on-device
    (SLM/free). Each step degrades gracefully; the `mode` field records which
    provider actually produced the layers.
    """
    slm_base_url = slm_base_url or "http://localhost:11434"
    slm_model = slm_model or "gemma-4-27b-it"
    chain = (
        [
            ("gemma", lambda: slm_layers(transcript, audio, slm_base_url, slm_model)),
            ("gemini", lambda: ai_layers(transcript, audio, api_key, model)),
        ]
        if slm_first
        else [
            ("gemini", lambda: ai_layers(transcript, audio, api_key, model)),
            ("gemma", lambda: slm_layers(transcript, audio, slm_base_url, slm_model)),
        ]
    )
    for name, runner in chain:
        if name == "gemini" and not api_key:
            continue
        try:
            return runner()
        except Exception:
            continue
    return heuristic_layers(transcript, audio)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
