"""PersonalMail AI — Pre-Send Quality and Safety Checker Agent.

Implements automated pre-dispatch checks to catch common email errors:
- Missing attachments (mentions 'attached', 'resume', 'report' but no file attached)
- Recipient name mismatch (greeting addresses 'John' but recipient email is 'alex@...')
- Sensitive data leaks (API keys, passwords, private keys, bearer tokens)
- Tone / Formality mismatches (unprofessional slang, profanity)
- Thread contradictions (contradicting commitments made in conversation)
- Empty / near-empty body and missing recipient

Assigns graded severities:
- INFO: Informational style suggestions (does not prevent sending).
- WARNING: Highlighted alert in draft card (user can choose to proceed).
- BLOCK: Serious error like missing recipient or sensitive secret (disables send).
"""

import json
import re
from typing import Any, Optional, Union

from langchain.chat_models import init_chat_model

from langmail.config import settings
from langmail.models.agent_schemas import (
    DraftProposal,
    QualityCheckItem,
    QualityCheckResult,
)


# ---------------------------------------------------------------------------
# Rule Regex Patterns
# ---------------------------------------------------------------------------

SENSITIVE_PATTERNS = [
    (r"\bsk-ant-[a-zA-Z0-9_\-]{20,}\b", "Anthropic API Key"),
    (r"\bsk-[a-zA-Z0-9_\-]{20,}\b", "OpenAI / API Secret Key"),
    (r"\bAIza[0-9A-Za-z\-_]{35}\b", "Google API Key"),
    (r"\b(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b", "AWS Access Key"),
    (r"-----BEGIN (?:RSA|OPENSSH|DSA|EC)?\s*PRIVATE KEY-----", "Private Key Header"),
    (r"\bBearer\s+[a-zA-Z0-9_\-\.]{25,}\b", "Bearer Auth Token"),
    (r"(?i)\b(?:password|passwd|pwd|secret_key|api_key)\s*[:=]\s*['\"]?([^\s'\"]{5,})", "Plaintext Password/Secret"),
]

ATTACHMENT_KEYWORDS = [
    r"\b(?:i(?:'ve| have)? attached|attached is|find attached|please find attached|see attached)\b",
    r"\b(?:attaching the|attached my|attached the|as attached)\b",
    r"\b(?:find my resume|attached resume|find the report|attached report|attached deck|attached presentation|attached document|attached invoice|attached file)\b",
    r"\b(?:attached|attaching)\b",
]

VULGAR_WORDS = [
    r"\b(?:wtf|fuck|shit|damn|ass|bitch|bastard)\b"
]

SLANG_WORDS = [
    r"\b(?:lmao|rofl|omg|idk|tbh|dunno|gonna|wanna|yo|sup)\b"
]

GREETING_REGEX = re.compile(
    r"(?i)^\s*(?:dear|hi|hello|hey|good\s+(?:morning|afternoon|evening))\s+(?:(?:dr|prof|professor|mr|mrs|ms)\.?\s+)?([a-zA-Z]+)",
    re.MULTILINE,
)

GENERIC_GREETINGS = {
    "all", "team", "everyone", "there", "colleagues", "colleague",
    "friends", "friend", "sir", "madam", "folks", "both",
    "dr", "prof", "professor", "mr", "mrs", "ms"
}

ROLE_EMAIL_PREFIXES = {
    "mentor", "support", "info", "contact", "admin", "advising", "office",
    "team", "help", "sales", "jobs", "careers", "recruiting", "talent"
}

THREAD_NEGATIVE_TERMS = [
    "not available", "cannot attend", "unable to meet", "decline",
    "can't make it", "canceled", "cancelled", "unavailable", "won't be able"
]

DRAFT_POSITIVE_ACCEPT = [
    "confirmed for", "see you at", "confirming our meeting", "happy to attend",
    "looking forward to meeting", "will be there", "glad to confirm"
]


