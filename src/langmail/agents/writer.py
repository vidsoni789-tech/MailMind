"""PersonalMail AI — Reply & Compose Writer Agent.

Writes context-aware email replies and fresh compositions by assembling:
- Thread context / received email
- Recipient and contact profile
- User profile (signature, role, tone)
- Learned style preferences
Produces structured DraftProposal and records the draft in SQLite.
"""

import json
import logging
import re
from typing import Any, Optional
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

from langmail.config import settings
from langmail.models.agent_schemas import DraftProposal
from langmail.prompts.templates import DRAFT_WRITER_SYSTEM
from langmail.services import DraftService, ProfileService
from langmail.state import GmailAgentState
from langmail.tools.db_tools import (
    db_get_sent_snippets,
    db_get_thread_summaries,
    db_lookup_contact,
)
from langmail.tools.gmail_tools import gmail_create_draft, gmail_read_thread


WRITER_LLM_PROMPT = """You are the Reply & Compose Writer for PersonalMail AI.
Your job is to write a high quality, context-aware email draft based on the user's instructions and recent conversation context.

=== RECENT CONVERSATION HISTORY ===
{conversation_history}

=== CURRENT USER INSTRUCTION ===
{instruction}

=== PREVIOUS DRAFT (IF REVISING / UPDATING) ===
{active_draft_context}

=== EMAIL THREAD CONTEXT ===
{thread_context}

=== SENDER & RECIPIENT DETAILS ===
Target Recipient: {recipient}
User Tone Preference: {tone}
User Signature / Signoff: {signature}

=== LEARNED USER STYLE DIRECTIVES ===
{learned_style}

=== HARD RULES ===
1. Address exactly what the user asked for across the conversation history.
2. If the user is correcting an email address, revising, or following up on a previous draft or instruction, retain the core message/body and apply the requested change.
3. Never invent fake commitments, meetings, or attachment files.
4. Be concise and natural — avoid corporate fluff.
5. If the User Signature / Signoff already includes a closing like "Your Truly", "Yours truly", "Sincerely", or "Best regards", do NOT write another closing like "Best," or "Regards," before it.
6. If any documents or files to attach are mentioned (like resume, contract, report, oslab4, specific file names, etc.), list ALL of them in the attachment_requests array.
7. Strictly adhere to learned user style directives (use preferred greeting and signoff, avoid specified phrases).

Respond ONLY with valid JSON using this exact schema:
{{
  "to_email": "recipient email address",
  "subject": "Clear email subject",
  "body": "Complete email body including greeting and sign-off",
  "tone": "professional | friendly | formal | concise",
  "confidence": 0.95,
  "attachment_requests": ["any mentioned documents or filenames, e.g. 'resume', 'oslab4'"]
}}
"""


IMPROVE_LLM_PROMPT = """You are the Email Polisher & Rewriter for PersonalMail AI.
Your job is to rewrite and polish an existing email draft according to the user's revision instruction and conversation context.

=== RECENT CONVERSATION HISTORY ===
{conversation_history}

=== ORIGINAL DRAFT BODY ===
{current_body}

=== USER REVISION INSTRUCTION ===
{instruction}

=== DETAILS ===
Target Recipient: {recipient}
Subject: {subject}
Desired Tone: {tone}
User Signature / Signoff: {signature}

=== LEARNED USER STYLE DIRECTIVES ===
{learned_style}

=== STRICT RULES ===
1. Keep the exact core meaning, facts, confirmations, and dates from the original draft.
2. Apply the requested revision (e.g. more formal, concise, friendly, warm, or fix grammar/recipient).
3. Do NOT repeat or include the user's revision instruction (e.g. never write "Rewrite this with a formal tone").
4. If the User Signature / Signoff already includes a closing like "Your Truly", "Yours truly", or "Best regards", do NOT add another closing before it.
5. Output the complete revised email text with greeting, revised body, and signoff.
6. Respect learned user style directives (greetings, signoffs, and avoided phrases).

Respond ONLY with valid JSON using this exact schema:
{{
  "to_email": "{recipient}",
  "subject": "{subject}",
  "body": "Complete rewritten email body",
  "tone": "formal | professional | friendly | concise",
  "confidence": 0.95
}}
"""


