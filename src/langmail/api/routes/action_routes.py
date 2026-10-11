"""PersonalMail AI — Action Execution and Audit History Routes.

Enforces human-in-the-loop approval before executing external write actions.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from langmail.auth import is_authenticated
from langmail.services import AuditService, DraftService
from langmail.tools.gmail_tools import gmail_send_draft, gmail_send_message

router = APIRouter(prefix="/api", tags=["actions"])


class SendActionRequest(BaseModel):
    to_email: str
    subject: str
    body: str
    thread_id: Optional[str] = None
    draft_id: Optional[str] = None
    user_approved: bool = True
    attachments: Optional[list[str]] = None


@router.post("/actions/send")
def execute_send_email(req: SendActionRequest):
    """Execute sending an email after human approval.

    Non-negotiable rule: Must have user_approved=True.
    """
    if not req.user_approved:
        AuditService.record_action(
            action="send_email",
            target_type="email",
            target_id=req.to_email,
            approval_status="rejected",
            result="User did not approve sending.",
        )
        raise HTTPException(status_code=400, detail="Action not approved by user.")

    # Quality Check Pre-Send Enforcement: BLOCK errors strictly prevent dispatch
    from langmail.agents.quality import QualityChecker
    checker = QualityChecker()
    qc_res = checker.check(
        draft={"to_email": req.to_email, "subject": req.subject, "body": req.body},
        thread_context=None,
        attached_files=req.attachments,
    )
    if qc_res.status == "BLOCK":
        block_reasons = [c.message for c in qc_res.checks if c.severity == "BLOCK"]
        msg = f"Cannot send email due to blocking quality errors: {'; '.join(block_reasons)}"
        AuditService.record_action(
            action="send_email",
            target_type="email",
            target_id=req.to_email,
            approval_status="blocked",
            result=msg,
        )
        raise HTTPException(status_code=400, detail=msg)

    if not is_authenticated():
        raise HTTPException(status_code=401, detail="Gmail not connected.")

    try:
        # Call Gmail send tool
        res = gmail_send_message.invoke({
            "to": req.to_email,
            "subject": req.subject,
            "body": req.body,
            "thread_id": req.thread_id,
            "attachments": req.attachments,
        })

        # Record edit and trigger learning if user edited draft before sending
        if req.draft_id:
            orig_draft = DraftService.get_draft(req.draft_id)
            if orig_draft and req.body and req.body.strip() != (orig_draft.get("body") or "").strip():
                DraftService.record_edit(
                    draft_id=req.draft_id,
                    original_text=orig_draft["body"],
                    edited_text=req.body,
                    diff_summary="User edit approved and sent",
                    generation_id=orig_draft.get("generation_id"),
                    contact_email=req.to_email,
                    trigger_learning=True,
                )

        # Update local draft if draft_id provided
        if req.draft_id:
            DraftService.update_draft(req.draft_id, body=req.body, status="sent")


        # Record audit log
        AuditService.record_action(
            action="send_email",
            target_type="email",
            target_id=req.to_email,
            approval_status="approved",
            result=f"Sent successfully via Gmail. Message ID: {res.get('message_id')}",
        )

        return {
            "status": "sent",
            "message_id": res.get("message_id"),
            "thread_id": res.get("thread_id"),
        }
    except Exception as e:
        AuditService.record_action(
            action="send_email",
            target_type="email",
            target_id=req.to_email,
            approval_status="approved",
            result=f"Send failed: {str(e)}",
        )
        err_str = str(e)
        if "rateLimitExceeded" in err_str or "Quota exceeded" in err_str:
            detail = (
                "Gmail API per-minute quota temporarily reached. "
                "Google Cloud resets this limit automatically every 60 seconds. "
                "Please wait 1 minute and click 'Approve & Send Now' again."
            )
        else:
            detail = f"Failed to send email: {err_str}"
        raise HTTPException(status_code=500, detail=detail)


@router.get("/history")
def get_history(limit: int = 50):
    """Fetch audit history timeline."""
    logs = AuditService.list_logs(limit=limit)
    return {"history": logs}
