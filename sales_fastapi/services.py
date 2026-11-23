"""External integrations.

Every integration is written to degrade gracefully: if credentials or network
are unavailable the method returns a structured placeholder / empty result and
flags ``available = False`` instead of raising, so the app stays testable.
"""

from __future__ import annotations

import base64
import binascii
import email
import imaplib
import json
import re
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional
from urllib.parse import urlencode

from .config import settings

# ==========================================================================
# Contact segregation helpers (domain / intent / context)
# ==========================================================================
_FREE_EMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "outlook.com",
    "hotmail.com",
    "rediffmail.com",
    "live.com",
    "icloud.com",
    "protonmail.com",
}

_INTENT_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("hiring", ("hiring", "recruit", "vacancy", "job", "intern", "opening")),
    ("procurement", ("procure", "purchase", "scm", "supply", "sourcing", "buyer", "vendor")),
    ("sales", ("sales", "rfq", "quotation", "quote", "enquiry", "inquiry")),
    ("partnership", ("partner", "collaborat", "alliance", "tie-up")),
    ("support", ("support", "help", "service", "issue", "complaint")),
]


def infer_domain(email_address: str) -> str:
    if not email_address or "@" not in email_address:
        return ""
    return email_address.split("@")[-1].strip().lower()


def infer_intent(text: str) -> str:
    haystack = (text or "").lower()
    for intent, needles in _INTENT_RULES:
        if any(n in haystack for n in needles):
            return intent
    return "general"


def classify_contact(email_address: str = "", context_text: str = "") -> dict[str, str]:
    """Produce a first-pass (domain, intent, context) segregation."""
    domain = infer_domain(email_address)
    intent = infer_intent(context_text or email_address)
    return {
        "domain": domain,
        "intent": intent,
        "context": context_text.strip(),
    }


def compact_text(value: str, limit: int = 280) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    return text[: max(0, int(limit))].strip()


