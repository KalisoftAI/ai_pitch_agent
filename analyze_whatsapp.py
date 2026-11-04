"""Analyze 'Kalika Order's' WhatsApp chat: messages, patterns, keywords, samples."""
import io, os, re, json, zipfile, sys
from collections import Counter
import google.auth
from google.cloud import storage

BASE = os.path.dirname(os.path.abspath(__file__))
CHAT_ZIP = "kalika backup/WhatsApp Chat with Kalika Order's .zip"

creds, _ = google.auth.default()
client = storage.Client(credentials=creds)
bucket = client.bucket("kalika_enterprises")
blob = bucket.blob(CHAT_ZIP)
buf = io.BytesIO()
blob.download_to_file(buf)
buf.seek(0)

z = zipfile.ZipFile(buf)
names = z.namelist()
txt_name = next((n for n in names if n.lower().endswith(".txt")), None)
print("zip entries:", len(names), "| chat file:", txt_name)

raw = z.read(txt_name).decode("utf-8", errors="replace")
lines = raw.splitlines()

# WhatsApp format: "DD/MM/YYYY, HH:MM - Sender: message"  (or 12h with am/pm)
msg_re = re.compile(r"^(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?(?:\s?[ap]m)?)\s*-\s*([^:]*?):\s*(.*)$", re.I)

msgs, senders, dates = [], Counter(), Counter()
kw = Counter()
keywords = {
    "order": ["order", "po ", "purchase order"],
    "rate/price": ["rate", "price", "rs.", "rs ", "₹"],
    "dispatch/delivery": ["dispatch", "delivery", "delivered", "challan", "transport"],
    "payment": ["payment", "paid", "udhaar", "credit"],
    "follow-up": ["follow up", "followup", "reminder", "pending", "kal", "tomorrow"],
    "invoice/bill": ["invoice", "bill", "gst"],
    "quantity": ["kg", "box", "boxes", "pcs", "carton", "roll"],
}
samples = {"order": [], "rate/price": [], "dispatch/delivery": [], "payment": [], "follow-up": []}

unmatched = 0
for ln in lines:
    m = msg_re.match(ln)
    if not m:
        if ln.strip():
            unmatched += 1
            if msgs:
                msgs[-1]["text"] += " " + ln.strip()
        continue
    d, t, sender, text = m.groups()
    msgs.append({"date": d, "time": t, "sender": sender.strip(), "text": text.strip()})
    senders[sender.strip()] += 1
    dates[d] += 1
    low = text.lower()
    for k, words in keywords.items():
        if any(w in low for w in words):
            kw[k] += 1
            if k in samples and len(samples[k]) < 8 and 10 < len(text) < 220:
                samples[k].append(f"[{d}] {sender.strip()}: {text.strip()[:180]}")

# date range (assume dd/mm/yyyy)
def dkey(s):
    p = s.split("/")
    return (int(p[2]), int(p[1]), int(p[0])) if len(p) == 3 else (0, 0, 0)

ds = sorted(dates.keys(), key=dkey)
media = sum(1 for m_ in msgs if "<Media omitted>" in m_["text"] or m_["text"].lower().endswith((".jpg", ".pdf", ".aac", ".mp4")))

result = {
    "chat": "Kalika Order's (WhatsApp export)",
    "total_messages": len(msgs),
    "media_omitted_refs": media,
    "date_range": {"first": ds[0] if ds else None, "last": ds[-1] if ds else None},
    "active_days": len(dates),
    "participants": dict(senders.most_common(10)),
    "keyword_patterns": dict(kw),
    "samples": samples,
    "attachments_in_zip": len(names) - 1,
}

out = os.path.join(BASE, "whatsapp_orders_analysis.json")
with open(out, "w", encoding="utf-8") as fh:
    json.dump(result, fh, indent=2, ensure_ascii=False)
print(json.dumps(result, indent=2, ensure_ascii=False)[:3500])
print("\nsaved", out)