class QualityChecker:
    """Automated pre-send quality and safety checker."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.model

    def check(
        self,
        draft: Union[DraftProposal, dict[str, Any]],
        thread_context: Optional[str] = None,
        recipient_name: Optional[str] = None,
        attached_files: Optional[list[str]] = None,
        use_llm: bool = False,
    ) -> QualityCheckResult:
        """Run all rule-based and optional LLM quality checks on a draft."""
        # Normalize draft inputs
        if isinstance(draft, DraftProposal):
            to_email = draft.to_email or ""
            subject = draft.subject or ""
            body = draft.body or ""
            attachment_requests = draft.attachment_requests or []
        else:
            to_email = draft.get("to_email") or ""
            subject = draft.get("subject") or ""
            body = draft.get("body") or ""
            attachment_requests = draft.get("attachment_requests") or []

        attached = attached_files or []
        checks: list[QualityCheckItem] = []

        # 1. EMPTY / NEAR-EMPTY BODY CHECK (BLOCK)
        body_stripped = body.strip()
        if not body_stripped:
            checks.append(QualityCheckItem(
                code="EMPTY_BODY",
                severity="BLOCK",
                message="Email body is completely empty."
            ))
        elif len(body_stripped) < 5:
            checks.append(QualityCheckItem(
                code="EMPTY_BODY",
                severity="BLOCK",
                message="Email body is too short (must be at least 5 characters)."
            ))

        # 2. RECIPIENT VALIDATION (BLOCK)
        to_email_stripped = to_email.strip()
        if not to_email_stripped:
            checks.append(QualityCheckItem(
                code="MISSING_RECIPIENT",
                severity="BLOCK",
                message="Recipient email address is required before sending."
            ))
        elif "@" not in to_email_stripped or "." not in to_email_stripped.split("@")[-1]:
            checks.append(QualityCheckItem(
                code="INVALID_RECIPIENT",
                severity="BLOCK",
                message=f"Recipient email '{to_email_stripped}' is invalid."
            ))
        else:
            # Check for common domain typos (e.g., gmai.com -> gmail.com)
            domain = to_email_stripped.split("@")[-1].lower()
            common_typos = {
                "gmai.com": "gmail.com",
                "gamil.com": "gmail.com",
                "gmial.com": "gmail.com",
                "gmaill.com": "gmail.com",
                "gmai.co": "gmail.com",
                "yaho.com": "yahoo.com",
                "yahooo.com": "yahoo.com",
                "hotmial.com": "hotmail.com",
                "hotmaill.com": "hotmail.com",
                "outlok.com": "outlook.com",
                "outloo.com": "outlook.com",
                "icld.com": "icloud.com",
            }
            if domain in common_typos:
                checks.append(QualityCheckItem(
                    code="DOMAIN_TYPO",
                    severity="WARNING",
                    message=f"Recipient domain '{domain}' appears to be a typo for '{common_typos[domain]}'. Please verify before sending."
                ))

        # 3. SENSITIVE DATA DETECTION (BLOCK)
        for pattern, label in SENSITIVE_PATTERNS:
            match = re.search(pattern, body)
            if match:
                checks.append(QualityCheckItem(
                    code="SENSITIVE_DATA",
                    severity="BLOCK",
                    message=f"Potential sensitive data leak detected ({label}). Remove credentials before sending."
                ))
                break

        # 4. MISSING ATTACHMENT CHECK (WARNING)
        # If no files attached, check if body or attachment_requests mentions attachments
        if not attached:
            detected_attachment_mention = False
            mention_matched = ""
            for pat in ATTACHMENT_KEYWORDS:
                m = re.search(pat, body, re.IGNORECASE)
                if m:
                    detected_attachment_mention = True
                    mention_matched = m.group(0)
                    break

            if detected_attachment_mention or attachment_requests:
                msg = (
                    f"Draft mentions an attachment ('{mention_matched or attachment_requests[0]}'), "
                    "but no file is selected or attached."
                )
                checks.append(QualityCheckItem(
                    code="MISSING_ATTACHMENT",
                    severity="WARNING",
                    message=msg
                ))

        # 5. RECIPIENT NAME MISMATCH (WARNING)
        if to_email_stripped and "@" in to_email_stripped:
            greet_match = GREETING_REGEX.search(body)
            if greet_match:
                greet_name = greet_match.group(1).strip()
                greet_name_lower = greet_name.lower()

                if greet_name_lower not in GENERIC_GREETINGS:
                    local_part = to_email_stripped.split("@")[0].lower()
                    # Do not flag role-based contact accounts like mentor@, support@, info@
                    if local_part not in ROLE_EMAIL_PREFIXES:
                        matches_local = greet_name_lower in local_part
                        matches_recipient = (
                            recipient_name is not None and
                            greet_name_lower in recipient_name.lower()
                        )

                        if not matches_local and not matches_recipient:
                            checks.append(QualityCheckItem(
                                code="RECIPIENT_MISMATCH",
                                severity="WARNING",
                                message=(
                                    f"Greeting addresses '{greet_name.capitalize()}', but the recipient "
                                    f"appears to be '{to_email_stripped}'."
                                )
                            ))

        # 6. SUBJECT EMPTY (WARNING)
        if not subject.strip():
            checks.append(QualityCheckItem(
                code="SUBJECT_EMPTY",
                severity="WARNING",
                message="Subject line is empty. Adding a descriptive subject improves response rates."
            ))

        # 7. TONE / FORMALITY CHECK (WARNING / INFO)
        has_vulgar = False
        for pat in VULGAR_WORDS:
            v_match = re.search(pat, body, re.IGNORECASE)
            if v_match:
                has_vulgar = True
                checks.append(QualityCheckItem(
                    code="TONE_MISMATCH",
                    severity="WARNING",
                    message=f"Inappropriate or vulgar language detected ('{v_match.group(0)}')."
                ))
                break

        if not has_vulgar:
            for pat in SLANG_WORDS:
                s_match = re.search(pat, body, re.IGNORECASE)
                if s_match:
                    checks.append(QualityCheckItem(
                        code="TONE_MISMATCH",
                        severity="INFO",
                        message=f"Informal slang detected ('{s_match.group(0)}'); consider a more polished phrasing for professional communication."
                    ))
                    break

        # 8. THREAD CONTRADICTION (WARNING)
        if thread_context:
            tc_lower = thread_context.lower()
            body_lower = body.lower()
            # If thread says user or sender is unavailable, but draft accepts
            thread_declines = any(neg in tc_lower for neg in THREAD_NEGATIVE_TERMS)
            draft_accepts = any(pos in body_lower for pos in DRAFT_POSITIVE_ACCEPT)
            if thread_declines and draft_accepts:
                checks.append(QualityCheckItem(
                    code="THREAD_CONTRADICTION",
                    severity="WARNING",
                    message="Draft appears to confirm or accept a meeting despite prior cancellation/unavailability in the thread."
                ))

        # 9. UNRESOLVED PLACEHOLDER DETECTION (WARNING)
        placeholder_matches = re.findall(
            r"\[(?:your\s+[a-z_\s]+|insert\s+[^\]]+|name|company|recipient|date|time|phone|link|signature|position|title)\]|"
            r"\[(?:Your\s+[A-Za-z\s]+|Insert\s+[^\]]+|Name|Company|Date|Time|Phone|Link)\]|"
            r"<insert\s+[^>]+>",
            body,
            re.IGNORECASE,
        )
        if not placeholder_matches:
            generic_brackets = re.findall(r"\[([A-Z][a-zA-Z0-9_\s]{1,30})\]", body)
            if generic_brackets:
                placeholder_matches = [f"[{g}]" for g in generic_brackets]

        if placeholder_matches:
            unique_ph = list(dict.fromkeys(placeholder_matches))
            checks.append(QualityCheckItem(
                code="UNRESOLVED_PLACEHOLDER",
                severity="WARNING",
                message=f"Draft contains unfilled placeholder(s): {', '.join(unique_ph)}. Please replace with your actual details before sending."
            ))

        # 10. OPTIONAL LLM CHECK
        if use_llm and thread_context and len(body_stripped) > 10:
            llm_checks = self._run_llm_quality_check(body, subject, to_email, thread_context)
            for item in llm_checks:
                # Avoid duplicate codes
                if not any(c.code == item.code for c in checks):
                    checks.append(item)

        # Compute overall status
        status = "PASS"
        if any(c.severity == "BLOCK" for c in checks):
            status = "BLOCK"
        elif any(c.severity == "WARNING" for c in checks):
            status = "WARNING"
        elif any(c.severity == "INFO" for c in checks):
            status = "INFO"

        return QualityCheckResult(status=status, checks=checks)

    def _run_llm_quality_check(
        self, body: str, subject: str, to_email: str, thread_context: str
    ) -> list[QualityCheckItem]:
        """Query LLM for deep factual consistency and tone nuances."""
        prompt = f"""You are a Pre-Send Email Quality & Safety Assessor.
