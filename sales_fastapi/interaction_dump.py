"""Interaction dump parsing — WhatsApp chat exports (+ email-shaped records).

Stdlib only so cron scripts and unit tests can use it without the app stack.

A "dump" is one JSON document:
{
  "generated_at": ..., "sources": [...],
  "stats": {chats, messages, attachments, media_by_type, mails, ...},
  "chats": [ {chat, file, participants, message_count, date_range,
              messages: [...], attachments: [{name,size,media_type}]} ],
  "mails": [ ... ]            # email-shaped interactions (IMAP/queue)
}
"""

from __future__ import annotations

import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

# "28/11/2024, 9:41:22 pm - Sender: text"  (12h or 24h, optional seconds)
WA_MSG_RE = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?(?:\s?[ap]\.?m\.?)?)\s*-\s*([^:]{1,80}?):\s*(.*)$",
    re.IGNORECASE,
)
MEDIA_OMITTED = "<Media omitted>"
ATTACHED_RE = re.compile(
    r"([\w\- .()]+\.(?:jpg|jpeg|png|gif|webp|mp4|aac|opus|mp3|pdf|docx?|xlsx?|vcf))\s*\(file attached\)",
    re.I,
)

MEDIA_TYPES = {
    "image": (".jpg", ".jpeg", ".png", ".gif", ".webp"),
    "video": (".mp4", ".mov", ".3gp"),
    "audio": (".aac", ".opus", ".mp3", ".m4a"),
    "document": (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt"),
    "contact_card": (".vcf",),
    "other": (),
}


def classify_media(filename: str) -> str:
    lower = (filename or "").lower()
    for kind, exts in MEDIA_TYPES.items():
        if lower.endswith(exts):
            return kind
    return "other"


def _iso_date(dmy: str) -> str:
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(dmy, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return dmy


def parse_whatsapp_chat(text: str) -> dict:
    """Parse exported WhatsApp chat text into structured messages."""
    messages = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        m = WA_MSG_RE.match(line)
        if not m:
            if messages:  # multi-line message continuation
                messages[-1]["text"] += " " + line
            continue
        d, t, sender, body = m.groups()
        attached = ATTACHED_RE.findall(body)
        messages.append(
            {
                "date": _iso_date(d),
                "time": t.strip(),
                "sender": sender.strip(),
                "text": body.strip(),
                "has_media": MEDIA_OMITTED in body,
                "attachments_inline": attached,
            }
        )
    participants = sorted({m["sender"] for m in messages})
    dates = sorted({m["date"] for m in messages})
    return {
        "message_count": len(messages),
        "participants": participants,
        "date_range": {"first": dates[0] if dates else None, "last": dates[-1] if dates else None},
        "media_omitted_count": sum(1 for m in messages if m["has_media"]),
        "messages": messages,
    }


def read_chat_zip(zip_path: str | Path) -> dict:
    """Read a WhatsApp export zip: parse chat text + list real attachments."""
    zip_path = Path(zip_path)
    chat_txt, attachments = None, []
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            name = info.filename
            if name.lower().endswith(".txt"):
                chat_txt = name
            else:
                attachments.append(
                    {
                        "name": name,
                        "size_bytes": int(info.file_size),
                        "media_type": classify_media(name),
                    }
                )
        parsed = (
            parse_whatsapp_chat(z.read(chat_txt).decode("utf-8", errors="replace"))
            if chat_txt
            else parse_whatsapp_chat("")
        )
    chat_title = re.sub(r"^WhatsApp Chat with\s+", "", zip_path.stem)
    return {
        "chat": chat_title,
        "file": zip_path.name,
        **parsed,
        "attachments": attachments,
    }


def mail_record(
    *, subject="", sender="", to="", date="", body="", attachments=None, source="imap"
) -> dict:
    """Normalised email-shaped interaction (for IMAP fetches / tests)."""
    return {
        "type": "email",
        "subject": subject,
        "from": sender,
        "to": to,
        "date": date,
        "body_preview": (body or "")[:200],
        "attachments": [
            {
                "name": a.get("name", ""),
                "size_bytes": int(a.get("size_bytes", a.get("size", 0)) or 0),
                "media_type": classify_media(a.get("name", "")),
            }
            for a in (attachments or [])
        ],
        "source": source,
    }


def dump_stats(chats: list[dict], mails: list[dict]) -> dict:
    media_by_type: dict[str, int] = {}
    total_att = 0
    for c in chats:
        for a in c.get("attachments", []):
            media_by_type[a["media_type"]] = media_by_type.get(a["media_type"], 0) + 1
            total_att += 1
    return {
        "chats": len(chats),
        "messages": sum(c.get("message_count", 0) for c in chats),
        "participants_total": len({p for c in chats for p in c.get("participants", [])}),
        "attachments": total_att,
        "media_by_type": media_by_type,
        "mails": len(mails),
        "media_omitted_refs": sum(c.get("media_omitted_count", 0) for c in chats),
    }


def build_dump(chats: list[dict], mails: list[dict], sources: list[str]) -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "stats": dump_stats(chats, mails),
        "chats": chats,
        "mails": mails,
    }
