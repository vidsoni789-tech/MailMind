"""PersonalMail AI — Thread & Email Summarizer Agent.

Produces structured SummaryResult objects and caches summaries in local SQLite database.
"""

import json
import os
import re
from typing import Any, Optional
from langchain.chat_models import init_chat_model

from langmail.config import settings
from langmail.models.agent_schemas import SummaryResult
from langmail.services import EmailService
from langmail.storage.database import db_session


SUMMARIZER_PROMPT = """You are the Email Summarizer for PersonalMail AI.
Analyze the following email thread and produce a structured, high-value executive summary of what is inside the email.
Focus on the actual substance: the purpose of the email, key discussion points, important dates/times/locations, and what the sender is communicating. Do NOT output raw metadata headers.

=== EMAIL CONTENT ===
{content}

Respond ONLY with valid JSON using this exact schema:
{{
  "summary": "Clear, informative 2-3 sentence overview explaining the core topic and what is happening inside the email.",
  "decisions": ["Any explicit agreements or decisions reached (empty list if none)"],
  "requests": ["Any questions or requests asked by the sender (empty list if none)"],
  "deadlines": ["Any explicit dates, times, deadlines, or locations mentioned (e.g. 'Oct 11, 9 AM - 5 PM at IIIT Pune')"],
  "next_steps": ["Recommended action items or next steps"]
}}
"""


class EmailSummarizer:
    """Agent that produces structured summaries of email threads and persists them."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.summarization_model

    def summarize(self, content: str, thread_id: Optional[str] = None) -> SummaryResult:
        """Generate structured summary and optionally persist to SQLite."""
        candidate_models = [self.model_name]
        for fallback_m in [
            "google_genai:gemini-2.5-flash-lite",
            "ollama:gemma4:e2b",
            "google_genai:gemini-3.8-flash",
            "google_genai:gemini-2.5-flash",
        ]:
            if fallback_m not in candidate_models:
                candidate_models.append(fallback_m)

        for m_name in candidate_models:
            try:
                model = init_chat_model(model=m_name, temperature=0.0)
                prompt = SUMMARIZER_PROMPT.format(content=content[:8000])
                resp = model.invoke(prompt)
                raw = resp.content
                if isinstance(raw, list):
                    raw = "".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in raw])
                raw = str(raw).strip()

                match = re.search(r"\{.*\}", raw, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    result = SummaryResult(
                        summary=data.get("summary", "Summary generated."),
                        decisions=data.get("decisions", []),
                        requests=data.get("requests", []),
                        deadlines=data.get("deadlines", []),
                        next_steps=data.get("next_steps", []),
                    )

                    if thread_id:
                        self._persist_summary(thread_id, result.summary)

                    return result
            except Exception:
                continue

        # Smart fallback if all models fail (strips headers, extracts clean text)
        body_lines = []
        for line in content.splitlines():
            line_s = line.strip()
            if not line_s or line_s.startswith("---"):
                continue
            if line_s.lower().startswith(("from:", "date:", "to:")):
                continue
            if line_s.lower().startswith("content:"):
                line_s = line_s[8:].strip()
            if line_s:
                body_lines.append(line_s)

        extracted = " ".join(body_lines)[:350].strip()
        fallback = SummaryResult(
            summary=extracted if extracted else "Email content received.",
            decisions=[],
            requests=[],
            deadlines=[],
            next_steps=[],
        )
        return fallback

    def _persist_summary(self, thread_id: str, summary_text: str) -> None:
        """Save or update thread summary in database."""
        try:
            with db_session() as conn:
                conn.execute(
                    """
                    INSERT INTO thread_summaries (thread_id, summary, last_updated)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(thread_id) DO UPDATE SET
                        summary = excluded.summary,
                        last_updated = CURRENT_TIMESTAMP
                    """,
                    (thread_id, summary_text),
                )
        except Exception:
            pass