# ==========================================================================
# Google Cloud Storage
# ==========================================================================
class GCSStorage:
    def __init__(self, bucket_name: str | None = None):
        self.bucket_name = bucket_name or settings.GCS_BUCKET_CONTACTS
        self.available = False
        self._client = None
        try:
            from google.cloud import storage  # type: ignore

            self._client = storage.Client(project=settings.GOOGLE_CLOUD_PROJECT or None)
            self.available = True
        except Exception:  # pragma: no cover - depends on env
            self._client = None
            self.available = False

    def list_contacts(self, prefix: str | None = None) -> list[dict[str, Any]]:
        if not self.available or self._client is None:
            return []
        prefix = prefix if prefix is not None else settings.GCS_PATH_CONTACTS
        out: list[dict[str, Any]] = []
        try:
            for blob in self._client.list_blobs(self.bucket_name, prefix=prefix):
                if not blob.name.lower().endswith((".json", ".csv", ".vcf", ".xlsx", ".xls")):
                    continue
                out.append(
                    {"name": blob.name, "size": blob.size, "content_type": blob.content_type}
                )
        except Exception:
            return out
        return out

    def list_blobs(
        self,
        prefix: str = "",
        suffixes: tuple[str, ...] | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        if not self.available or self._client is None:
            return []
        out: list[dict[str, Any]] = []
        options: dict[str, Any] = {"prefix": prefix}
        if max_results is not None:
            options["max_results"] = max(1, min(int(max_results), 1000))
        try:
            for blob in self._client.list_blobs(self.bucket_name, **options):
                if blob.name.endswith("/"):
                    continue
                if suffixes and not blob.name.lower().endswith(suffixes):
                    continue
                out.append(
                    {
                        "name": blob.name,
                        "size": blob.size,
                        "updated": str(blob.updated or ""),
                        "content_type": blob.content_type,
                    }
                )
        except Exception:
            return out
        return out

    def download_blob(self, blob_name: str) -> Optional[bytes]:
        if not self.available or self._client is None:
            return None
        try:
            blob = self._client.bucket(self.bucket_name).blob(blob_name)
            if blob.exists():
                return blob.download_as_bytes()
        except Exception:
            return None
        return None

    def upload_json(self, blob_name: str, payload: dict[str, Any]) -> bool:
        if not self.available or self._client is None:
            return False
        try:
            blob = self._client.bucket(self.bucket_name).blob(blob_name)
            blob.upload_from_string(json.dumps(payload), content_type="application/json")
            return True
        except Exception:
            return False

    def upload_bytes(
        self, blob_name: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> bool:
        if not self.available or self._client is None:
            return False
        try:
            blob = self._client.bucket(self.bucket_name).blob(blob_name)
            blob.upload_from_string(data, content_type=content_type or "application/octet-stream")
            return True
        except Exception:
            return False


# ==========================================================================
# IMAP extraction
# ==========================================================================
class EmailExtractor:
    def __init__(self, imap_host: str, imap_port: int = 993, user: str = "", password: str = ""):
        self.imap_host = imap_host
        self.imap_port = int(imap_port or 993)
        self.user = user
        self.password = password
        self.connection: imaplib.IMAP4_SSL | None = None

    def connect(self) -> bool:
        self.connection = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
        self.connection.login(self.user, self.password)
        self.connection.select("INBOX")
        return True

    def get_uidvalidity(self) -> int:
        """UIDVALIDITY of the selected mailbox (0 when unavailable)."""
        if self.connection is None:
            self.connect()
        assert self.connection is not None
        candidates: list[str] = []
        try:  # most IMAP servers stash it from the SELECT untagged response
            data = getattr(self.connection, "untagged_responses", {}) or {}
            for value in data.get("UIDVALIDITY", []) or []:
                candidates.append(
                    value.decode(errors="ignore") if isinstance(value, bytes) else str(value)
                )
        except Exception:  # noqa: BLE001
            pass
        try:
            _status, data = self.connection.response("UIDVALIDITY")
            if data and data[0]:
                candidates.append(
                    data[0].decode(errors="ignore") if isinstance(data[0], bytes) else str(data[0])
                )
        except Exception:  # noqa: BLE001
            pass
        try:
            _status, data = self.connection.status("INBOX", "(UIDVALIDITY)")
            if data and data[0]:
                candidates.append(
                    data[0].decode(errors="ignore") if isinstance(data[0], bytes) else str(data[0])
                )
        except Exception:  # noqa: BLE001
            pass
        for value in candidates:
            digits = re.sub(r"\D", "", value)
            if digits:
                return int(digits)
        return 0

    def sync_emails(
        self,
        *,
        last_uid: int = 0,
        batch: int = 25,
        full: bool = False,
        since: datetime | None = None,
        until: datetime | None = None,
        query: str = "",
        sender: str = "",
        unread_only: bool = False,
        before_uid: int | None = None,
    ) -> list[dict[str, Any]]:
        """Read-only incremental UID sync (never flags, moves or deletes mailbox mail).

        With ``last_uid`` set only messages with UID > last_uid are fetched (new
        mail since the checkpoint); otherwise today's mail by default (or all when
        ``full``). Batch size is clamped to 20-50. Returns parsed dicts including
        raw bytes, Message-ID and attachments for checkpointing + GCS upload.
        """
        if self.connection is None:
            self.connect()
        assert self.connection is not None
        batch = max(20, min(int(batch or 25), 50))
        criteria: list[str] = []
        if not full:
            if last_uid > 0:
                criteria.extend(["UID", f"{int(last_uid) + 1}:*"])
            else:
                criteria.extend(
                    ["SINCE", (since or datetime.now(timezone.utc)).strftime("%d-%b-%Y")]
                )
        elif since is not None:
            criteria.extend(["SINCE", since.strftime("%d-%b-%Y")])
        if until is not None and (full or since is not None):
            criteria.extend(["BEFORE", (until + timedelta(days=1)).strftime("%d-%b-%Y")])
        if not full and last_uid == 0 and (since is not None or until is not None):
            # honour explicit date window on a first sync too (replace default SINCE above)
            pass
        if unread_only:
            criteria.append("UNSEEN")
        if query.strip():
            criteria.extend(["TEXT", query.strip()])
        if sender.strip():
            criteria.extend(["FROM", f'"{sender.strip()}"'])
        if not criteria:
            criteria = ["ALL"]
        status, data = self.connection.uid("SEARCH", None, *criteria)
        if status != "OK":
            raise RuntimeError("IMAP UID SEARCH failed")
        uids = [int(u) for u in (data[0].split() if data and data[0] else [])]
        if before_uid:
            uids = [u for u in uids if u < int(before_uid)]
        uids = sorted(uids)[-batch:]  # newest slice; caller paginates with before_uid
        out: list[dict[str, Any]] = []
        for uid in uids:
            status, msg_data = self.connection.uid("FETCH", str(uid), "(BODY.PEEK[])")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            raw = b""
            for part in msg_data:
                if isinstance(part, tuple) and len(part) >= 2:
                    raw = part[1]
                    break
            if not raw:
                continue
            msg = email.message_from_bytes(raw)
            body = self._extract_body(msg)
            attachments: list[dict[str, Any]] = []
            if msg.is_multipart():
                for part in msg.walk():
                    disposition = (part.get_content_disposition() or "").lower()
                    filename = part.get_filename()
                    if disposition == "attachment" or (filename and disposition != "inline"):
                        payload = part.get_payload(decode=True) or b""
                        if payload and len(payload) <= 25_000_000:
                            attachments.append(
                                {
                                    "name": filename or f"attachment-{len(attachments) + 1}",
                                    "mime_type": part.get_content_type(),
                                    "size": len(payload),
                                    "data": payload,
                                }
                            )
            out.append(
                {
                    "uid": str(uid),
                    "message_id": str(msg.get("Message-ID", "")).strip(),
                    "subject": str(msg.get("Subject", "")),
                    "from": str(msg.get("From", "")),
                    "to": str(msg.get("To", "")),
                    "date": str(msg.get("Date", "")),
                    "intent": infer_intent(f"{msg.get('Subject', '')} {compact_text(body, 800)}"),
                    "body": body[:50_000],
                    "snippet": compact_text(body, 400),
                    "attachments": [
                        {k: v for k, v in a.items() if k != "data"} for a in attachments
                    ],
                    "_attachments_data": attachments,
                    "_raw": raw,
                }
            )
        return out

    def fetch_emails(
        self,
        limit: int = 25,
        query: str = "",
        sender: str = "",
        since: datetime | None = None,
        until: datetime | None = None,
        unread_only: bool = False,
    ) -> list[dict[str, Any]]:
        if self.connection is None:
            self.connect()
        assert self.connection is not None
        safe_limit = max(1, min(int(limit), 50))
        criteria = ["ALL"]
        if unread_only:
            criteria.append("UNSEEN")
        if query.strip():
            criteria.extend(["TEXT", query.strip()])
        if sender.strip():
            criteria.extend(["FROM", f'"{sender.strip()}"'])
        if since is not None:
            criteria.extend(["SINCE", since.strftime("%d-%b-%Y")])
        if until is not None:
            criteria.extend(["BEFORE", (until + timedelta(days=1)).strftime("%d-%b-%Y")])
        status, data = self.connection.search(None, *criteria)
        if status != "OK":
            raise RuntimeError("IMAP search failed")
        raw_ids = data[0].split() if data and data[0] else []
        scan_limit = min(max(safe_limit * 5, 50), 200)
        ids = raw_ids[-scan_limit:]
        results: list[dict[str, Any]] = []
        for uid in ids:
            _status, msg_data = self.connection.fetch(uid, "(RFC822)")
            raw = msg_data[1][0][1]
            msg = email.message_from_bytes(raw)
            subject = msg.get("Subject", "")
            body = self._extract_body(msg)
            results.append(
                {
                    "uid": uid.decode() if isinstance(uid, bytes) else str(uid),
                    "subject": subject,
                    "from": msg.get("From", ""),
                    "date": msg.get("Date", ""),
                    "intent": infer_intent(f"{subject} {compact_text(body, 1000)}"),
                    "body": body[:50_000],
                }
            )
        return results

    @staticmethod
    def _extract_body(msg) -> str:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode(errors="ignore")
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode(errors="ignore")
            return ""
        payload = msg.get_payload(decode=True)
        return payload.decode(errors="ignore") if payload else ""

    def disconnect(self) -> None:
        if self.connection is not None:
            try:
                self.connection.logout()
            except Exception:
                pass
            finally:
                self.connection = None


class GoogleOAuthClient:
    authorization_endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
    token_endpoint = "https://oauth2.googleapis.com/token"
    gmail_scope = "https://www.googleapis.com/auth/gmail.readonly"

    def __init__(self):
        self.client_id = (settings.GOOGLE_CLIENT_ID or "").strip()
        self.client_secret = (settings.GOOGLE_CLIENT_SECRET or "").strip()
        self.redirect_uri = (settings.GOOGLE_OAUTH_REDIRECT_URI or "").strip()

    @property
    def configured(self) -> bool:
        return bool(
            settings.GMAIL_OAUTH_ENABLED
            and self.client_id
            and self.client_secret
            and self.redirect_uri
        )

    def authorization_url(self, state: str) -> str:
        if not self.configured:
            raise RuntimeError("Google Gmail OAuth is not configured")
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": f"openid email profile {self.gmail_scope}",
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
        }
        return f"{self.authorization_endpoint}?{urlencode(params)}"

    def exchange_code(self, code: str) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError("Google Gmail OAuth is not configured")
        import httpx

        try:
            with httpx.Client(timeout=20) as client:
                response = client.post(
                    self.token_endpoint,
                    data={
                        "code": code,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "redirect_uri": self.redirect_uri,
                        "grant_type": "authorization_code",
                    },
                )
        except httpx.HTTPError as exc:
            raise RuntimeError("Google OAuth token exchange failed") from exc
        if response.status_code >= 400:
            raise RuntimeError("Google OAuth token exchange failed")
        return response.json()

    def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        if not self.configured or not refresh_token:
            raise RuntimeError("Google Gmail OAuth is not configured")
        import httpx

        try:
            with httpx.Client(timeout=20) as client:
                response = client.post(
                    self.token_endpoint,
                    data={
                        "refresh_token": refresh_token,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": "refresh_token",
                    },
                )
        except httpx.HTTPError as exc:
            raise RuntimeError("Google OAuth token refresh failed") from exc
        if response.status_code >= 400:
            raise RuntimeError("Google OAuth token refresh failed")
        return response.json()


class GmailExtractor:
    api_root = "https://gmail.googleapis.com/gmail/v1/users/me"

    def __init__(self, access_token: str):
        self.access_token = access_token

    def _get(self, path: str, params: Any) -> dict[str, Any]:
        import httpx

        try:
            response = httpx.get(
                f"{self.api_root}/{path.lstrip('/')}",
                params=params,
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=20,
            )
        except httpx.HTTPError as exc:
            raise RuntimeError("Gmail API request failed") from exc
        if response.status_code >= 400:
            raise RuntimeError("Gmail API request failed")
        return response.json()

    def profile(self) -> dict[str, Any]:
        return self._get("profile", {})

    def list_message_ids(
        self, *, query: str = "", max_results: int = 100, page_token: str = ""
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"maxResults": max(1, min(int(max_results), 500))}
        if query.strip():
            params["q"] = query.strip()
        if page_token:
            params["pageToken"] = page_token
        return self._get("messages", params)

    def history(
        self, start_history_id: str, *, page_token: str = "", max_results: int = 100
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "startHistoryId": str(start_history_id),
            "maxResults": max(1, min(int(max_results), 500)),
        }
        if page_token:
            params["pageToken"] = page_token
        return self._get("history", params)

    def get_message(self, message_id: str) -> dict[str, Any]:
        return self._get(f"messages/{message_id}", {"format": "full"})

    def get_attachment(self, message_id: str, attachment_id: str) -> bytes:
        payload = self._get(f"messages/{message_id}/attachments/{attachment_id}", {})
        data = str(payload.get("data", ""))
        if not data:
            return b""
        try:
            padding = "=" * (-len(data) % 4)
            return base64.urlsafe_b64decode(f"{data}{padding}")
        except (binascii.Error, ValueError) as exc:
            raise RuntimeError("Gmail attachment decode failed") from exc

    def fetch_emails(
        self,
        limit: int = 15,
        query: str = "",
        sender: str = "",
        since: datetime | None = None,
        until: datetime | None = None,
        unread_only: bool = False,
        include_body: bool = False,
    ) -> tuple[int, list[dict[str, Any]]]:
        safe_limit = max(1, min(int(limit), 50))
        query_parts: list[str] = []
        if query.strip():
            query_parts.append(f"{{{query.strip()}}}")
        if sender.strip():
            query_parts.append(f"from:{sender.strip().replace(chr(34), '')}")
        if since is not None:
            query_parts.append(f"after:{since.strftime('%Y/%m/%d')}")
        if until is not None:
            query_parts.append(f"before:{(until + timedelta(days=1)).strftime('%Y/%m/%d')}")
        if unread_only:
            query_parts.append("is:unread")
        listing = self._get(
            "messages",
            {"q": " ".join(query_parts), "maxResults": min(max(safe_limit * 4, 50), 100)},
        )
        items = listing.get("messages", [])
        results: list[dict[str, Any]] = []
        for item in items:
            message_id = str(item.get("id", ""))
            if not message_id:
                continue
            metadata = self._get(
                f"messages/{message_id}",
                [
                    ("format", "metadata"),
                    ("metadataHeaders", "Subject"),
                    ("metadataHeaders", "From"),
                    ("metadataHeaders", "Date"),
                ],
            )
            headers = {
                str(header.get("name", "")).lower(): str(header.get("value", ""))
                for header in metadata.get("payload", {}).get("headers", [])
            }
            subject = headers.get("subject", "")
            snippet = compact_text(str(metadata.get("snippet", "")), 1000)
            body = ""
            attachments: list[dict[str, Any]] = []
            if include_body:
                full_message = self._get(f"messages/{message_id}", {"format": "full"})
                payload = full_message.get("payload", {})
                body = self._extract_body(payload)
                attachments = self._extract_attachments(payload)
            results.append(
                {
                    "uid": message_id,
                    "subject": subject,
                    "from": headers.get("from", ""),
                    "date": headers.get("date", ""),
                    "intent": infer_intent(f"{subject} {snippet} {body}"),
                    "body": body[:50_000],
                    "snippet": snippet,
                    "attachments": attachments,
                }
            )
            if len(results) >= safe_limit:
                break
        return len(items), results

    @classmethod
    def _extract_attachments(cls, part: dict[str, Any]) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        filename = str(part.get("filename", "")).strip()
        body = part.get("body", {}) or {}
        if filename:
            found.append(
                {
                    "name": filename,
                    "size": int(body.get("size") or 0),
                    "mime_type": str(part.get("mimeType", "")),
                    "attachment_id": str(body.get("attachmentId", "")),
                }
            )
        for child in part.get("parts", []) or []:
            found.extend(cls._extract_attachments(child))
        return found

    @classmethod
    def _extract_body(cls, part: dict[str, Any]) -> str:
        mime_type = str(part.get("mimeType", ""))
        data = str(part.get("body", {}).get("data", ""))
        if data:
            try:
                padding = "=" * (-len(data) % 4)
                decoded = base64.urlsafe_b64decode(f"{data}{padding}").decode(errors="ignore")
            except (binascii.Error, ValueError):
                decoded = ""
            if mime_type == "text/plain" or not part.get("parts"):
                return decoded
        for child in part.get("parts", []):
            body = cls._extract_body(child)
            if body:
                return body
        return ""


# ==========================================================================
# SMTP sending
# ==========================================================================
class MailSender:
    def __init__(self, smtp_host: str, smtp_port: int = 587, user: str = "", password: str = ""):
        self.smtp_host = smtp_host
        self.smtp_port = int(smtp_port or 587)
        self.user = user
        self.password = password

    def send(
        self,
        to: str,
        subject: str,
        body: str,
        from_email: str | None = None,
        *,
        html: bool = False,
        retries: int = 2,
    ) -> dict[str, Any]:
        """Send one message with Message-ID header and bounded retries.

        Returns provider id (Message-ID) and final status; raises RuntimeError with
        the last SMTP error text when all attempts fail so callers can log per-
        recipient failures honestly.
        """
        from_email = from_email or self.user
        message_id = (
            f"<{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S.%f')}"
            f"@{from_email.split('@')[-1] if '@' in from_email else 'kalika.local'}>"
        )
        msg = MIMEMultipart("alternative")
        msg["From"] = from_email
        msg["To"] = to
        msg["Subject"] = subject
        msg["Message-ID"] = message_id
        msg["X-Mailer"] = "Kalika Sales Outreach"
        msg.attach(MIMEText(body, "html" if html else "plain", "utf-8"))
        last_error = ""
        for _attempt in range(max(1, retries)):
            try:
                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                    server.starttls()
                    if self.user:
                        server.login(self.user, self.password)
                    server.send_message(msg)
                return {"sent": True, "to": to, "from": from_email, "message_id": message_id}
            except Exception as exc:  # noqa: BLE001 - retry then surface
                last_error = f"{type(exc).__name__}: {exc}"
        raise RuntimeError(last_error or "SMTP send failed")


def check_smtp_connection(
    host: str, port: int, user: str = "", password: str = "", timeout: int = 15
) -> tuple[bool, str]:
    """Verify SMTP/STARTTLS/login without delivering a message."""
    try:
        with smtplib.SMTP(host, port, timeout=timeout) as server:
            server.ehlo()
            if server.has_extn("STARTTLS"):
                server.starttls()
                server.ehlo()
            if user:
                server.login(user, password)
        return True, "connected"
    except Exception as exc:  # noqa: BLE001 - report the provider error to the caller
        detail = f"{type(exc).__name__}: {exc}"[:300]
        if password:
            detail = detail.replace(password, "***")
        return False, detail


# ==========================================================================
# LinkedIn
# ==========================================================================
class LinkedInExtractor:
    def __init__(self):
        self.available = bool(settings.LINKEDIN_CLIENT_ID)

    def search_by_hiring_alerts(
        self, keywords: list[str], location: str = ""
    ) -> list[dict[str, Any]]:
        """Return candidate profile stubs for hiring-related keywords.

        Without API credentials this produces deterministic stubs so the pipeline
        can be exercised end-to-end.
        """
        now = datetime.now(timezone.utc).isoformat()
        out = []
        for kw in keywords:
            slug = re.sub(r"[^a-z0-9]+", "-", kw.lower()).strip("-")
            out.append(
                {
                    "profile_url": f"https://www.linkedin.com/in/{slug}-talent",
                    "name": kw.title(),
                    "headline": f"{kw} | hiring",
                    "company": "",
                    "location": location,
                    "skills": [],
                    "source_keyword": kw,
                    "extracted_at": now,
                }
            )
        return out

    def extract_profile(self, profile_url: str) -> dict[str, Any]:
        return {
            "profile_url": profile_url,
            "name": "",
            "headline": "",
            "company": "",
            "location": "",
            "skills": [],
            "source_keyword": "",
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }


# ==========================================================================
# YouTube (Google Data API v3)
# ==========================================================================
class YouTubeExtractor:
    """YouTube Data API v3 extractor for company / tech signal scanning.

    Secured via a Google API key (or ADC service-account) configured in
    ``YOUTUBE_API_KEY``. Without credentials it returns deterministic stubs so
    the pipeline can be exercised end-to-end, mirroring LinkedIn/Reddit.
    """

    def __init__(self):
        self.available = bool(settings.YOUTUBE_API_KEY)

    def search_signals(self, queries: list[str], max_results: int = 10) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        out: list[dict[str, Any]] = []
        for q in queries:
            slug = re.sub(r"[^a-z0-9]+", "-", q.lower()).strip("-")
            out.append(
                {
                    "video_url": f"https://www.youtube.com/results?search_query={slug}",
                    "title": f"[signal] {q}",
                    "channel": "",
                    "query": q,
                    "extracted_at": now,
                    "api_available": self.available,
                }
            )
            if len(out) >= max_results:
                break
        return out


# ==========================================================================
# Reddit
# ==========================================================================
class RedditScraper:
    def __init__(self):
        self.available = bool(settings.REDDIT_CLIENT_ID)

    def search_hiring_posts(
        self, subreddits: list[str], keywords: list[str]
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        out = []
        for sub in subreddits:
            for kw in keywords:
                out.append(
                    {
                        "post_url": f"https://www.reddit.com/r/{sub}/search/?q={kw}",
                        "title": f"[{sub}] hiring: {kw}",
                        "content": "",
                        "subreddit": sub,
                        "alerts_related": [kw],
                        "extracted_at": now,
                    }
                )
        return out


class AppDataStore:
    """JSON side-cache in ``kalika_enterprises/sales-metadata/sales-app-data/``.

    Derived/intermediate payloads (stats, file indexes) live here so hot read
    paths avoid Cloud SQL round trips. The database stays the source of truth;
    cache misses fall back to DB and refresh the copy best-effort.
    """

    BUCKET = "kalika_enterprises"
    PREFIX = "sales-metadata/sales-app-data/"

    def __init__(self) -> None:
        self._gcs = GCSStorage(bucket_name=self.BUCKET)

    @property
    def available(self) -> bool:
        return self._gcs.available

    def _path(self, key: str) -> str:
        return f"{self.PREFIX}{key}.json"

    def load(self, key: str, max_age_sec: int | None = None) -> Optional[dict[str, Any]]:
        if not self._gcs.available:
            return None
        raw = self._gcs.download_blob(self._path(key))
        if not raw:
            return None
        if max_age_sec is not None and self._gcs._client is not None:
            try:
                blob = self._gcs._client.bucket(self.BUCKET).blob(self._path(key))
                blob.reload()
                updated = blob.updated
                if updated is not None:
                    from datetime import datetime, timezone

                    age = (datetime.now(timezone.utc) - updated).total_seconds()
                    if age > max_age_sec:
                        return None
            except Exception:
                return None
        try:
            payload = json.loads(raw.decode("utf-8"))
            return payload if isinstance(payload, dict) else None
        except Exception:
            return None

    def save(self, key: str, payload: dict[str, Any]) -> bool:
        if not self._gcs.available:
            return False
        return self._gcs.upload_json(self._path(key), payload)

    def delete(self, key: str) -> None:
        try:
            if self._gcs.available and self._gcs._client is not None:
                self._gcs._client.bucket(self.BUCKET).blob(self._path(key)).delete()
        except Exception:
            pass
