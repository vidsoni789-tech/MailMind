"""PersonalMail AI — Personalization & Edit-Learning Engine.

Analyzes differences between AI-generated drafts and user-edited versions to
extract durable writing style preferences (greetings, sign-offs, conciseness,
tone, avoided phrases, and preferred phrases) and persists them into SQLite.
"""

import difflib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from langmail.config import settings
from langmail.services.profile_service import ProfileService


class LearnedPreference(BaseModel):
    """Structured representation of a learned writing preference."""

    pref_type: str = Field(description="Type: greeting, signoff, conciseness, tone, avoid_phrase, preferred_phrase")
    value: str = Field(description="The preferred text or style value")
    contact_email: Optional[str] = Field(default=None, description="Contact-specific email, or None if global")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence score")
    evidence_count: int = Field(default=1, description="Number of times observed")
    reason: str = Field(default="", description="Explanation of why this preference was extracted")
    source: str = Field(default="user_edit", description="Source of learning: user_edit or manual")


@dataclass
class EditDiffResult:
    """Detailed textual and semantic diff between original and edited draft."""

    original_text: str
    edited_text: str
    diff_summary: str
    unified_diff: str
    original_words: int
    edited_words: int
    length_ratio: float
    original_greeting: Optional[str] = None
    edited_greeting: Optional[str] = None
    greeting_changed: bool = False
    original_signoff: Optional[str] = None
    edited_signoff: Optional[str] = None
    signoff_changed: bool = False
    removed_phrases: list[str] = field(default_factory=list)
    added_phrases: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Common Email Patterns & Heuristics
# ---------------------------------------------------------------------------

GREETING_REGEX = re.compile(
    r"^(?:Dear\s+[^,\n]+|Hi\s+[^,\n]+|Hello\s+[^,\n]+|Hey\s+[^,\n]+|Cheers\s+[^,\n]+|Howdy\s+[^,\n]+|Yo\s+[^,\n]+|Hiya\s+[^,\n]+|Good\s+(?:morning|afternoon|evening)[^,\n]*|Greetings)[,\n]?",
    re.IGNORECASE,
)

SIGNOFF_REGEX = re.compile(
    r"(?:Best\s+regards|Kind\s+regards|Warm\s+regards|Warmly|Regards|Best|Thanks\s+again|Thanks|Thank\s+you|Cheers|Sincerely|Yours\s+truly|Your\s+truly|Respectfully)[,\n]?",
    re.IGNORECASE,
)

COMMON_FILLER_PHRASES = [
    "I hope this email finds you well",
    "I hope you are doing well",
    "I hope you're doing well",
    "Please feel free to reach out",
    "Please do not hesitate to reach out",
    "Don't hesitate to reach out",
    "Let me know if you have any questions",
    "Per my previous email",
    "As per our conversation",
    "Just wanted to touch base",
    "Just following up on",
    "At your earliest convenience",
    "Kindly be advised that",
    "Please find attached herewith",
]


def extract_greeting(text: str) -> Optional[str]:
    """Extract greeting line or prefix from the beginning of an email text."""
    if not text:
        return None
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    if not lines:
        return None
    first_line = lines[0]
    match = GREETING_REGEX.match(first_line)
    if match:
        return match.group(0).rstrip(",:").strip()

    # Generic greeting heuristic: first line ending with comma/colon and short word count (<= 6 words)
    words = first_line.split()
    if 1 <= len(words) <= 6 and (first_line.endswith(",") or first_line.endswith(":")):
        return first_line.rstrip(",:").strip()

    return None


def extract_signoff(text: str) -> Optional[str]:
    """Extract sign-off phrase from the end of an email text."""
    if not text:
        return None
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    if len(lines) <= 1:
        return None
    # Exclude the first line (which is the greeting line!)
    candidate_lines = lines[1:]
    for line in reversed(candidate_lines[-2:]):
        match = SIGNOFF_REGEX.search(line)
        if match:
            return match.group(0).rstrip(",:").strip()
    return None



