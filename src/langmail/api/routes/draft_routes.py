"""PersonalMail AI — Draft Routes."""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from langmail.services import DraftService

router = APIRouter(prefix="/api", tags=["drafts"])


class CreateDraftRequest(BaseModel):
    to_email: str
    subject: str
    body: str
    thread_id: Optional[str] = None
    gmail_draft_id: Optional[str] = None
    draft_id: Optional[str] = None



class UpdateDraftRequest(BaseModel):
    body: Optional[str] = None
    subject: Optional[str] = None
    status: Optional[str] = None


class ValidateDraftRequest(BaseModel):
    to_email: Optional[str] = ""
    subject: Optional[str] = ""
    body: str
    thread_id: Optional[str] = None
    attached_files: Optional[list[str]] = None


@router.post("/drafts/validate")
def validate_draft(req: ValidateDraftRequest):
    """Run automated quality and safety checks on draft content."""
    from langmail.agents.quality import QualityChecker
    from langmail.services import EmailService

    checker = QualityChecker()
    thread_ctx = ""
    if req.thread_id:
        msgs = EmailService.get_thread(req.thread_id)
        if msgs:
            thread_ctx = "\n".join(m.get("snippet", "") for m in msgs)

    result = checker.check(
        draft={"to_email": req.to_email, "subject": req.subject, "body": req.body},
        thread_context=thread_ctx,
        attached_files=req.attached_files,
    )
    return {
        "status": result.status,
        "checks": [c.model_dump() for c in result.checks],
    }


@router.get("/drafts")
def list_drafts(limit: int = 20):
    """List recent email drafts."""
    drafts = DraftService.list_drafts(limit=limit)
    return {"drafts": drafts}


@router.get("/drafts/{draft_id}")
def get_draft(draft_id: str):
    """Get single draft."""
    draft = DraftService.get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.post("/drafts")
def create_draft(req: CreateDraftRequest):
    """Save a draft locally and in Gmail, tracking edits if an existing draft was updated."""
    target_id = req.draft_id
    if not target_id and req.to_email:
        recent_drafts = DraftService.list_drafts(limit=5)
        for d in recent_drafts:
            if d.get("to_email", "").lower() == req.to_email.lower():
                target_id = d["id"]
                break

    # If this is updating an existing draft with new body text, record edit for learning!
    if target_id:
        existing = DraftService.get_draft(target_id)
        if existing and existing.get("body") and existing["body"].strip() != req.body.strip():
            DraftService.record_edit(
                draft_id=target_id,
                original_text=existing["body"],
                edited_text=req.body,
                generation_id=existing.get("generation_id"),
                contact_email=req.to_email,
                trigger_learning=True,
            )
            updated = DraftService.update_draft(
                draft_id=target_id,
                body=req.body,
                subject=req.subject,
                gmail_draft_id=req.gmail_draft_id,
            )
            if updated:
                return updated

    # Also save to Gmail if connected
    gmail_draft_id = req.gmail_draft_id
    try:
        from langmail.auth import is_authenticated
        if is_authenticated() and not gmail_draft_id:
            from langmail.tools.gmail_tools import gmail_create_draft
            g_draft = gmail_create_draft.invoke({
                "to": req.to_email,
                "subject": req.subject,
                "body": req.body,
                "thread_id": req.thread_id,
            })
            gmail_draft_id = g_draft.get("draft_id")
    except Exception:
        pass  # allow saving draft locally even if offline

    draft = DraftService.create_draft(
        to_email=req.to_email,
        subject=req.subject,
        body=req.body,
        thread_id=req.thread_id,
        gmail_draft_id=gmail_draft_id,
    )
    return draft



@router.patch("/drafts/{draft_id}")
def update_draft(draft_id: str, req: UpdateDraftRequest):
    """Update draft body or status, automatically capturing diffs and learning preferences."""
    draft = DraftService.get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    learned_prefs = []
    # If the user edited the body, record the edit and trigger edit-learning!
    if req.body and req.body != draft["body"]:
        _, learned_prefs = DraftService.record_edit(
            draft_id=draft_id,
            original_text=draft["body"],
            edited_text=req.body,
            generation_id=draft.get("generation_id"),
            contact_email=draft.get("to_email"),
            trigger_learning=True,
        )

    updated = DraftService.update_draft(
        draft_id=draft_id,
        body=req.body,
        subject=req.subject,
        status=req.status,
    )
    if updated:
        updated["learned_preferences"] = learned_prefs
    return updated


@router.get("/drafts/{draft_id}/edits")
def get_draft_edits(draft_id: str):
    """List edits recorded for a specific draft."""
    draft = DraftService.get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    edits = DraftService.list_edits(draft_id=draft_id)
    return {"draft_id": draft_id, "edits": edits}


@router.get("/edits")
def list_all_edits(limit: int = 50):
    """List recent user edits across all drafts."""
    edits = DraftService.list_edits(limit=limit)
    return {"edits": edits}


@router.get("/drafts/{draft_id}/quality-check")
def check_saved_draft_quality(draft_id: str):
    """Run automated quality check on a persisted draft."""
    draft = DraftService.get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    from langmail.agents.quality import QualityChecker
    checker = QualityChecker()
    result = checker.check(draft)
    return {
        "status": result.status,
        "checks": [c.model_dump() for c in result.checks],
    }


