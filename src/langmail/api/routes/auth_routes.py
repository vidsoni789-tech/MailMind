"""PersonalMail AI — Auth and System Health Routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from langmail.auth import is_authenticated, revoke_credentials
from langmail.config import settings
from langmail.services import EmailService

router = APIRouter(prefix="/api", tags=["auth"])


class AuthStatusResponse(BaseModel):
    authenticated: bool
    model: str
    summarization_model: str
    message: str


@router.get("/health")
def get_health():
    """System health check and basic stats."""
    metrics = EmailService.get_inbox_metrics()
    return {
        "status": "healthy",
        "app": "PersonalMail AI",
        "authenticated": is_authenticated(),
        "metrics": metrics,
    }


@router.get("/auth/status", response_model=AuthStatusResponse)
def get_auth_status():
    """Check if valid Gmail credentials exist."""
    authenticated = is_authenticated()
    return AuthStatusResponse(
        authenticated=authenticated,
        model=settings.model,
        summarization_model=settings.summarization_model,
        message="Gmail connected and ready" if authenticated else "Gmail not connected. Setup required.",
    )


@router.post("/auth/disconnect")
def disconnect_auth():
    """Revoke credentials and clear local OAuth token."""
    revoke_credentials()
    return {"status": "disconnected", "message": "Gmail credentials revoked."}