def compute_edit_diff(original_text: str, edited_text: str) -> EditDiffResult:
    """Compute rich structural and semantic diff between original and edited draft."""
    orig_clean = original_text.strip()
    edit_clean = edited_text.strip()

    orig_lines = orig_clean.splitlines(keepends=True)
    edit_lines = edit_clean.splitlines(keepends=True)

    diff_lines = list(
        difflib.unified_diff(
            orig_lines,
            edit_lines,
            fromfile="original_draft",
            tofile="edited_draft",
            lineterm="",
        )
    )
    unified_diff_str = "\n".join(diff_lines)

    orig_words = len(orig_clean.split())
    edit_words = len(edit_clean.split())
    length_ratio = (edit_words / orig_words) if orig_words > 0 else 1.0

    orig_greeting = extract_greeting(orig_clean)
    edit_greeting = extract_greeting(edit_clean)
    greeting_changed = bool(
        (orig_greeting or edit_greeting)
        and (orig_greeting or "").lower() != (edit_greeting or "").lower()
    )

    orig_signoff = extract_signoff(orig_clean)
    edit_signoff = extract_signoff(edit_clean)
    signoff_changed = bool(
        (orig_signoff or edit_signoff)
        and (orig_signoff or "").lower() != (edit_signoff or "").lower()
    )

    # Check common filler phrases removed
    removed_fillers: list[str] = []
    for filler in COMMON_FILLER_PHRASES:
        if re.search(r"\b" + re.escape(filler) + r"\b", orig_clean, re.IGNORECASE):
            if not re.search(r"\b" + re.escape(filler) + r"\b", edit_clean, re.IGNORECASE):
                removed_fillers.append(filler)

    # Build human-readable summary
    summary_parts = []
    if greeting_changed:
        summary_parts.append(
            f"Greeting changed from '{orig_greeting or 'none'}' to '{edit_greeting or 'none'}'"
        )
    if signoff_changed:
        summary_parts.append(
            f"Sign-off changed from '{orig_signoff or 'none'}' to '{edit_signoff or 'none'}'"
        )
    if length_ratio <= 0.7:
        pct = int((1.0 - length_ratio) * 100)
        summary_parts.append(f"Shortened body by ~{pct}%")
    elif length_ratio >= 1.35:
        pct = int((length_ratio - 1.0) * 100)
        summary_parts.append(f"Expanded body by ~{pct}%")

    if removed_fillers:
        summary_parts.append(f"Removed filler phrase(s): {', '.join(f'\"{f}\"' for f in removed_fillers)}")

    if not summary_parts:
        summary_parts.append("Minor textual refinements and wording adjustments")

    diff_summary = "; ".join(summary_parts)

    return EditDiffResult(
        original_text=orig_clean,
        edited_text=edit_clean,
        diff_summary=diff_summary,
        unified_diff=unified_diff_str,
        original_words=orig_words,
        edited_words=edit_words,
        length_ratio=length_ratio,
        original_greeting=orig_greeting,
        edited_greeting=edit_greeting,
        greeting_changed=greeting_changed,
        original_signoff=orig_signoff,
        edited_signoff=edit_signoff,
        signoff_changed=signoff_changed,
        removed_phrases=removed_fillers,
    )


# ---------------------------------------------------------------------------
# Learning Agent
# ---------------------------------------------------------------------------

