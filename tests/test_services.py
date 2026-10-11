"""Unit tests for PersonalMail AI storage and services layer."""

import pytest
from pathlib import Path

from langmail.services import (
    EmailService,
    TaskService,
    DraftService,
    ProfileService,
    AttachmentService,
    AuditService,
)
from langmail.storage.database import db_session, get_connection


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Fixture pointing DB_FILE to a temporary SQLite database."""
    test_db_path = tmp_path / "test_gmail.db"
    monkeypatch.setattr("langmail.config.DB_FILE", test_db_path)
    monkeypatch.setattr("langmail.storage.database.DB_FILE", test_db_path)
    return test_db_path


class TestEmailService:
    def test_list_and_triage(self, temp_db):
        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO messages (
                    message_id, thread_id, subject, snippet, from_email, from_name,
                    date, is_read, category, priority, requires_reply
                ) VALUES (
                    'msg_1', 'th_1', 'Interview Invitation', 'Can you attend?',
                    'hr@company.com', 'HR Team', '2026-10-08T10:00:00Z', 0, 'job', 'high', 1
                )
                """
            )

        emails = EmailService.list_emails(unread_only=True)
        assert len(emails) == 1
        assert emails[0]["subject"] == "Interview Invitation"

        # Test triage update
        EmailService.update_triage("msg_1", category="job", priority="urgent", requires_reply=True, security_risk="safe", reason="Interview")
        email = EmailService.get_email("msg_1")
        assert email["priority"] == "urgent"

        metrics = EmailService.get_inbox_metrics()
        assert metrics["unread"] == 1
        assert metrics["needs_reply"] == 1
        assert metrics["high_priority"] == 1


class TestTaskService:
    def test_task_lifecycle(self, temp_db):
        task = TaskService.create_task(
            thread_id="th_100",
            title="Send updated resume",
            deadline="2026-10-15",
            priority="high",
            source_from="hr@company.com",
            source_text="Please send your updated resume by Friday."
        )
        assert task["title"] == "Send updated resume"
        assert task["status"] == "pending"

        tasks = TaskService.list_tasks(status="pending")
        assert len(tasks) == 1

        updated = TaskService.update_task_status(task["id"], "completed")
        assert updated["status"] == "completed"

        assert len(TaskService.list_tasks(status="pending")) == 0
        assert len(TaskService.list_tasks(status="completed")) == 1

        deleted = TaskService.delete_task(task["id"])
        assert deleted is True
        assert len(TaskService.list_tasks()) == 0


class TestDraftService:
    def test_draft_lifecycle_and_edits(self, temp_db):
        draft = DraftService.create_draft(
            to_email="colleague@example.com",
            subject="Project Update",
            body="Here is the project update...",
            thread_id="th_200",
        )
        assert draft["subject"] == "Project Update"
        assert draft["status"] == "generated"

        # Update draft
        updated = DraftService.update_draft(
            draft["id"],
            body="Updated: Here is the finalized project update.",
            status="edited"
        )
        assert updated["status"] == "edited"

        # Record user edit
        edit_id = DraftService.record_edit(
            draft_id=draft["id"],
            original_text="Here is the project update...",
            edited_text="Updated: Here is the finalized project update.",
            diff_summary="Added finalized prefix"
        )
        assert edit_id is not None

        # Record generation
        gen_id = DraftService.record_generation(
            intent="REPLY",
            model="gemini-1.5-flash",
            draft_id=draft["id"],
            latency_ms=450
        )
        assert gen_id is not None


class TestProfileService:
    def test_profile_and_preferences(self, temp_db):
        profile = ProfileService.get_profile()
        assert profile["role"] == "Professional"

        updated = ProfileService.update_profile(
            role="AI Engineer",
            organization="Tech Corp",
            bio="Software Developer",
            default_tone="concise"
        )
        assert updated["role"] == "AI Engineer"
        assert updated["default_tone"] == "concise"

        # Add style preference
        pref = ProfileService.add_preference(
            pref_type="greeting",
            value="Hi",
            contact_email="hr@company.com",
            confidence=0.9
        )
        assert pref["value"] == "Hi"

        # Reinforce existing preference
        pref2 = ProfileService.add_preference(
            pref_type="greeting",
            value="Hi",
            contact_email="hr@company.com",
        )
        assert pref2["evidence_count"] == 2

        prefs = ProfileService.list_preferences(contact_email="hr@company.com")
        assert len(prefs) == 1

        deleted = ProfileService.delete_preference(pref["id"])
        assert deleted is True


class TestAttachmentService:
    def test_index_and_search_candidates(self, temp_db, tmp_path):
        sample_file = tmp_path / "Resume_2026.pdf"
        sample_file.write_text("dummy resume content")

        indexed = AttachmentService.index_file(str(sample_file), tags="resume, cv")
        assert indexed is not None
        assert indexed["filename"] == "Resume_2026.pdf"
        assert indexed["mime_type"] == "application/pdf"

        candidates = AttachmentService.search_candidates("resume")
        assert len(candidates) == 1
        assert candidates[0]["filename"] == "Resume_2026.pdf"


class TestAuditService:
    def test_record_audit(self, temp_db):
        log_id = AuditService.record_action(
            action="send_email",
            target_type="draft",
            target_id="draft_123",
            approval_status="approved",
            result="success"
        )
        assert log_id is not None

        logs = AuditService.list_logs()
        assert len(logs) == 1
        assert logs[0]["action"] == "send_email"
        assert logs[0]["approval_status"] == "approved"
