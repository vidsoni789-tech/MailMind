"""PersonalMail AI — AuditService.

Records immutable audit trails for external write actions and user approval decisions.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from langmail.storage.database import db_session


class AuditService:
    """Service handling audit logging for security and compliance."""

    @staticmethod
    def record_action(
        action: str,
        target_type: str,
        approval_status: str,
        target_id: Optional[str] = None,
        result: Optional[str] = None,
    ) -> str:
        """Record an action event (e.g. proposed, approved, rejected, executed)."""
        log_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO audit_logs (
                    id, action, target_type, target_id, approval_status, result, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (log_id, action, target_type, target_id, approval_status, result, now),
            )

        return log_id

    @staticmethod
    def list_logs(limit: int = 50) -> list[dict[str, Any]]:
        """List audit history."""
        with db_session() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(row) for row in rows]
