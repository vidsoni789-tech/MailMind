"""PersonalMail AI — Chat and Streaming Routes.

Powers the AI Assistant chat panel with Intent Routing, multi-agent delegation,
and SSE streaming.
"""

import asyncio
import json
import time
from typing import Any, AsyncGenerator, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from langmail.agents.orchestrator import MasterOrchestrator
from langmail.agents.supervisor import create_supervisor
from langmail.auth import is_authenticated
from langmail.services import DraftService, EmailService

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    selected_thread_id: Optional[str] = None
    selected_message_id: Optional[str] = None
    active_draft: Optional[dict[str, Any]] = None
    history: Optional[list[dict[str, Any]]] = None


@router.post("/chat")
def handle_chat(req: ChatRequest):
    """Synchronous chat endpoint powered by MasterOrchestrator."""
    if not is_authenticated():
        return {
            "reply": "Gmail is not connected yet. Please connect Gmail using credentials.json to enable full inbox assistance.",
            "draft_card": None,
        }

    start_time = time.time()
    orchestrator = MasterOrchestrator()

    try:
        result = orchestrator.process_message(
            message=req.message,
            selected_thread_id=req.selected_thread_id,
            selected_message_id=req.selected_message_id,
            active_draft=req.active_draft,
            history=req.history,
        )
        return result
    except Exception as e:
        # Graceful fallback to supervisor agent
        try:
            supervisor = create_supervisor()
            chat_messages = []
            if req.history:
                for h in req.history[-6:]:
                    r = h.get("role", "user")
                    c = h.get("content", "")
                    if r in ("user", "assistant") and c:
                        chat_messages.append({"role": r, "content": c})
            chat_messages.append({"role": "user", "content": req.message})

            res = supervisor.invoke({
                "messages": chat_messages,
                "files": {},
                "current_email_id": req.selected_message_id or "",
            })
            content = res["messages"][-1].content
            if isinstance(content, list):
                content = "".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in content])

            return {
                "reply": str(content).strip() or "Processed request.",
                "draft_card": None,
                "latency_ms": int((time.time() - start_time) * 1000),
            }
        except Exception as fallback_err:
            raise HTTPException(status_code=500, detail=f"Orchestrator error: {e}; Fallback error: {fallback_err}")


@router.get("/chat/stream")
async def stream_chat(
    message: str = Query(..., description="User message"),
    thread_id: Optional[str] = Query(None, description="Active thread ID"),
):
    """Server-Sent Events (SSE) streaming endpoint for live agent progress."""
    async def event_generator() -> AsyncGenerator[dict[str, str], None]:
        yield {
            "event": "status",
            "data": json.dumps({"step": "routing", "message": "Classifying user intent..."}),
        }
        await asyncio.sleep(0.2)

        if thread_id:
            yield {
                "event": "status",
                "data": json.dumps({"step": "reading_thread", "message": "Reading conversation thread..."}),
            }
            await asyncio.sleep(0.3)

        yield {
            "event": "status",
            "data": json.dumps({"step": "executing_agent", "message": "Executing specialized agent..."}),
        }
        await asyncio.sleep(0.3)

        def run_sync():
            req = ChatRequest(message=message, selected_thread_id=thread_id)
            return handle_chat(req)

        try:
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(None, run_sync)

            yield {
                "event": "result",
                "data": json.dumps(res),
            }
        except Exception as err:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(err)}),
            }

    return EventSourceResponse(event_generator())
