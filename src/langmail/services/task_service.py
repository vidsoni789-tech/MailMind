"""PersonalMail AI — TaskService.

Manages action items, deadlines, and completion states.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from langmail.storage.database import db_session


class TaskService:
    """Service handling action items extracted from emails."""

    @staticmethod
    def create_task(
        thread_id: Optional[str] = None,
        title: str = "",
        message_id: Optional[str] = None,
        deadline: Optional[str] = None,
        priority: str = "medium",
        source_from: Optional[str] = None,
        source_text: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Insert or update a task extracted from an email or created manually."""
        task_id = str(uuid.uuid4())
        effective_title = title or kwargs.get("title", "Untitled Task")
        effective_thread_id = thread_id or kwargs.get("thread_id") or "manual"
        now = datetime.now(timezone.utc).isoformat()

        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO tasks (
                    id, thread_id, message_id, title, deadline, priority,
                    status, source_from, source_text, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
                """,
                (
                    task_id,
                    effective_thread_id,
                    message_id,
                    effective_title,
                    deadline,
                    priority.lower(),
                    source_from,
                    source_text,
                    now,
                    now,
                ),
            )

        return TaskService.get_task(task_id)  # type: ignore

    @staticmethod
    def get_task(task_id: str) -> Optional[dict[str, Any]]:
        """Fetch a single task."""
        with db_session() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def list_tasks(
        status: Optional[str] = None,
        priority: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """List tasks with optional status, priority, and search filters."""
        query = "SELECT * FROM tasks WHERE 1=1"
        params: list[Any] = []

        if status and status.lower() != "all":
            query += " AND status = ?"
            params.append(status.lower())

        if priority and priority.lower() != "all":
            query += " AND priority = ?"
            params.append(priority.lower())

        if search:
            query += " AND (title LIKE ? OR source_text LIKE ? OR source_from LIKE ?)"
            term = f"%{search.strip()}%"
            params.extend([term, term, term])

        query += " ORDER BY CASE WHEN deadline IS NULL THEN 1 ELSE 0 END, deadline ASC, created_at DESC"

        with db_session() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_task_status(task_id: str, status: str) -> Optional[dict[str, Any]]:
        """Update a task's status (e.g. pending -> completed)."""
        now = datetime.now(timezone.utc).isoformat()
        with db_session() as conn:
            conn.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                (status.lower(), now, task_id),
            )
        return TaskService.get_task(task_id)

    @staticmethod
    def delete_task(task_id: str) -> bool:
        """Delete a task."""
        with db_session() as conn:
            res = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            return res.rowcount > 0
