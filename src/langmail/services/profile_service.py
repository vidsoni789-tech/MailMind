"""PersonalMail AI — ProfileService.

Manages user profile settings and durable writing style preferences.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from langmail.storage.database import db_session


class ProfileService:
    """Service handling user profile customization and learned style preferences."""

    @staticmethod
    def get_profile() -> dict[str, Any]:
        """Fetch user profile, creating default if not yet initialized."""
        now = datetime.now(timezone.utc).isoformat()
        with db_session() as conn:
            row = conn.execute("SELECT * FROM user_profiles WHERE id = 1").fetchone()
            if not row:
                conn.execute(
                    """
                    INSERT INTO user_profiles (
                        id, role, organization, college, bio, signature,
                        preferred_language, default_tone, default_reply_length,
                        created_at, updated_at
                    ) VALUES (1, 'Professional', '', '', '', '', 'English', 'professional', 'concise', ?, ?)
                    """,
                    (now, now),
                )
                row = conn.execute("SELECT * FROM user_profiles WHERE id = 1").fetchone()

            return dict(row)

    @staticmethod
    def update_profile(
        role: Optional[str] = None,
        organization: Optional[str] = None,
        college: Optional[str] = None,
        bio: Optional[str] = None,
        signature: Optional[str] = None,
        preferred_language: Optional[str] = None,
        default_tone: Optional[str] = None,
        default_reply_length: Optional[str] = None,
    ) -> dict[str, Any]:
        """Update user profile fields."""
        ProfileService.get_profile()  # ensure initialized
        now = datetime.now(timezone.utc).isoformat()

        updates = ["updated_at = ?"]
        params: list[Any] = [now]

        fields = {
            "role": role,
            "organization": organization,
            "college": college,
            "bio": bio,
            "signature": signature,
            "preferred_language": preferred_language,
            "default_tone": default_tone,
            "default_reply_length": default_reply_length,
        }

        for key, val in fields.items():
            if val is not None:
                updates.append(f"{key} = ?")
                params.append(val)

        query = f"UPDATE user_profiles SET {', '.join(updates)} WHERE id = 1"
        with db_session() as conn:
            conn.execute(query, params)

        return ProfileService.get_profile()

    @staticmethod
    def add_preference(
        pref_type: str,
        value: str,
        contact_email: Optional[str] = None,
        confidence: float = 0.8,
        source: str = "user_edit",
    ) -> dict[str, Any]:
        """Add or reinforce a style preference."""
        clean_email = (
            contact_email.strip().lower()
            if (contact_email and isinstance(contact_email, str) and contact_email.strip())
            else None
        )
        pref_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with db_session() as conn:
            # Check if matching preference already exists
            existing = conn.execute(
                """
                SELECT * FROM style_preferences
                WHERE type = ? AND value = ? AND (
                    (contact_email IS NOT NULL AND LOWER(contact_email) = ?)
                    OR (contact_email IS NULL AND ? IS NULL)
                )
                """,
                (pref_type, value, clean_email, clean_email),
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE style_preferences
                    SET evidence_count = evidence_count + 1,
                        confidence = MIN(1.0, confidence + 0.1),
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (now, existing["id"]),
                )
                pref_id = existing["id"]
            else:
                conn.execute(
                    """
                    INSERT INTO style_preferences (
                        id, contact_email, type, value, confidence, evidence_count, source, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
                    """,
                    (pref_id, clean_email, pref_type, value, confidence, source, now, now),
                )

        return ProfileService.get_preference(pref_id)  # type: ignore

    @staticmethod
    def get_preference(pref_id: str) -> Optional[dict[str, Any]]:
        """Fetch single preference."""
        with db_session() as conn:
            row = conn.execute(
                "SELECT * FROM style_preferences WHERE id = ?", (pref_id,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def list_preferences(contact_email: Optional[str] = None) -> list[dict[str, Any]]:
        """List preferences (global or contact-specific)."""
        clean_email = (
            contact_email.strip().lower()
            if (contact_email and isinstance(contact_email, str) and contact_email.strip())
            else None
        )
        with db_session() as conn:
            if clean_email:
                rows = conn.execute(
                    """
                    SELECT * FROM style_preferences
                    WHERE LOWER(contact_email) = ? OR contact_email IS NULL OR contact_email = ''
                    ORDER BY confidence DESC, evidence_count DESC
                    """,
                    (clean_email,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM style_preferences ORDER BY confidence DESC, evidence_count DESC"
                ).fetchall()

            return [dict(row) for row in rows]

    @staticmethod
    def update_preference(
        pref_id: str,
        value: Optional[str] = None,
        confidence: Optional[float] = None,
        pref_type: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Update fields of an existing style preference."""
        now = datetime.now(timezone.utc).isoformat()
        updates = ["updated_at = ?"]
        params: list[Any] = [now]

        if value is not None:
            updates.append("value = ?")
            params.append(value)
        if confidence is not None:
            updates.append("confidence = ?")
            params.append(max(0.0, min(1.0, float(confidence))))
        if pref_type is not None:
            updates.append("type = ?")
            params.append(pref_type)

        params.append(pref_id)
        query = f"UPDATE style_preferences SET {', '.join(updates)} WHERE id = ?"
        with db_session() as conn:
            conn.execute(query, params)

        return ProfileService.get_preference(pref_id)

    @staticmethod
    def delete_preference(pref_id: str) -> bool:
        """Delete a learned preference."""
        with db_session() as conn:
            res = conn.execute("DELETE FROM style_preferences WHERE id = ?", (pref_id,))
            return res.rowcount > 0

    @staticmethod
    def get_effective_preferences(contact_email: Optional[str] = None) -> dict[str, Any]:
        """Resolve and rank active style preferences for drafting.

        Contact-specific preferences take priority over global preferences.
        Preferences for other contacts are strictly excluded.
        """
        clean_email = (
            contact_email.strip().lower()
            if (contact_email and isinstance(contact_email, str) and contact_email.strip())
            else None
        )

        with db_session() as conn:
            if clean_email:
                rows = conn.execute(
                    """
                    SELECT * FROM style_preferences
                    WHERE LOWER(contact_email) = ? OR contact_email IS NULL OR contact_email = ''
                    ORDER BY confidence DESC, evidence_count DESC
                    """,
                    (clean_email,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM style_preferences
                    WHERE contact_email IS NULL OR contact_email = ''
                    ORDER BY confidence DESC, evidence_count DESC
                    """
                ).fetchall()

            all_prefs = [dict(row) for row in rows]

        # Sort: contact-specific first, then highest confidence
        def sort_key(p: dict[str, Any]):
            p_contact = p.get("contact_email")
            is_contact = 1 if (clean_email and p_contact and p_contact.strip().lower() == clean_email) else 0
            return (is_contact, p.get("confidence", 0.0), p.get("evidence_count", 0))

        sorted_prefs = sorted(all_prefs, key=sort_key, reverse=True)

        effective: dict[str, Any] = {
            "greeting": None,
            "signoff": None,
            "tone": None,
            "conciseness": None,
            "formatting": None,
            "avoid_phrases": [],
            "preferred_phrases": [],
            "all_preferences": sorted_prefs,
        }

        for p in sorted_prefs:
            ptype = p.get("type")
            pval = p.get("value")
            if not ptype or not pval:
                continue

            if ptype == "greeting" and effective["greeting"] is None:
                effective["greeting"] = pval
            elif ptype == "signoff" and effective["signoff"] is None:
                effective["signoff"] = pval
            elif ptype == "tone" and effective["tone"] is None:
                effective["tone"] = pval
            elif ptype in ("conciseness", "length") and effective["conciseness"] is None:
                effective["conciseness"] = pval
            elif ptype == "formatting" and effective["formatting"] is None:
                effective["formatting"] = pval
            elif ptype == "avoid_phrase":
                if pval not in effective["avoid_phrases"]:
                    effective["avoid_phrases"].append(pval)
            elif ptype == "preferred_phrase":
                if pval not in effective["preferred_phrases"]:
                    effective["preferred_phrases"].append(pval)

        return effective

