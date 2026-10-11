"""PersonalMail AI — DraftService.

Handles drafts lifecycle, user modifications, and generation records.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from langmail.storage.database import db_session


class EditRecordResult(str):
    """Result of record_edit that behaves both as a string edit_id and unpackable tuple."""

    learned_preferences: list[dict[str, Any]]

    def __new__(cls, edit_id: str, learned_preferences: Optional[list[dict[str, Any]]] = None):
        instance = super().__new__(cls, edit_id)
        instance.learned_preferences = learned_preferences or []
        return instance

    def __iter__(self):
        yield str(self)
        yield self.learned_preferences


class DraftService:
    """Service handling generated email drafts, user edits, and send status."""


    @staticmethod
    def create_draft(
        to_email: str,
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
        gmail_draft_id: Optional[str] = None,
        generation_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Record a newly generated draft."""
        draft_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO drafts (
                    id, thread_id, gmail_draft_id, to_email, subject, body,
                    status, generation_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'generated', ?, ?, ?)
                """,
                (
                    draft_id,
                    thread_id,
                    gmail_draft_id,
                    to_email,
                    subject,
                    body,
                    generation_id,
                    now,
                    now,
                ),
            )

        return DraftService.get_draft(draft_id)  # type: ignore

    @staticmethod
    def get_draft(draft_id: str) -> Optional[dict[str, Any]]:
        """Fetch draft by ID."""
        with db_session() as conn:
            row = conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def update_draft(
        draft_id: str,
        body: Optional[str] = None,
        subject: Optional[str] = None,
        status: Optional[str] = None,
        gmail_draft_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Update draft contents or status."""
        now = datetime.now(timezone.utc).isoformat()
        updates = ["updated_at = ?"]
        params: list[Any] = [now]

        if body is not None:
            updates.append("body = ?")
            params.append(body)
        if subject is not None:
            updates.append("subject = ?")
            params.append(subject)
        if status is not None:
            updates.append("status = ?")
            params.append(status.lower())
        if gmail_draft_id is not None:
            updates.append("gmail_draft_id = ?")
            params.append(gmail_draft_id)

        params.append(draft_id)
        query = f"UPDATE drafts SET {', '.join(updates)} WHERE id = ?"

        with db_session() as conn:
            conn.execute(query, params)

        return DraftService.get_draft(draft_id)

    @staticmethod
    def record_edit(
        draft_id: str,
        original_text: str,
        edited_text: str,
        diff_summary: Optional[str] = None,
        generation_id: Optional[str] = None,
        contact_email: Optional[str] = None,
        trigger_learning: bool = True,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Record a user edit and automatically trigger the edit-learning engine.

        Returns:
            Tuple of (edit_id, list_of_learned_preferences)
        """
        from langmail.agents.learning import LearningAgent, compute_edit_diff

        # Auto-compute diff summary if not supplied
        if not diff_summary:
            diff_res = compute_edit_diff(original_text, edited_text)
            diff_summary = diff_res.diff_summary

        edit_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # If contact_email not provided, look up from draft
        target_contact = contact_email
        if not target_contact and draft_id:
            draft = DraftService.get_draft(draft_id)
            if draft:
                target_contact = draft.get("to_email")

        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO user_edits (
                    id, generation_id, draft_id, original_text, edited_text, diff_summary, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (edit_id, generation_id, draft_id, original_text, edited_text, diff_summary, now),
            )

        learned_prefs: list[dict[str, Any]] = []
        if trigger_learning:
            learner = LearningAgent()
            learned_prefs = learner.learn_from_edit(
                original_text=original_text,
                edited_text=edited_text,
                contact_email=target_contact,
                draft_id=draft_id,
            )

        return EditRecordResult(edit_id, learned_prefs)

    @staticmethod
    def get_edit(edit_id: str) -> Optional[dict[str, Any]]:
        """Fetch a specific user edit record."""
        with db_session() as conn:
            row = conn.execute("SELECT * FROM user_edits WHERE id = ?", (edit_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def list_edits(draft_id: Optional[str] = None, limit: int = 50) -> list[dict[str, Any]]:
        """List recorded user edits."""
        with db_session() as conn:
            if draft_id:
                rows = conn.execute(
                    "SELECT * FROM user_edits WHERE draft_id = ? ORDER BY created_at DESC LIMIT ?",
                    (draft_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM user_edits ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(row) for row in rows]


    @staticmethod
    def record_generation(
        intent: str,
        model: str,
        draft_id: Optional[str] = None,
        prompt_version: str = "v1",
        latency_ms: int = 0,
        status: str = "success",
    ) -> str:
        """Record an LLM generation event."""
        gen_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO generations (
                    id, draft_id, intent, model, prompt_version, latency_ms, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (gen_id, draft_id, intent, model, prompt_version, latency_ms, status, now),
            )

        return gen_id

    @staticmethod
    def list_drafts(limit: int = 20) -> list[dict[str, Any]]:
        """List recent drafts."""
        with db_session() as conn:
            rows = conn.execute(
                "SELECT * FROM drafts ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(row) for row in rows]