def _format_learned_style_directives(effective: dict[str, Any]) -> str:
    """Format effective learned style preferences into readable instructions for LLM."""
    lines = []
    if effective.get("greeting"):
        lines.append(f"- Preferred Greeting: \"{effective['greeting']}\"")
    if effective.get("signoff"):
        lines.append(f"- Preferred Sign-off: \"{effective['signoff']}\"")
    if effective.get("conciseness"):
        lines.append(f"- Conciseness / Length: {effective['conciseness']}")
    if effective.get("formatting"):
        lines.append(f"- Formatting preference: {effective['formatting']}")
    if effective.get("avoid_phrases"):
        lines.append(f"- Phrases to strictly avoid: {', '.join(f'\"{p}\"' for p in effective['avoid_phrases'])}")
    if effective.get("preferred_phrases"):
        lines.append(f"- Preferred phrases to include: {', '.join(f'\"{p}\"' for p in effective['preferred_phrases'])}")
    return "\n".join(lines) if lines else "No specific learned style preferences recorded yet; match standard tone."


def _clean_body_closing(body: str, signature: Optional[str] = None) -> str:
    """Remove redundant standalone closings (like 'Best,') immediately preceding user signature."""
    if not body:
        return body
    cleaned = body.strip()

    closing_phrases = ["your truly", "yours truly"]
    if signature:
        sig_first_line = signature.strip().splitlines()[0].strip().lower().rstrip(":,")
        if sig_first_line and any(sig_first_line.startswith(c) for c in [
            "your truly", "yours truly", "sincerely", "regards", "best regards", "warm regards", "warmly", "cheers", "thanks", "thank you"
        ]):
            closing_phrases.append(re.escape(sig_first_line))

    closing_pattern = "|".join(dict.fromkeys(closing_phrases))
    pat = rf"(?im)\n\s*(?:best|best regards|regards|kind regards|warm regards|with regards|sincerely|warmly),?\s*\n+(?=\s*(?:{closing_pattern})\b)"
    cleaned = re.sub(pat, "\n\n", cleaned)
    return cleaned.strip()



@tool(parse_docstring=True)
def think_draft(reflection: str) -> str:
    """Pause to reason about tone, content, and style before drafting.

    Args:
        reflection: Your analysis before writing the draft.
    """
    return f"Draft analysis recorded: {reflection}"


