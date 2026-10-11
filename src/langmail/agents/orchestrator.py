"""PersonalMail AI — Master Agent Orchestrator.

Orchestrates the upgraded multi-agent pipeline with Intent Routing,
dedicated specialized agents, and Human-in-the-Loop approval nodes:
  User Message
      ↓
  [Intent Router] ──┬──► [Summarizer Agent] ──► Structured Summary & DB Update
                    ├──► [Action Extractor] ──► Tasks Extracted & Saved to DB
                    ├──► [Reply / Compose Writer] ──► Draft Card (PAUSE: Approval)
                    ├──► [Search & Triage] ──► Filtered Email List
                    └──► [Supervisor Assistant] ──► Conversational Support
"""

import re
import time
from typing import Any, Optional
from langchain.chat_models import init_chat_model

from langmail.agents.attachment import AttachmentAgent
from langmail.agents.extractor import TaskExtractor
from langmail.agents.quality import QualityChecker
from langmail.agents.router import IntentRouter
from langmail.agents.summarizer import EmailSummarizer
from langmail.agents.writer import ReplyWriter
from langmail.config import settings
from langmail.models.agent_schemas import DraftProposal, IntentType
from langmail.services import DraftService, EmailService, TaskService


class MasterOrchestrator:
    """Coordinates intent routing, specialized agent execution, and human approval."""

    def __init__(self):
        self.router = IntentRouter()
        self.summarizer = EmailSummarizer()
        self.extractor = TaskExtractor()
        self.writer = ReplyWriter()
        self.quality_checker = QualityChecker()
        self.attachment_agent = AttachmentAgent()

    def process_message(
        self,
        message: str,
        selected_thread_id: Optional[str] = None,
        selected_message_id: Optional[str] = None,
        active_draft: Optional[dict[str, Any]] = None,
        history: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """Main entrypoint for processing user messages."""
        start_time = time.time()

        # 1. Classify intent
        intent_res = self.router.classify(message, thread_id=selected_thread_id)
        intent = intent_res.intent

        # 2. Build conversation history string
        conv_lines = []
        if history:
            for h in history[-8:]:
                r = "User" if h.get("role") == "user" else "Assistant"
                c = str(h.get("content", "")).strip()
                if c:
                    conv_lines.append(f"{r}: {c}")
                if h.get("draftCard"):
                    dc = h["draftCard"]
                    conv_lines.append(f"  [Previous Draft: To: {dc.get('to_email')}, Subject: {dc.get('subject')}, Body: {dc.get('body')}]")
        conv_history_str = "\n".join(conv_lines) if conv_lines else "No previous conversation turns."

        # 3. Resolve active/candidate draft across parameters, history, or recent records
        target_draft = active_draft
        if not target_draft and history:
            for item in reversed(history):
                if item.get("draftCard"):
                    target_draft = item["draftCard"]
                    break
        if not target_draft and selected_thread_id:
            recent_drafts = DraftService.list_drafts(limit=5)
            target_draft = next(
                (d for d in recent_drafts if d.get("thread_id") == selected_thread_id),
                None,
            )

        # 4. Gather context if thread is selected or referenced
        thread_messages = []
        thread_context_str = ""
        contact_email = None
        subject = None

        if selected_thread_id or selected_message_id:
            from langmail.auth import is_authenticated
            if selected_thread_id:
                if is_authenticated():
                    try:
                        from langmail.context import _fetch_thread
                        tdata = _fetch_thread(selected_thread_id)
                        thread_messages = tdata.get("messages", [])
                    except Exception:
                        pass
                if not thread_messages:
                    thread_messages = EmailService.get_thread(selected_thread_id)
            elif selected_message_id:
                single_msg = EmailService.get_email(selected_message_id)
                if single_msg:
                    thread_messages = [single_msg]

            if thread_messages:
                lines = []
                for m in thread_messages:
                    sender = m.get('from_name') or m.get('from') or m.get('from_email') or ''
                    lines.append(f"From: {sender}")
                    lines.append(f"Date: {m.get('date', '')}")
                    lines.append(f"Subject: {m.get('subject', '')}")
                    body_val = m.get('body') or m.get('body_text') or m.get('snippet') or ''
                    lines.append(f"Email Content:\n{body_val}\n---")
                thread_context_str = "\n".join(lines)
                latest = thread_messages[-1]
                contact_email = latest.get("from_email") or latest.get("from")
                subject = latest.get("subject")
                if subject and not subject.lower().startswith("re:"):
                    subject = f"Re: {subject}"

        # If user explicitly specifies a recipient email in the message, that takes priority
        msg_email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", message)
        if msg_email_match:
            contact_email = msg_email_match.group(0)

        msg_lower = message.lower().strip()

        # 5. Check if this is a recipient correction / clarification on an existing active draft
        is_recipient_update = False
        if target_draft and target_draft.get("body") and msg_email_match:
            cleaned = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "", msg_lower).strip()
            cleaned = re.sub(r"[,\.:;!?'\"]", " ", cleaned).strip()
            connector_words = {
                "", "ok", "okay", "the", "email", "mail", "is", "its", "it's", "to", "send",
                "change", "update", "set", "recipient", "address", "actually", "correct", "my",
                "use", "please", "yes", "sure", "here", "for", "not", "instead", "new", "this"
            }
            words = set(cleaned.split())
            if words.issubset(connector_words):
                is_recipient_update = True

        if is_recipient_update and target_draft:
            new_email = msg_email_match.group(0)
            updated_body = target_draft.get("body", "")
            updated_subject = target_draft.get("subject") or subject or "Regarding your email"
            draft_thread_id = target_draft.get("thread_id") or selected_thread_id

            draft_proposal = DraftProposal(
                to_email=new_email,
                subject=updated_subject,
                body=updated_body,
                tone=target_draft.get("tone", "professional"),
                confidence=1.0,
                attachment_requests=target_draft.get("attachment_requests", []),
                thread_id=draft_thread_id,
                draft_id=target_draft.get("id"),
            )

            record = DraftService.create_draft(
                to_email=draft_proposal.to_email,
                subject=draft_proposal.subject,
                body=draft_proposal.body,
                thread_id=draft_proposal.thread_id,
            )
            draft_proposal.draft_id = record.get("id")

            qc_result = self.quality_checker.check(
                draft=draft_proposal,
                thread_context=thread_context_str,
            )

            att_recom = self.attachment_agent.suggest_attachments(
                text=message,
                thread_context=f"{draft_proposal.body}\n{thread_context_str}",
                requested_files=draft_proposal.attachment_requests,
            )
            preselected_attachments = [s.model_dump() for s in att_recom.suggestions if s.is_selected]

            draft_card_data = {
                "id": draft_proposal.draft_id,
                "to_email": draft_proposal.to_email,
                "subject": draft_proposal.subject,
                "body": draft_proposal.body,
                "thread_id": draft_proposal.thread_id,
                "tone": draft_proposal.tone,
                "attachment_requests": draft_proposal.attachment_requests,
                "attachment_suggestions": [s.model_dump() for s in att_recom.suggestions],
                "selected_attachments": preselected_attachments,
                "detected_attachment_requests": att_recom.requested_files,
                "status": "generated",
                "requires_approval": True,
                "quality_check": {
                    "status": qc_result.status,
                    "checks": [c.model_dump() for c in qc_result.checks],
                },
                "warnings": [c.message for c in qc_result.checks if c.severity in ("WARNING", "BLOCK")],
            }

            reply_text = (
                f"✅ I've updated the recipient email to **{new_email}**.\n\n"
                f"Your draft message has been preserved and re-validated. "
                f"Review the draft details below, or click **Approve & Send Now** when ready."
            )

            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "reply": reply_text,
                "draft_card": draft_card_data,
                "intent": IntentType.IMPROVE.value,
                "latency_ms": latency_ms,
            }

        # 6. Check if this is an IMPROVE operation on an existing draft
        improve_keywords = [
            "formal", "friendly", "concise", "shorter", "longer",
            "improve", "rewrite", "polish", "grammar"
        ]

        is_compose_or_reply = any(
            w in msg_lower
            for w in [
                "compose", "draft a reply", "draft reply", "reply to",
                "write a reply", "write an email", "send an email", "tell them"
            ]
        )
        is_summary_or_tasks = any(
            w in msg_lower
            for w in [
                "summarize", "summary", "extract task", "extract deadline", "action item"
            ]
        )

        is_improve = (
            not is_compose_or_reply
            and not is_summary_or_tasks
            and (
                intent == IntentType.IMPROVE
                or any(kw in msg_lower for kw in improve_keywords)
            )
        )

        # Branch A1: Improve Existing Draft (only if an active draft for this context exists)
        if is_improve and target_draft and target_draft.get("body"):
            current_body = target_draft.get("body", "")
            draft_recipient = target_draft.get("to_email") or contact_email
            draft_subject = target_draft.get("subject") or subject
            draft_thread_id = target_draft.get("thread_id") or selected_thread_id

            draft_proposal = self.writer.improve_draft(
                instruction=message,
                current_body=current_body,
                recipient=draft_recipient,
                subject=draft_subject,
                thread_id=draft_thread_id,
                conversation_history=conv_history_str,
                persist=True,
            )

            reply_text = (
                f"✨ I've rewritten the draft with a **{draft_proposal.tone}** tone as requested.\n\n"
                f"Review the updated draft below. You can click **Edit** to adjust any details, "
                f"or **Approve & Send Now** when ready."
            )

            # Pre-send quality validation
            qc_result = self.quality_checker.check(
                draft=draft_proposal,
                thread_context=thread_context_str,
            )

            # Smart attachment recommendations
            att_recom = self.attachment_agent.suggest_attachments(
                text=message,
                thread_context=f"{draft_proposal.body}\n{thread_context_str}",
                requested_files=draft_proposal.attachment_requests,
            )

            preselected_attachments = [s.model_dump() for s in att_recom.suggestions if s.is_selected]

            draft_card_data = {
                "id": draft_proposal.draft_id or target_draft.get("id"),
                "to_email": draft_proposal.to_email,
                "subject": draft_proposal.subject,
                "body": draft_proposal.body,
                "thread_id": draft_proposal.thread_id,
                "tone": draft_proposal.tone,
                "attachment_requests": draft_proposal.attachment_requests,
                "attachment_suggestions": [s.model_dump() for s in att_recom.suggestions],
                "selected_attachments": preselected_attachments,
                "detected_attachment_requests": att_recom.requested_files,
                "status": "generated",
                "requires_approval": True,
                "quality_check": {
                    "status": qc_result.status,
                    "checks": [c.model_dump() for c in qc_result.checks],
                },
                "warnings": [c.message for c in qc_result.checks if c.severity in ("WARNING", "BLOCK")],
            }

            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "reply": reply_text,
                "draft_card": draft_card_data,
                "intent": IntentType.IMPROVE.value,
                "latency_ms": latency_ms,
            }

        # If user explicitly specifies a recipient email or compose keywords, route to draft writer
        if is_compose_or_reply or (msg_email_match and any(w in msg_lower for w in ["send", "mail", "write", "saying", "tell", "draft", "meet", "to", "email", "reply"])):
            intent = IntentType.REPLY

        # Branch A2: Reply, Compose, or Send Request / Fresh Generation
        if intent in [IntentType.REPLY, IntentType.IMPROVE, IntentType.REGENERATE, IntentType.SEND, IntentType.FORWARD]:
            active_draft_info = ""
            if target_draft and target_draft.get("body"):
                active_draft_info = (
                    f"To: {target_draft.get('to_email')}\n"
                    f"Subject: {target_draft.get('subject')}\n"
                    f"Body:\n{target_draft.get('body')}"
                )

            draft_proposal = self.writer.generate_draft(
                instruction=message,
                thread_context=thread_context_str,
                recipient=contact_email or (target_draft.get("to_email") if target_draft else None),
                thread_id=selected_thread_id or (target_draft.get("thread_id") if target_draft else None),
                subject=subject or (target_draft.get("subject") if target_draft else None),
                conversation_history=conv_history_str,
                active_draft_context=active_draft_info,
                persist=True,
            )

            reply_text = (
                f"✍️ I've prepared a draft response based on your instruction.\n\n"
                f"Review the draft details below. You can click **Edit** to modify it, "
                f"**Improve** to adjust the tone, or **Approve & Send Now** when ready."
            )

            # Pre-send quality validation
            qc_result = self.quality_checker.check(
                draft=draft_proposal,
                thread_context=thread_context_str,
            )

            # Smart attachment recommendations
            att_recom = self.attachment_agent.suggest_attachments(
                text=message,
                thread_context=f"{draft_proposal.body}\n{thread_context_str}",
                requested_files=draft_proposal.attachment_requests,
            )

            preselected_attachments = [s.model_dump() for s in att_recom.suggestions if s.is_selected]

            draft_card_data = {
                "id": draft_proposal.draft_id,
                "to_email": draft_proposal.to_email,
                "subject": draft_proposal.subject,
                "body": draft_proposal.body,
                "thread_id": draft_proposal.thread_id,
                "tone": draft_proposal.tone,
                "attachment_requests": draft_proposal.attachment_requests,
                "attachment_suggestions": [s.model_dump() for s in att_recom.suggestions],
                "selected_attachments": preselected_attachments,
                "detected_attachment_requests": att_recom.requested_files,
                "status": "generated",
                "requires_approval": True,
                "quality_check": {
                    "status": qc_result.status,
                    "checks": [c.model_dump() for c in qc_result.checks],
                },
                "warnings": [c.message for c in qc_result.checks if c.severity in ("WARNING", "BLOCK")],
            }


            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "reply": reply_text,
                "draft_card": draft_card_data,
                "intent": intent.value,
                "latency_ms": latency_ms,
            }

        # Branch: Find Attachment / Files
        if intent == IntentType.FIND_ATTACHMENT:
            recom = self.attachment_agent.suggest_attachments(
                text=message,
                thread_context=thread_context_str,
            )
            if recom.suggestions:
                lines = [f"📎 Found **{len(recom.suggestions)} matching file(s)** in your local files index:\n"]
                for idx, s in enumerate(recom.suggestions, 1):
                    lines.append(f"**{idx}. {s.filename}** ({int(s.confidence * 100)}% match)")
                    lines.append(f"• Reason: {s.reason}")
                    lines.append(f"• Path: `{s.file_path}`")
                    lines.append("")
                lines.append("You can select these files directly on any draft card before approving and sending.")
                reply_text = "\n".join(lines).strip()
            else:
                reply_text = (
                    "📁 No matching files were found in your local files index.\n\n"
                    "Place your documents (e.g. `Resume.pdf`, `Report.docx`) in `~/.langmail/files/` "
                    "or upload them in the **Files** tab to enable smart attachment recommendations."
                )

            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "reply": reply_text,
                "draft_card": None,
                "intent": intent.value,
                "latency_ms": latency_ms,
            }

        # Branch B: Summarize
        if intent == IntentType.SUMMARIZE:
            target_content = thread_context_str
            if not target_content:
                # Fallback to recent unread emails
                recent_emails = EmailService.list_emails(limit=5)
                if recent_emails:
                    target_content = "\n\n".join(
                        f"From: {e.get('from_name')} <{e.get('from_email')}>\n"
                        f"Subject: {e.get('subject')}\nSnippet: {e.get('snippet')}"
                        for e in recent_emails
                    )

            if not target_content:
                reply_text = "No emails found to summarize. Connect your Gmail or trigger a sync to populate your inbox."
            else:
                summary_res = self.summarizer.summarize(target_content, thread_id=selected_thread_id)
                lines = [f"📋 **Executive Summary:**\n{summary_res.summary}\n"]
                if summary_res.decisions:
                    lines.append("✅ **Decisions & Agreements:**")
                    lines.extend(f"• {d}" for d in summary_res.decisions)
                    lines.append("")
                if summary_res.deadlines:
                    lines.append("⏰ **Key Dates & Deadlines:**")
                    lines.extend(f"• {dl}" for dl in summary_res.deadlines)
                    lines.append("")
                if summary_res.requests:
                    lines.append("❓ **Requests & Questions:**")
                    lines.extend(f"• {rq}" for rq in summary_res.requests)
                    lines.append("")
                if summary_res.next_steps:
                    lines.append("🚀 **Next Steps:**")
                    lines.extend(f"• {ns}" for ns in summary_res.next_steps)

                reply_text = "\n".join(lines).strip()

            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "reply": reply_text,
                "draft_card": None,
                "intent": intent.value,
                "latency_ms": latency_ms,
            }

        # Branch C: Extract Tasks
        if intent == IntentType.TASKS:
            target_content = thread_context_str
            if not target_content:
                recent_emails = EmailService.list_emails(limit=5)
                if recent_emails:
                    target_content = "\n\n".join(
                        f"From: {e.get('from_email')}\nSubject: {e.get('subject')}\n{e.get('snippet')}"
                        for e in recent_emails
                    )

            if not target_content:
                reply_text = "No active emails found to extract action items from."
            else:
                extraction_res = self.extractor.extract_and_persist(
                    content=target_content,
                    thread_id=selected_thread_id or "inbox_batch",
                    source_from=contact_email,
                    persist=True,
                )

                if extraction_res.actions:
                    lines = [f"✅ Extracted **{len(extraction_res.actions)} task(s)** and added them to your Tasks list:\n"]
                    for idx, a in enumerate(extraction_res.actions, 1):
                        lines.append(f"**{idx}. {a.title}**")
                        lines.append(f"• **Priority:** {a.priority.upper()}")
                        if a.deadline:
                            lines.append(f"• **Deadline:** {a.deadline}")
                        if a.source_quote:
                            lines.append(f"• *Quote:* \"{a.source_quote}\"")
                        lines.append("")
                    reply_text = "\n".join(lines).strip()
                else:
                    reply_text = "I analyzed the emails and found no pending action items or deadlines."

            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "reply": reply_text,
                "draft_card": None,
                "intent": intent.value,
                "latency_ms": latency_ms,
            }

        # Branch D: Search
        if intent == IntentType.SEARCH:
            search_query = message
            for prefix in ["search for", "find emails", "show emails from", "find message"]:
                if prefix in message.lower():
                    search_query = message.lower().split(prefix, 1)[-1].strip()

            found_emails = EmailService.list_emails(search_query=search_query, limit=5)
            if found_emails:
                lines = [f"🔍 Found **{len(found_emails)} email(s)** matching '{search_query}':\n"]
                for idx, e in enumerate(found_emails, 1):
                    lines.append(f"**{idx}. {e.get('subject', '(No Subject)')}**")
                    lines.append(f"• **From:** {e.get('from_name', '')} <{e.get('from_email', '')}>")
                    lines.append(f"• **Date:** {e.get('date', '')}")
                    if e.get("snippet"):
                        lines.append(f"• **Snippet:** {e.get('snippet')}")
                    lines.append("")
                reply_text = "\n".join(lines).strip()
            else:
                reply_text = f"No emails found matching '{search_query}'. Try syncing or refining your search term."

            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "reply": reply_text,
                "draft_card": None,
                "intent": intent.value,
                "latency_ms": latency_ms,
            }

        # Branch E: General Conversational Assistant (Fallback)
        # Try conversational response with conversation history
        try:
            conv_prompt = f"""You are PersonalMail AI, an intelligent personal email assistant.
Answer the user's message concisely and helpfully. Keep your answer natural and relevant.

=== RECENT CONVERSATION HISTORY ===
{conv_history_str}

=== USER MESSAGE ===
{message}
"""
            models_to_try = [self.writer.model_name]
            for fallback_m in [
                "google_genai:gemini-2.5-flash-lite",
                "ollama:gemma4:e2b",
                "google_genai:gemini-3.8-flash",
                "google_genai:gemini-2.5-flash",
            ]:
                if fallback_m not in models_to_try:
                    models_to_try.append(fallback_m)

            for m_name in models_to_try:
                try:
                    model = init_chat_model(model=m_name, temperature=0.3, max_retries=1)
                    resp = model.invoke(conv_prompt)
                    raw = resp.content
                    if isinstance(raw, list):
                        raw = "".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in raw])
                    conv_reply = str(raw).strip()
                    if conv_reply:
                        latency_ms = int((time.time() - start_time) * 1000)
                        return {
                            "reply": conv_reply,
                            "draft_card": None,
                            "intent": intent.value,
                            "latency_ms": latency_ms,
                        }
                except Exception:
                    continue
        except Exception:
            pass

        # Handle general queries or overview
        try:
            recent_count = EmailService.count_emails()
        except Exception:
            recent_count = len(EmailService.list_emails(limit=100))

        try:
            pending_tasks = len(TaskService.list_tasks(status="pending"))
        except Exception:
            pending_tasks = 0

        reply_text = (
            f"Hello! I am your **PersonalMail AI** assistant.\n\n"
            f"📊 **Current Status:**\n"
            f"• Indexed Emails: **{recent_count}**\n"
            f"• Pending Tasks: **{pending_tasks}**\n\n"
            f"**You can ask me to:**\n"
            f"• *\"Summarize my important emails\"*\n"
            f"• *\"Reply to [sender] and confirm attendance\"*\n"
            f"• *\"Extract action items and deadlines\"*\n"
            f"• *\"Search for emails from Canara Bank\"*"
        )

        latency_ms = int((time.time() - start_time) * 1000)
        return {
            "reply": reply_text,
            "draft_card": None,
            "intent": intent.value,
            "latency_ms": latency_ms,
        }
