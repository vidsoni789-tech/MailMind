"""PersonalMail AI — Email and Thread Routes."""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from langmail.services import EmailService
from langmail.auth import is_authenticated

router = APIRouter(prefix="/api", tags=["emails"])


@router.get("/emails")
def list_emails(
    unread_only: bool = Query(False, description="Filter for unread messages"),
    category: Optional[str] = Query(None, description="Category filter (e.g. job, work, personal)"),
    priority: Optional[str] = Query(None, description="Priority filter (urgent, high, medium, low)"),
    requires_reply: Optional[bool] = Query(None, description="Filter for emails needing reply"),
    search: Optional[str] = Query(None, description="Search query string"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List emails with category, priority, and search filters."""
    emails = EmailService.list_emails(
        unread_only=unread_only,
        category=category,
        priority=priority,
        requires_reply=requires_reply,
        search_query=search,
        limit=limit,
        offset=offset,
    )
    return {"emails": emails, "count": len(emails), "offset": offset}


@router.get("/emails/{message_id}")
def get_email(message_id: str):
    """Get single email metadata and content."""
    email = EmailService.get_email(message_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    # Fetch full plain text body if authenticated and not already loaded
    if is_authenticated() and not email.get("body"):
        try:
            thread_id = email.get("thread_id")
            if thread_id:
                from langmail.context import _fetch_thread
                tdata = _fetch_thread(thread_id)
                for m in tdata.get("messages", []):
                    if (m.get("message_id") or m.get("id")) == message_id:
                        email["body"] = m.get("body", "")
                        break
        except Exception:
            pass

    if not email.get("body"):
        email["body"] = email.get("snippet", "")

    return email


@router.get("/threads/{thread_id}")
def get_thread(thread_id: str):
    """Fetch complete thread conversation with full message bodies."""
    db_messages = EmailService.get_thread(thread_id)

    # Attempt fetching full messages (including bodies) from Gmail / cache
    live_messages = []
    if is_authenticated():
        try:
            from langmail.context import _fetch_thread
            tdata = _fetch_thread(thread_id)
            live_messages = tdata.get("messages", [])
        except Exception:
            try:
                from langmail.tools.gmail_tools import gmail_read_thread
                tdata = gmail_read_thread.invoke({"thread_id": thread_id})
                live_messages = tdata.get("messages", [])
            except Exception:
                pass

    if live_messages:
        db_by_id = {m["message_id"]: m for m in db_messages} if db_messages else {}
        merged = []
        for lmsg in live_messages:
            mid = lmsg.get("id") or lmsg.get("message_id")
            db_meta = db_by_id.get(mid, {})
            merged.append({
                "message_id": mid,
                "thread_id": thread_id,
                "subject": lmsg.get("subject") or db_meta.get("subject", ""),
                "snippet": lmsg.get("snippet") or db_meta.get("snippet", ""),
                "from_email": db_meta.get("from_email") or lmsg.get("from", ""),
                "from_name": db_meta.get("from_name") or lmsg.get("from", ""),
                "to_emails": db_meta.get("to_emails") or lmsg.get("to", ""),
                "date": lmsg.get("date") or db_meta.get("date", ""),
                "body": lmsg.get("body") or db_meta.get("snippet", ""),
                "is_read": db_meta.get("is_read", 1),
                "category": db_meta.get("category", "other"),
                "priority": db_meta.get("priority", "medium"),
                "requires_reply": db_meta.get("requires_reply", 0),
                "security_risk": db_meta.get("security_risk", "safe"),
                "triage_reason": db_meta.get("triage_reason", ""),
            })
        return {"thread_id": thread_id, "messages": merged}

    if db_messages:
        for m in db_messages:
            if not m.get("body"):
                m["body"] = m.get("snippet", "")
        return {"thread_id": thread_id, "messages": db_messages}

    raise HTTPException(status_code=404, detail="Thread not found")


@router.patch("/emails/{message_id}/read")
def mark_email_read(message_id: str, is_read: bool = Query(True)):
    """Mark email read or unread."""
    EmailService.mark_read(message_id, is_read)
    return {"message_id": message_id, "is_read": is_read}


@router.get("/metrics")
def get_metrics():
    """Get inbox badge metrics (unread, needs reply, high priority, security alerts)."""
    return EmailService.get_inbox_metrics()


class SyncRequest(BaseModel):
    incremental: bool = True
    months: int = 3


@router.post("/emails/sync")
def trigger_sync(req: SyncRequest):
    """Trigger background or incremental sync."""
    if not is_authenticated():
        raise HTTPException(status_code=401, detail="Gmail not connected")

    from langmail.sync import run_incremental_sync, run_initial_sync
    try:
        if req.incremental:
            stats = run_incremental_sync()
        else:
            stats = run_initial_sync(months=req.months)
        return {"status": "success", "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