class LearningAgent:
    """Agent that extracts durable writing preferences from user edits."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.model

    def analyze_edit(
        self,
        original_text: str,
        edited_text: str,
        contact_email: Optional[str] = None,
    ) -> list[LearnedPreference]:
        """Analyze differences between original and edited draft to extract style preferences."""
        if not original_text or not edited_text or original_text.strip() == edited_text.strip():
            return []

        diff = compute_edit_diff(original_text, edited_text)
        preferences: list[LearnedPreference] = []

        # 1. Greeting Preference
        if diff.greeting_changed and diff.edited_greeting:
            # Normalize greeting prefix (e.g. "Hi Alex" -> "Hi", "Dear Dr. Adams" -> "Dear Dr.")
            val = diff.edited_greeting.strip()
            m = re.match(
                r"^(Dear\s+Dr\.|Dear\s+Professor|Dear|Hi|Hello|Hey|Cheers|Howdy|Yo|Good\s+\w+)",
                val,
                re.IGNORECASE,
            )
            if m:
                pref_val = m.group(0)
            else:
                words = val.split()
                pref_val = words[0] if words else val

            preferences.append(
                LearnedPreference(
                    pref_type="greeting",
                    value=pref_val,
                    contact_email=contact_email,
                    confidence=0.85,
                    reason=f"User replaced greeting '{diff.original_greeting}' with '{pref_val}'",
                )
            )

        # 2. Sign-off Preference
        if diff.signoff_changed and diff.edited_signoff:
            preferences.append(
                LearnedPreference(
                    pref_type="signoff",
                    value=diff.edited_signoff.strip(),
                    contact_email=contact_email,
                    confidence=0.85,
                    reason=f"User replaced sign-off '{diff.original_signoff}' with '{diff.edited_signoff}'",
                )
            )

        # 3. Conciseness / Length Preference
        if diff.length_ratio <= 0.65:
            preferences.append(
                LearnedPreference(
                    pref_type="conciseness",
                    value="concise",
                    contact_email=contact_email,
                    confidence=0.80,
                    reason=f"User shortened draft by {int((1.0 - diff.length_ratio) * 100)}%",
                )
            )
        elif diff.length_ratio >= 1.4:
            preferences.append(
                LearnedPreference(
                    pref_type="length",
                    value="detailed",
                    contact_email=contact_email,
                    confidence=0.75,
                    reason=f"User expanded draft by {int((diff.length_ratio - 1.0) * 100)}%",
                )
            )

        # 4. Bullet Points / Formatting Preference
        has_bullets_in_edit = bool(re.search(r"^\s*[-*•]\s+", diff.edited_text, re.MULTILINE))
        has_bullets_in_orig = bool(re.search(r"^\s*[-*•]\s+", diff.original_text, re.MULTILINE))
        if has_bullets_in_edit and not has_bullets_in_orig:
            preferences.append(
                LearnedPreference(
                    pref_type="formatting",
                    value="bullet_points",
                    contact_email=contact_email,
                    confidence=0.80,
                    reason="User formatted content using bullet points",
                )
            )

        # 5. Avoided Phrases (Removed Fillers)
        for filler in diff.removed_phrases:
            preferences.append(
                LearnedPreference(
                    pref_type="avoid_phrase",
                    value=filler,
                    contact_email=contact_email,
                    confidence=0.90,
                    reason=f"User deleted common filler phrase '{filler}'",
                )
            )

        # 6. Tone Inference
        orig_lower = diff.original_text.lower()
        edit_lower = diff.edited_text.lower()
        formal_markers = ["sincerely", "regards", "dear", "inquire", "confirming", "cordially"]
        casual_markers = ["hey", "cheers", "thanks!", "awesome", "sounds good"]

        orig_formal = sum(1 for m in formal_markers if m in orig_lower)
        orig_casual = sum(1 for m in casual_markers if m in orig_lower)
        edit_formal = sum(1 for m in formal_markers if m in edit_lower)
        edit_casual = sum(1 for m in casual_markers if m in edit_lower)

        if edit_formal > orig_formal and edit_formal >= 2:
            preferences.append(
                LearnedPreference(
                    pref_type="tone",
                    value="formal",
                    contact_email=contact_email,
                    confidence=0.75,
                    reason="User added formal language markers",
                )
            )
        elif edit_casual > orig_casual and edit_casual >= 1:
            preferences.append(
                LearnedPreference(
                    pref_type="tone",
                    value="casual",
                    contact_email=contact_email,
                    confidence=0.75,
                    reason="User introduced casual/friendly tone markers",
                )
            )

        return preferences

    def learn_from_edit(
        self,
        original_text: str,
        edited_text: str,
        contact_email: Optional[str] = None,
        draft_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Extract durable style preferences from an edit and persist them in the database."""
        extracted = self.analyze_edit(
            original_text=original_text,
            edited_text=edited_text,
            contact_email=contact_email,
        )

        persisted: list[dict[str, Any]] = []
        for pref in extracted:
            saved = ProfileService.add_preference(
                pref_type=pref.pref_type,
                value=pref.value,
                contact_email=pref.contact_email,
                confidence=pref.confidence,
                source=pref.source,
            )
            persisted.append(saved)

        return persisted