class ReplyWriter:
    """Agent that creates structured email drafts and records them in the database."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.model

    def improve_draft(
        self,
        instruction: str,
        current_body: str,
        recipient: Optional[str] = None,
        subject: Optional[str] = None,
        thread_id: Optional[str] = None,
        conversation_history: Optional[str] = None,
        persist: bool = True,
    ) -> DraftProposal:
        """Rewrite and improve an existing draft according to user instruction."""
        if not recipient:
            recip_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", instruction)
            if recip_match:
                recipient = recip_match.group(0)

        profile = ProfileService.get_profile()
        effective = ProfileService.get_effective_preferences(recipient)
        user_tone = effective.get("tone") or profile.get("default_tone", "professional")
        user_sig = profile.get("signature", "")
        learned_style = _format_learned_style_directives(effective)

        prompt = IMPROVE_LLM_PROMPT.format(
            conversation_history=conversation_history or "No previous conversation turns.",
            current_body=current_body,
            instruction=instruction,
            recipient=recipient or "",
            subject=subject or "Regarding your email",
            tone=user_tone,
            signature=user_sig or "(Standard polite closing with user's name)",
            learned_style=learned_style,
        )

        models_to_try = [self.model_name]
        if not self.model_name.startswith("nonexistent"):
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
                resp = model.invoke(prompt)
                raw = resp.content
                if isinstance(raw, list):
                    parts = [p.get("text", "") if isinstance(p, dict) else str(p) for p in raw]
                    raw = "".join(parts)
                raw = str(raw).strip()

                match = re.search(r"\{.*\}", raw, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    body = _clean_body_closing(data.get("body", "").strip(), user_sig)
                    if body:
                        target_recip = recipient or data.get("to_email", "")
                        if not target_recip or "@" not in target_recip:
                            email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", instruction)
                            if email_match:
                                target_recip = email_match.group(0)

                        proposal = DraftProposal(
                            to_email=target_recip or "",
                            subject=subject or data.get("subject", "Email Draft"),
                            body=body,
                            tone=data.get("tone", "formal" if "formal" in instruction.lower() else user_tone),
                            confidence=0.95,
                            attachment_requests=[],
                            thread_id=thread_id,
                        )
                        if persist:
                            record = DraftService.create_draft(
                                to_email=proposal.to_email,
                                subject=proposal.subject,
                                body=proposal.body,
                                thread_id=proposal.thread_id,
                            )
                            proposal.draft_id = record.get("id")
                        return proposal
            except Exception as e:
                logger.warning("Improve draft LLM attempt failed for %s: %s", m_name, e)
                continue

        # Rule-based polish fallback if all LLMs fail
        learned_greeting = effective.get("greeting") or "Hello"
        learned_signoff = effective.get("signoff") or "Best regards"
        avoid_phrases = effective.get("avoid_phrases") or []

        polished_body = current_body
        for avoid in avoid_phrases:
            polished_body = re.sub(r"\b" + re.escape(avoid) + r"\b[\.,]?", "", polished_body, flags=re.IGNORECASE).strip()

        if "formal" in instruction.lower():
            salutation = f"Dear Colleague" if not learned_greeting or learned_greeting.lower() in ("hey", "hello") else f"{learned_greeting}"
            closing = "Sincerely" if not learned_signoff or learned_signoff.lower() in ("cheers", "thanks") else learned_signoff
            polished_body = f"{salutation},\n\nI am writing to formally confirm that {polished_body.replace('Dear', '').replace('Hi', '').strip()}\n\n{closing},\n{user_sig or '[Your Name]'}"
        elif "concise" in instruction.lower() or "shorter" in instruction.lower() or effective.get("conciseness") == "concise":
            lines = [line.strip() for line in polished_body.splitlines() if line.strip()]
            polished_body = "\n\n".join(lines[:3])

        fallback_recip = recipient or ""
        if not fallback_recip or "@" not in fallback_recip:
            email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", instruction)
            if email_match:
                fallback_recip = email_match.group(0)

        fallback = DraftProposal(
            to_email=fallback_recip,
            subject=subject or "Regarding your email",
            body=polished_body,
            tone="formal" if "formal" in instruction.lower() else user_tone,
            confidence=0.8,
            attachment_requests=[],
            thread_id=thread_id,
        )
        if persist:
            record = DraftService.create_draft(
                to_email=fallback.to_email,
                subject=fallback.subject,
                body=fallback.body,
                thread_id=fallback.thread_id,
            )
            fallback.draft_id = record.get("id")
        return fallback

    def generate_draft(
        self,
        instruction: str,
        thread_context: Optional[str] = None,
        recipient: Optional[str] = None,
        thread_id: Optional[str] = None,
        subject: Optional[str] = None,
        conversation_history: Optional[str] = None,
        active_draft_context: Optional[str] = None,
        persist: bool = True,
    ) -> DraftProposal:
        """Generate a complete draft proposal and persist to database."""
        if not recipient:
            recip_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", instruction)
            if recip_match:
                recipient = recip_match.group(0)

        profile = ProfileService.get_profile()
        effective = ProfileService.get_effective_preferences(recipient)
        user_tone = effective.get("tone") or profile.get("default_tone", "professional")
        user_sig = profile.get("signature", "")
        learned_style = _format_learned_style_directives(effective)

        prompt = WRITER_LLM_PROMPT.format(
            conversation_history=conversation_history or "No previous conversation turns.",
            instruction=instruction,
            active_draft_context=active_draft_context or "No previous draft proposal.",
            thread_context=thread_context or "New email composition (no prior thread).",
            recipient=recipient or "Recipient",
            tone=user_tone,
            signature=user_sig or "(Use standard polite closing with user's name)",
            learned_style=learned_style,
        )

        # Multi-model candidate failover in case of quota exhaustion
        # Multi-model candidate failover in case of quota exhaustion or local offline
        models_to_try = [self.model_name]
        if not self.model_name.startswith("nonexistent"):
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
                resp = model.invoke(prompt)
                raw = resp.content
                if isinstance(raw, list):
                    parts = [p.get("text", "") if isinstance(p, dict) else str(p) for p in raw]
                    raw = "".join(parts)
                raw = str(raw).strip()

                match = re.search(r"\{.*\}", raw, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    to_email = data.get("to_email", recipient or "")
                    if not to_email or "@" not in to_email:
                        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", instruction)
                        if email_match:
                            to_email = email_match.group(0)

                    subj = subject or data.get("subject", "Email Draft")
                    body = _clean_body_closing(data.get("body", "").strip(), user_sig)

                    if body:
                        # Combine LLM attachment_requests with programmatic detection from instruction
                        from langmail.agents.attachment import AttachmentAgent
                        raw_att = data.get("attachment_requests", [])
                        if not isinstance(raw_att, list):
                            raw_att = [raw_att] if raw_att else []
                        detected_att = AttachmentAgent().detect_requested_documents(instruction)
                        merged_att = []
                        for item in raw_att + detected_att:
                            c_item = str(item).strip()
                            if c_item and c_item.lower() not in [x.lower() for x in merged_att]:
                                merged_att.append(c_item)

                        proposal = DraftProposal(
                            to_email=to_email or "",
                            subject=subj,
                            body=body,
                            tone=data.get("tone", user_tone),
                            confidence=float(data.get("confidence", 0.95)),
                            attachment_requests=merged_att,
                            thread_id=thread_id,
                        )

                        if persist:
                            draft_record = DraftService.create_draft(
                                to_email=proposal.to_email,
                                subject=proposal.subject,
                                body=proposal.body,
                                thread_id=proposal.thread_id,
                            )
                            proposal.draft_id = draft_record.get("id")

                        return proposal
            except Exception as e:
                logger.warning("Generate draft LLM attempt failed for %s: %s", m_name, e)
                continue

        # Smart clean message extraction if all LLM models fail
        fallback_to = recipient or ""
        if not fallback_to:
            email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", instruction)
            if email_match:
                fallback_to = email_match.group(0)

        cleaned_msg = instruction.strip()
        for prefix_pattern in [
            r"write\s+(?:an?\s+)?(?:email|mail|reply)\s+to\s+[\w\.-]+@[\w\.-]+\.\w+\s+(?:saying|that|asking)\s+",
            r"write\s+(?:an?\s+)?(?:email|mail|reply)\s+(?:saying|that|asking)\s+",
            r"send\s+(?:an?\s+)?(?:email|mail)\s+to\s+[\w\.-]+@[\w\.-]+\.\w+\s+(?:saying|that|asking)\s+",
            r"tell\s+them\s+(?:that\s+)?",
            r"(?:saying|that)\s+",
        ]:
            m = re.search(prefix_pattern, cleaned_msg, re.IGNORECASE)
            if m:
                cleaned_msg = cleaned_msg[m.end():].strip()
                break

        # Strip remaining connectors like "that ", "to ", "asking ", "saying "
        cleaned_msg = re.sub(r"^(?:that|to|asking|saying)\s+", "", cleaned_msg, flags=re.IGNORECASE).strip()

        if cleaned_msg:
            if re.match(r"^i\s+", cleaned_msg, re.IGNORECASE):
                cleaned_msg = "I " + cleaned_msg[2:]
            else:
                cleaned_msg = cleaned_msg[0].upper() + cleaned_msg[1:]

        # Transform raw user intent into courteous, natural email text
        lower_msg = cleaned_msg.lower()
        if active_draft_context and ("no previous draft proposal" not in active_draft_context.lower()):
            m_body = re.search(r"Body:\s*\n?(.*)", active_draft_context, re.DOTALL)
            m_subj = re.search(r"Subject:\s*(.*)", active_draft_context)
            if m_body and len(m_body.group(1).strip()) > 5 and len(cleaned_msg) < 30:
                body_content = m_body.group(1).strip()
                if m_subj and not subject:
                    subject = m_subj.group(1).strip()
            elif "not be able to meet" in lower_msg or "cannot meet" in lower_msg or "can't meet" in lower_msg:
                body_content = (
                    f"I am writing to let you know that I will not be able to meet tomorrow as planned.\n\n"
                    f"Please accept my apologies for any inconvenience, and please let me know if we can reschedule for another time that works for you."
                )
            elif lower_msg.startswith("i ") or lower_msg.startswith("we "):
                body_content = f"I am writing to let you know that {cleaned_msg[0].lower() + cleaned_msg[1:]}.\n\nPlease let me know if you need any further information."
            else:
                body_content = cleaned_msg
        elif "not be able to meet" in lower_msg or "cannot meet" in lower_msg or "can't meet" in lower_msg:
            body_content = (
                f"I am writing to let you know that I will not be able to meet tomorrow as planned.\n\n"
                f"Please accept my apologies for any inconvenience, and please let me know if we can reschedule for another time that works for you."
            )
        elif lower_msg.startswith("i ") or lower_msg.startswith("we "):
            body_content = f"I am writing to let you know that {cleaned_msg[0].lower() + cleaned_msg[1:]}.\n\nPlease let me know if you need any further information."
        else:
            body_content = cleaned_msg

        fallback_subj = subject
        if not fallback_subj:
            if "meet" in instruction.lower() or "meeting" in instruction.lower():
                fallback_subj = "Regarding our meeting"
            elif "interview" in instruction.lower():
                fallback_subj = "Regarding Interview"
            else:
                fallback_subj = "Regarding your email"

        # Apply learned style preferences in fallback generation
        learned_greeting = effective.get("greeting") or "Hello"
        learned_signoff = effective.get("signoff") or "Best regards"
        avoid_phrases = effective.get("avoid_phrases") or []

        # Remove any avoided phrases
        for avoid in avoid_phrases:
            body_content = re.sub(r"\b" + re.escape(avoid) + r"\b[\.,]?", "", body_content, flags=re.IGNORECASE).strip()

        # Conciseness preference
        if effective.get("conciseness") == "concise":
            lines = [l.strip() for l in body_content.splitlines() if l.strip()]
            body_content = "\n\n".join(lines[:2])

        greeting_prefix = f"{learned_greeting},"
        if user_sig:
            sig_lower = user_sig.strip().lower()
            starts_with_closing = any(
                sig_lower.startswith(prefix)
                for prefix in [
                    "your truly", "yours truly", "best regards", "warm regards",
                    "with regards", "sincerely", "regards", "best,", "cheers,", "warmly,"
                ]
            )
            if starts_with_closing:
                sign_off = f"\n\n{user_sig}"
            else:
                sign_off = f"\n\n{learned_signoff},\n{user_sig}"
        else:
            sign_off = f"\n\n{learned_signoff},"

        fallback_body = f"{greeting_prefix}\n\n{body_content}{sign_off}".strip()
        fallback_body = _clean_body_closing(fallback_body, user_sig)

        from langmail.agents.attachment import AttachmentAgent
        fallback_attachment_requests = AttachmentAgent().detect_requested_documents(instruction)

        fallback = DraftProposal(
            to_email=fallback_to,
            subject=fallback_subj,
            body=fallback_body,
            tone=user_tone,
            confidence=0.7,
            attachment_requests=fallback_attachment_requests,
            thread_id=thread_id,
        )
        if persist:
            record = DraftService.create_draft(
                to_email=fallback.to_email,
                subject=fallback.subject,
                body=fallback.body,
                thread_id=fallback.thread_id,
            )
            fallback.draft_id = record.get("id")
        return fallback



def create_draft_writer(model_name: str) -> object:
    """Build the Draft Writer sub-agent for backward compatibility.

    Args:
        model_name: Provider:model string.

    Returns:
        Compiled LangGraph agent ready to invoke.
    """
    model = init_chat_model(model=model_name, temperature=0.3)

    tools = [
        gmail_read_thread,
        db_lookup_contact,
        db_get_thread_summaries,
        db_get_sent_snippets,
        gmail_create_draft,
        think_draft,
    ]

    agent = create_agent(
        model,
        tools,
        system_prompt=DRAFT_WRITER_SYSTEM,
        state_schema=GmailAgentState,
    )

    return agent