Analyze this email draft against the thread context for serious factual errors, contradictions, or inappropriate tone.

=== THREAD CONTEXT ===
{thread_context}

=== DRAFT DETAILS ===
To: {to_email}
Subject: {subject}
Body:
{body}

=== INSTRUCTIONS ===
Identify any:
1. Direct factual contradictions with the thread.
2. Unwarranted commitments or unsubstantiated claims.

If everything is sound, return an empty checks array.
Respond ONLY with valid JSON:
{{
  "checks": [
    {{
      "code": "CONTRADICTION | UNSUPPORTED_CLAIM",
      "severity": "WARNING | INFO",
      "message": "Clear description of the issue"
    }}
  ]
}}
"""
        models_to_try = [self.model_name]
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
                model = init_chat_model(model=m_name, temperature=0.0, max_retries=1)
                resp = model.invoke(prompt)
                raw = resp.content
                if isinstance(raw, list):
                    raw = "".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in raw])
                raw = str(raw).strip()
                match = re.search(r"\{.*\}", raw, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    items = []
                    for c in data.get("checks", []):
                        items.append(QualityCheckItem(
                            code=c.get("code", "QUALITY_ISSUE"),
                            severity=c.get("severity", "WARNING").upper(),
                            message=c.get("message", "Quality issue detected"),
                        ))
                    return items
            except Exception:
                continue

        return []
