"""PersonalMail AI — Sync Routes.

Provides endpoints to manage background sync worker and trigger immediate synchronization.
"""

from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from langmail.services.sync_worker import sync_worker

router = APIRouter(prefix="/api/sync", tags=["sync"])


class StartWorkerRequest(BaseModel):
    interval_seconds: Optional[int] = 120


@router.get("/status")
def get_sync_status():
    """Get current status of background sync worker and local index metadata."""
    return sync_worker.get_status()


@router.post("/start")
def start_sync_worker(req: Optional[StartWorkerRequest] = None):
    """Start background incremental sync worker."""
    interval = req.interval_seconds if req else 120
    return sync_worker.start(interval_seconds=interval)


@router.post("/stop")
def stop_sync_worker():
    """Stop background sync worker."""
    return sync_worker.stop()


@router.post("/trigger")
def trigger_sync_now():
    """Trigger an immediate incremental sync cycle."""
    return sync_worker.trigger_now()
