"""PersonalMail AI — Profile and Preference Routes."""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from langmail.services import ProfileService

router = APIRouter(prefix="/api", tags=["profile"])


class ProfileUpdateRequest(BaseModel):
    role: Optional[str] = None
    organization: Optional[str] = None
    college: Optional[str] = None
    bio: Optional[str] = None
    signature: Optional[str] = None
    preferred_language: Optional[str] = None
    default_tone: Optional[str] = None
    default_reply_length: Optional[str] = None


class AddPreferenceRequest(BaseModel):
    pref_type: str
    value: str
    contact_email: Optional[str] = None
    confidence: float = 0.8


@router.get("/profile")
def get_profile():
    """Get current user profile."""
    return ProfileService.get_profile()


@router.put("/profile")
def update_profile(req: ProfileUpdateRequest):
    """Update user profile fields."""
    return ProfileService.update_profile(
        role=req.role,
        organization=req.organization,
        college=req.college,
        bio=req.bio,
        signature=req.signature,
        preferred_language=req.preferred_language,
        default_tone=req.default_tone,
        default_reply_length=req.default_reply_length,
    )


class UpdatePreferenceRequest(BaseModel):
    value: Optional[str] = None
    confidence: Optional[float] = None
    pref_type: Optional[str] = None


@router.get("/profile/preferences")
def list_preferences(contact_email: Optional[str] = None):
    """List learned writing preferences."""
    prefs = ProfileService.list_preferences(contact_email=contact_email)
    return {"preferences": prefs}


@router.get("/profile/preferences/effective")
def get_effective_preferences(contact_email: Optional[str] = None):
    """Get resolved effective style directives for drafting."""
    return ProfileService.get_effective_preferences(contact_email=contact_email)


@router.post("/profile/preferences")
def add_preference(req: AddPreferenceRequest):
    """Manually add or tune a style preference."""
    pref = ProfileService.add_preference(
        pref_type=req.pref_type,
        value=req.value,
        contact_email=req.contact_email,
        confidence=req.confidence,
        source="manual",
    )
    return pref


@router.put("/profile/preferences/{pref_id}")
def update_preference(pref_id: str, req: UpdatePreferenceRequest):
    """Update an existing style preference."""
    updated = ProfileService.update_preference(
        pref_id=pref_id,
        value=req.value,
        confidence=req.confidence,
        pref_type=req.pref_type,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Preference not found")
    return updated


@router.delete("/profile/preferences/{pref_id}")
def delete_preference(pref_id: str):
    """Delete a style preference."""
    success = ProfileService.delete_preference(pref_id)
    if not success:
        raise HTTPException(status_code=404, detail="Preference not found")
    return {"status": "deleted", "id": pref_id}

