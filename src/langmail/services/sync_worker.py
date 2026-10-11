"""PersonalMail AI — Background Sync Worker.

Runs continuous background polling and incremental synchronization with Gmail.
Extracts new action items and categorizes incoming messages without blocking the UI.
"""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

from langmail.auth import is_authenticated
from langmail.config import settings

logger = logging.getLogger(__name__)


class SyncWorker:
    """Singleton background worker running periodic incremental syncs."""

    _instance: Optional["SyncWorker"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "SyncWorker":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.interval_seconds: int = 120  # Default 2 minutes
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.is_syncing: bool = False
        self.last_sync_at: Optional[str] = None
        self.total_syncs: int = 0
        self.last_error: Optional[str] = None
        self.last_stats: dict[str, Any] = {}

    def start(self, interval_seconds: Optional[int] = None) -> dict[str, Any]:
        """Start the background sync worker daemon."""
        if interval_seconds and interval_seconds > 0:
            self.interval_seconds = interval_seconds

        with self._lock:
            if self._running and self._thread and self._thread.is_alive():
                return self.get_status()

            self._running = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._worker_loop,
                name="LangMail-SyncWorker",
                daemon=True,
            )
            self._thread.start()
            logger.info("Background SyncWorker started with interval %ss", self.interval_seconds)

        return self.get_status()

    def stop(self) -> dict[str, Any]:
        """Stop the background sync worker."""
        with self._lock:
            if not self._running:
                return self.get_status()

            self._running = False
            self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

        logger.info("Background SyncWorker stopped")
        return self.get_status()

    def trigger_now(self) -> dict[str, Any]:
        """Manually trigger a sync cycle right now."""
        return self._run_single_sync_cycle()

    def _worker_loop(self) -> None:
        """Main periodic polling loop."""
        # Run an initial check after a short 2-second startup grace period
        if not self._stop_event.wait(2.0):
            self._run_single_sync_cycle()

        while not self._stop_event.is_set():
            # Wait for next interval or early exit
            if self._stop_event.wait(self.interval_seconds):
                break
            self._run_single_sync_cycle()

    def _run_single_sync_cycle(self) -> dict[str, Any]:
        """Execute one incremental sync pass and auto-extract tasks."""
        if self.is_syncing:
            return {"status": "in_progress", "message": "Sync already running"}

        self.is_syncing = True
        try:
            if not is_authenticated():
                self.last_error = "Gmail authentication credentials not configured"
                return {
                    "status": "skipped",
                    "reason": "unauthenticated",
                    "last_error": self.last_error,
                }

            from langmail.sync import run_incremental_sync

            stats = run_incremental_sync()
            self.total_syncs += 1
            self.last_sync_at = datetime.now(timezone.utc).isoformat()
            self.last_error = None
            self.last_stats = stats or {}

            # Perform background action item extraction on newly added emails
            self._auto_process_new_messages()

            return {"status": "success", "stats": stats, "timestamp": self.last_sync_at}

        except Exception as e:
            self.last_error = str(e)
            logger.exception("Error during background sync pass: %s", e)
            return {"status": "error", "error": str(e)}
        finally:
            self.is_syncing = False

    def _auto_process_new_messages(self) -> None:
        """Auto-extract tasks and commitments from recent un-triaged emails."""
        try:
            from langmail.services.email_service import EmailService
            from langmail.agents.extractor import ActionExtractor

            # Fetch up to 10 most recent unread messages that need review
            recent_unreads = EmailService.list_emails(unread_only=True, limit=10)
            if not recent_unreads:
                return

            extractor = ActionExtractor()
            for email in recent_unreads:
                body = email.get("body") or email.get("snippet") or ""
                if not body:
                    continue
                # Extract any deadlines/tasks and store into TaskService
                try:
                    extractor.extract_tasks(
                        thread_id=email.get("thread_id") or email.get("message_id") or "manual",
                        email_body=body,
                        sender_email=email.get("from_email"),
                        message_id=email.get("message_id"),
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.debug("Background task extraction step skipped: %s", e)

    def get_status(self) -> dict[str, Any]:
        """Return worker state, health, and sync history."""
        from langmail.sync import get_sync_status

        sync_meta = {}
        try:
            sync_meta = get_sync_status()
        except Exception:
            pass

        return {
            "running": self._running and (self._thread.is_alive() if self._thread else False),
            "is_syncing": self.is_syncing,
            "interval_seconds": self.interval_seconds,
            "last_sync_at": self.last_sync_at,
            "total_syncs": self.total_syncs,
            "last_error": self.last_error,
            "last_stats": self.last_stats,
            "sync_metadata": sync_meta,
        }


# Singleton accessor
sync_worker = SyncWorker()
