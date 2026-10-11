"""PersonalMail AI — Intent Router Agent.

Classifies incoming user messages into structured IntentResult objects
as defined in new_update/agents.md:
- SEARCH
- SUMMARIZE
- CLASSIFY
- REPLY
- IMPROVE
- REGENERATE
- FORWARD
- SEND
- FIND_ATTACHMENT
- TASKS
- HISTORY
- PROFILE
- GENERAL_CHAT
"""

import json
import re
from typing import Optional
from langchain.chat_models import init_chat_model

from langmail.config import settings
from langmail.models.agent_schemas import IntentResult, IntentType


ROUTER_PROMPT = """You are the Intent Router for PersonalMail AI.
Classify the user's intent into exactly ONE of the following intent types:

- SEARCH: User wants to search for specific emails, senders, or past messages.
- SUMMARIZE: User wants an email or thread summarized, or an overview of emails.
- CLASSIFY: User wants to triage, classify, or inspect unread/important status.
- REPLY: User wants to write, draft, compose, or send an email to someone.
- IMPROVE: User wants to rewrite, polish, shorten, or make a draft more formal/friendly.
- FORWARD: User wants to forward an email.
- SEND: User asks to dispatch an existing approved draft or message.
- TASKS: User wants to extract action items, deadlines, to-dos, or pending tasks.
- FIND_ATTACHMENT: User asks about attachments or files (resumes, reports).
- HISTORY: User wants to view audit logs or activity history.
- PROFILE: User wants to check or update user profile, bio, or settings.
- GENERAL_CHAT: General greeting or question about capabilities.

Return JSON ONLY with this exact structure:
{{
  "intent": "REPLY",
  "confidence": 0.95,
  "explanation": "User asked to reply to an email"
}}

User message: {message}
Active thread ID context: {thread_id}
"""


def _fast_heuristic_classifier(message: str, thread_id: Optional[str] = None) -> Optional[IntentResult]:
    """Instant heuristic matching for common user commands to minimize LLM latency and quota."""
    lowered = message.strip().lower()

    # Reply / Compose / Send Email to Recipient
    compose_phrases = [
        "reply to", "reply back", "draft a reply", "write a reply", "send a reply", "respond to",
        "compose", "write an email to", "draft an email to", "write to", "write email to",
        "write a mail to", "write mail to", "send a mail to", "send an email to",
        "send email to", "send mail to", "mail to", "email to", "send message to",
        "send a message to", "send a draft to", "draft to"
    ]
    if any(k in lowered for k in compose_phrases):
        return IntentResult(
            intent=IntentType.REPLY,
            confidence=0.99,
            target_thread_id=thread_id,
            explanation="Explicit email compose or send instruction detected",
        )

    # Check if message contains an explicit email address and compose intent
    if "@" in lowered and re.search(r"[\w\.-]+@[\w\.-]+\.\w+", lowered):
        if any(w in lowered for w in ["send", "write", "mail", "email", "tell", "saying", "meet", "draft"]):
            return IntentResult(
                intent=IntentType.REPLY,
                confidence=0.99,
                target_thread_id=thread_id,
                explanation="Recipient email address with message content detected",
            )

    # Improve draft
    if any(k in lowered for k in ["formal", "friendly", "concise", "shorter", "longer", "improve", "rewrite", "polish"]):
        return IntentResult(
            intent=IntentType.IMPROVE,
            confidence=0.95,
            target_thread_id=thread_id,
            explanation="Draft improvement command detected",
        )

    # Tasks / Deadlines
    if any(k in lowered for k in ["extract tasks", "extract action items", "what are my deadlines", "any deadlines", "to-do", "todo", "action items"]):
        return IntentResult(
            intent=IntentType.TASKS,
            confidence=0.98,
            target_thread_id=thread_id,
            explanation="Task / deadline extraction command detected",
        )

    # Summarize
    if any(k in lowered for k in ["summarize", "summary of", "what is this email about", "tldr", "overview of my emails"]):
        return IntentResult(
            intent=IntentType.SUMMARIZE,
            confidence=0.98,
            target_thread_id=thread_id,
            explanation="Summarize command detected",
        )

    # Search
    if any(k in lowered for k in ["search for", "find emails", "look for email", "show emails from", "find message"]):
        return IntentResult(
            intent=IntentType.SEARCH,
            confidence=0.95,
            target_thread_id=thread_id,
            explanation="Search command detected",
        )

    # Triage / Classify
    if any(k in lowered for k in ["triage", "which emails need reply", "important emails", "check priority", "classify"]):
        return IntentResult(
            intent=IntentType.CLASSIFY,
            confidence=0.92,
            target_thread_id=thread_id,
            explanation="Classification / triage command detected",
        )

    # Attachment search
    if any(k in lowered for k in ["find attachment", "find my", "search files", "suggest attachment", "attach my", "attach file", "find document", "find resume", "find report"]):
        return IntentResult(
            intent=IntentType.FIND_ATTACHMENT,
            confidence=0.98,
            target_thread_id=thread_id,
            explanation="Attachment search command detected",
        )

    # Greetings
    if re.search(r"\b(hi|hello|hey|help|who are you|what can you do)\b", lowered):
        return IntentResult(
            intent=IntentType.GENERAL_CHAT,
            confidence=1.0,
            target_thread_id=thread_id,
            explanation="General chat greeting",
        )

    return None


class IntentRouter:
    """Agent that classifies user intentions using fast heuristics with LLM fallback."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.model

    def classify(self, message: str, thread_id: Optional[str] = None) -> IntentResult:
        """Route message to structured IntentResult."""
        # 1. Fast heuristics
        fast_result = _fast_heuristic_classifier(message, thread_id)
        if fast_result:
            return fast_result

        # 2. LLM fallback classifier
        try:
            model = init_chat_model(model=self.model_name, temperature=0.0)
            prompt = ROUTER_PROMPT.format(
                message=message,
                thread_id=thread_id or "none",
            )
            resp = model.invoke(prompt)
            content = resp.content

            if isinstance(content, list):
                content = "".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in content])
            content = str(content).strip()

            # Extract JSON block
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                intent_str = parsed.get("intent", "GENERAL_CHAT").upper()
                try:
                    intent_type = IntentType(intent_str)
                except ValueError:
                    intent_type = IntentType.GENERAL_CHAT

                return IntentResult(
                    intent=intent_type,
                    confidence=float(parsed.get("confidence", 0.85)),
                    target_thread_id=thread_id,
                    explanation=parsed.get("explanation"),
                )
        except Exception:
            pass

        # Default fallback
        return IntentResult(
            intent=IntentType.GENERAL_CHAT,
            confidence=0.5,
            target_thread_id=thread_id,
            explanation="Fallback to general assistant",
        )
