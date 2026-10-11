"""PersonalMail AI — Main FastAPI Application."""

import os
import sys

if sys.platform == "win32":
    os.environ["PYTHONUTF8"] = "1"
    try:
        if sys.stdout.encoding != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr.encoding != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from langmail.api.routes.action_routes import router as action_router
from langmail.api.routes.attachment_routes import router as attachment_router
from langmail.api.routes.auth_routes import router as auth_router
from langmail.api.routes.chat_routes import router as chat_router
from langmail.api.routes.draft_routes import router as draft_router
from langmail.api.routes.email_routes import router as email_router
from langmail.api.routes.profile_routes import router as profile_router
from langmail.api.routes.sync_routes import router as sync_router
from langmail.api.routes.task_routes import router as task_router
from langmail.config import ensure_dirs, settings
from langmail.services.sync_worker import sync_worker
from langmail.storage.database import get_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    ensure_dirs()
    # Bootstrap database tables
    conn = get_connection()
    conn.close()
    # Auto-triage any unclassified emails
    try:
        from langmail.services.email_service import EmailService
        EmailService.triage_all_emails()
    except Exception:
        pass
    # Start background sync worker if authenticated
    try:
        sync_worker.start()
    except Exception:
        pass
    yield
    # Stop background sync worker on shutdown
    try:
        sync_worker.stop()
    except Exception:
        pass


app = FastAPI(
    title="PersonalMail AI",
    description="Personalized multi-agent email assistant operating system",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        settings.frontend_url,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)
app.include_router(email_router)
app.include_router(task_router)
app.include_router(draft_router)
app.include_router(profile_router)
app.include_router(action_router)
app.include_router(chat_router)
app.include_router(attachment_router)
app.include_router(sync_router)

# Serve built frontend static files if present
frontend_dist = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists() and frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
