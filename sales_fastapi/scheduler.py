"""Customized cron scheduler service with Redis-backed task queue.

Design
------
- Uses Redis lists as a durable queue when ``REDIS_URL`` is reachable.
- Falls back to an in-process list when Redis is unavailable (local dev) so the
  API never hard-fails — mirroring the codebase's graceful-degradation policy.
- Tasks are user-scoped: each enqueue stores the owning ``user_id`` so a worker
  can process only what belongs to one tenant.
- Cloud Scheduler (GCP) hits ``POST /api/scheduler/run`` on a cron expression;
  the same endpoint powers the frontend "Run cron sweep" button.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from .config import settings

# Standard recurring tasks, aligned with Cloud Scheduler jobs in production.
STANDARD_TASKS: List[Dict[str, Any]] = [
    {
        "name": "sync_gcs_contacts",
        "cron": "0 */6 * * *",
        "description": "Import contacts from GCS bucket",
    },
    {
        "name": "refresh_email_connections",
        "cron": "*/30 * * * *",
        "description": "Re-test IMAP/SMTP connections",
    },
    {
        "name": "linkedin_hiring_alerts",
        "cron": "0 8 * * *",
        "description": "Daily LinkedIn hiring-keyword sweep",
    },
    {
        "name": "reddit_hiring_alerts",
        "cron": "0 8 * * *",
        "description": "Daily Reddit hiring-thread sweep",
    },
    {
        "name": "youtube_signal_scan",
        "cron": "0 9 * * *",
        "description": "YouTube company/tech signal scan (future)",
    },
    {
        "name": "whatsapp_reminders",
        "cron": "0 10 * * *",
        "description": "Queue follow-up WhatsApp reminders",
    },
    {
        "name": "events_whatsapp_due",
        "cron": "*/15 * * * *",
        "description": "Dispatch queued event WhatsApp messages whose schedule time has passed",
    },
    {
        "name": "pipeline_feedback_due",
        "cron": "0 * * * *",
        "description": "Send-due pass over feedback-pipeline queued WhatsApp messages (recent orders / new customers / leads)",
    },
    {
        "name": "build_interaction_dump",
        "cron": "0 2 * * *",
        "description": "Nightly: parse WhatsApp chat exports (kalika backup/) + app outbox into interaction_dump.json with attachment details",
    },
    {
        "name": "erp_dispatch_sync",
        "cron": "0 6 * * *",
        "description": "Daily 06:00: pull latest ERP report (ERP-V1/Reports) and upsert Dispatch + Orders for the sales dashboard/forecast",
    },
    {
        "name": "voice_transcription_sync",
        "cron": "30 3 * * *",
        "description": "09:00 IST: transcribe call recordings + layered tone/lead analysis (Gemma SLM first via Ollama, Gemini fallback)",
    },
    # --- Daily 20:00-22:00 IST window (UTC = 14:30-16:30) ---
    {
        "name": "daily_guardrail_checks",
        "cron": "30 14 * * *",
        "description": "20:00 IST: run preflight guardrail checks (config/security/data/ERP/LLM/UAT) and store the report",
    },
    {
        "name": "daily_llm_prompt_refine",
        "cron": "30 15 * * *",
        "description": "21:00 IST: refine the weekly prompt samples against last week's outcomes (human review required)",
    },
    {
        "name": "daily_uat_report",
        "cron": "30 16 * * *",
        "description": "22:00 IST: UAT daily digest — ERP sync status, journey events, pending feedback, model usage",
    },
    {
        "name": "weekly_uat_review",
        "cron": "30 14 * * 1",
        "description": "Monday 20:00 IST: weekly UAT review — feature enablement, stories, RL pattern candidates",
    },
    {
        "name": "youtube_channel_sync",
        "cron": "0 7 * * *",
        "description": "Daily 07:00: refresh YouTube channel stats via Data API v3 (Analytics API = OAuth, next scope)",
    },
    {
        "name": "rebuild_graph_preprocessing",
        "cron": "30 2 * * *",
        "description": "Nightly: networkx graph preprocessing (contacts x domains x intents x chats x ERP customers) -> nodes/edges/gexf for future graph DB",
    },
    {"name": "kpi_snapshot", "cron": "0 23 * * *", "description": "Nightly business-KPI snapshot"},
]

_QUEUE_KEY = "sales:cron"
_USER_QUEUE_PREFIX = "sales:cron:user:"


class SchedulerService:
    """Redis-backed (or in-memory fallback) cron task queue."""

    def __init__(self) -> None:
        self._redis = None
        self._memory_queue: List[Dict[str, Any]] = []
        self._redis_checked = False

    # -- backend plumbing ----------------------------------------------------
    def _get_redis(self):
        if self._redis_checked:
            return self._redis
        self._redis_checked = True
        try:
            import redis  # type: ignore

            client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1)
            client.ping()
            self._redis = client
        except Exception:
            self._redis = None
        return self._redis

    def backend_status(self) -> str:
        return "redis" if self._get_redis() is not None else "in-memory"

    @staticmethod
    def _queue_key(user_id: int | None) -> str:
        return f"{_USER_QUEUE_PREFIX}{user_id}" if user_id else _QUEUE_KEY

    # -- queue operations ----------------------------------------------------
    def enqueue(
        self, task_name: str, user_id: int | None = None, kwargs: Dict[str, Any] | None = None
    ) -> str:
        task_id = str(uuid.uuid4())
        payload = {
            "id": task_id,
            "name": task_name,
            "user_id": user_id,
            "kwargs": kwargs or {},
            "status": "queued",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        client = self._get_redis()
        if client is not None:
            client.rpush(self._queue_key(user_id), json.dumps(payload))
        else:
            self._memory_queue.append(payload)
        return task_id

    def enqueue_standard_tasks(self, user_id: int | None = None) -> List[str]:
        return [self.enqueue(t["name"], user_id=user_id) for t in STANDARD_TASKS]

    def queued(self, user_id: int | None = None) -> List[Dict[str, Any]]:
        client = self._get_redis()
        if client is not None:
            raw_items = client.lrange(self._queue_key(user_id), 0, -1)
            return [json.loads(raw) for raw in raw_items]
        if user_id is None:
            return list(self._memory_queue)
        return [t for t in self._memory_queue if t.get("user_id") == user_id]

    def clear(self, user_id: int | None = None) -> int:
        client = self._get_redis()
        if client is not None:
            key = self._queue_key(user_id)
            count = client.llen(key)
            client.delete(key)
            return int(count)
        before = len(self._memory_queue)
        if user_id is None:
            self._memory_queue.clear()
        else:
            self._memory_queue = [t for t in self._memory_queue if t.get("user_id") != user_id]
        return before - len(self._memory_queue)

    # -- introspection -------------------------------------------------------
    def registered_tasks(self) -> List[Dict[str, Any]]:
        return list(STANDARD_TASKS)

    def status(self, user_id: int | None = None) -> Dict[str, Any]:
        tasks = self.queued(user_id=user_id)
        return {
            "scheduler": "running",
            "backend": self.backend_status(),
            "queued_count": len(tasks),
            "queued_tasks": tasks,
            "registered_tasks": len(STANDARD_TASKS),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }


scheduler_service = SchedulerService()
