"""Unit and integration tests for Phase 5: Pre-Send Quality and Safety Checker."""

import pytest
from fastapi.testclient import TestClient

from langmail.agents.quality import QualityChecker
from langmail.models.agent_schemas import (
    DraftProposal,
    QualityCheckItem,
    QualityCheckResult,
)
from langmail.agents.orchestrator import MasterOrchestrator
from langmail.services import DraftService


# ---------------------------------------------------------------------------
# Unit Tests: QualityChecker
# ---------------------------------------------------------------------------

class TestQualityChecker:
    @pytest.fixture
    def checker(self):
        return QualityChecker()

    def test_clean_draft_passes(self, checker):
        """A complete, well-formed draft with valid recipient should PASS."""
        draft = {
            "to_email": "sarah.connor@example.com",
            "subject": "Project Status Update",
            "body": "Hi Sarah,\n\nHere is the current milestone summary for this week.\n\nBest regards,\nAlex",
        }
        res = checker.check(draft)
        assert res.status == "PASS"
        assert len(res.checks) == 0

    def test_missing_attachment_detected(self, checker):
        """Draft mentioning attachments without attached files should yield WARNING."""
        draft = {
            "to_email": "recruiter@hiring.com",
            "subject": "Job Application",
            "body": "Dear Recruiter,\n\nI have attached my resume for the Senior Software Engineer role.\n\nThanks,\nCandidate",
        }
        res = checker.check(draft, attached_files=[])
        assert res.status == "WARNING"
        codes = [c.code for c in res.checks]
        assert "MISSING_ATTACHMENT" in codes
        item = next(c for c in res.checks if c.code == "MISSING_ATTACHMENT")
        assert item.severity == "WARNING"
        assert "attached" in item.message.lower()

        # When files are provided, missing attachment warning should disappear
        res_with_files = checker.check(draft, attached_files=["resume.pdf"])
        codes_with_files = [c.code for c in res_with_files.checks]
        assert "MISSING_ATTACHMENT" not in codes_with_files

    def test_recipient_name_mismatch(self, checker):
        """Greeting someone other than the recipient email user should yield WARNING."""
        draft = {
            "to_email": "alex.morgan@company.com",
            "subject": "Quick Question",
            "body": "Dear John,\n\nCould you review this proposal when you get a chance?\n\nRegards,\nTeam",
        }
        res = checker.check(draft)
        assert res.status == "WARNING"
        codes = [c.code for c in res.checks]
        assert "RECIPIENT_MISMATCH" in codes
        item = next(c for c in res.checks if c.code == "RECIPIENT_MISMATCH")
        assert item.severity == "WARNING"
        assert "John" in item.message

        # No mismatch when greeting matches email user
        draft_correct = {
            "to_email": "alex.morgan@company.com",
            "subject": "Quick Question",
            "body": "Hi Alex,\n\nCould you review this proposal when you get a chance?\n\nRegards,\nTeam",
        }
        res_correct = checker.check(draft_correct)
        codes_correct = [c.code for c in res_correct.checks]
        assert "RECIPIENT_MISMATCH" not in codes_correct

        # Generic greetings should not trigger false positives
        draft_generic = {
            "to_email": "alex.morgan@company.com",
            "subject": "Update",
            "body": "Hi team,\n\nHere is our update.\n\nRegards,\nAlex",
        }
        res_generic = checker.check(draft_generic)
        assert "RECIPIENT_MISMATCH" not in [c.code for c in res_generic.checks]

    def test_empty_or_too_short_body_blocks(self, checker):
        """Empty or trivial body must produce BLOCK severity."""
        draft_empty = {"to_email": "test@example.com", "subject": "Hello", "body": ""}
        res_empty = checker.check(draft_empty)
        assert res_empty.status == "BLOCK"
        assert any(c.code == "EMPTY_BODY" and c.severity == "BLOCK" for c in res_empty.checks)

        draft_short = {"to_email": "test@example.com", "subject": "Hello", "body": "Hey"}
        res_short = checker.check(draft_short)
        assert res_short.status == "BLOCK"
        assert any(c.code == "EMPTY_BODY" for c in res_short.checks)

    def test_missing_or_invalid_recipient_blocks(self, checker):
        """Missing or invalid recipient must produce BLOCK severity."""
        draft_no_recip = {
            "to_email": "",
            "subject": "Meeting",
            "body": "Hello, let's meet tomorrow at 10 AM.",
        }
        res_no_recip = checker.check(draft_no_recip)
        assert res_no_recip.status == "BLOCK"
        assert any(c.code == "MISSING_RECIPIENT" for c in res_no_recip.checks)

        draft_bad_recip = {
            "to_email": "invalid-email-address",
            "subject": "Meeting",
            "body": "Hello, let's meet tomorrow at 10 AM.",
        }
        res_bad_recip = checker.check(draft_bad_recip)
        assert res_bad_recip.status == "BLOCK"
        assert any(c.code == "INVALID_RECIPIENT" for c in res_bad_recip.checks)

    def test_sensitive_data_leaks_block(self, checker):
        """Accidental passwords, OpenAI/Anthropic/Google keys must yield BLOCK."""
        # API Key
        draft_key = {
            "to_email": "developer@partner.com",
            "subject": "API Access",
            "body": "Here is the key: sk-ant-api03-abcdef1234567890abcdef1234567890. Please do not share.",
        }
        res_key = checker.check(draft_key)
        assert res_key.status == "BLOCK"
        assert any(c.code == "SENSITIVE_DATA" and c.severity == "BLOCK" for c in res_key.checks)

        # Plaintext Password
        draft_pwd = {
            "to_email": "user@example.com",
            "subject": "Credentials",
            "body": "Your temporary password: SuperSecret99! and login at site.",
        }
        res_pwd = checker.check(draft_pwd)
        assert res_pwd.status == "BLOCK"
        assert any(c.code == "SENSITIVE_DATA" for c in res_pwd.checks)

    def test_tone_mismatch_and_slang(self, checker):
        """Vulgar terms yield WARNING; informal slang yields INFO."""
        draft_vulgar = {
            "to_email": "client@enterprise.com",
            "subject": "Project delay",
            "body": "Hi Client,\n\nWTF happened with the server outage yesterday?\n\nAlex",
        }
        res_vulgar = checker.check(draft_vulgar)
        assert res_vulgar.status == "WARNING"
        assert any(c.code == "TONE_MISMATCH" and c.severity == "WARNING" for c in res_vulgar.checks)

        draft_slang = {
            "to_email": "client@enterprise.com",
            "subject": "Meeting",
            "body": "Hi client,\n\nLMAO that was funny, idk if we can meet though tbh.\n\nAlex",
        }
        res_slang = checker.check(draft_slang)
        assert res_slang.status == "INFO"
        assert any(c.code == "TONE_MISMATCH" and c.severity == "INFO" for c in res_slang.checks)

    def test_thread_contradiction(self, checker):
        """Draft confirming attendance when thread declined should yield WARNING."""
        thread_context = (
            "From: Bob <bob@example.com>\n"
            "Date: yesterday\n"
            "Content: Unfortunately I am unable to meet and have to decline the Thursday sync.\n---"
        )
        draft = {
            "to_email": "bob@example.com",
            "subject": "Re: Thursday sync",
            "body": "Hi Bob,\n\nConfirming our meeting on Thursday at 2 PM. Looking forward to it!\n\nAlex",
        }
        res = checker.check(draft, thread_context=thread_context)
        assert res.status == "WARNING"
        assert any(c.code == "THREAD_CONTRADICTION" for c in res.checks)

    def test_unresolved_placeholder_detected(self, checker):
        """Draft containing unfilled template placeholders like [Your Name] must yield WARNING."""
        draft_placeholder = {
            "to_email": "vidhanshji01@gmail.com",
            "subject": "Unable to Meet Tomorrow",
            "body": "Dear Vidhansh,\n\nI won't be able to meet tomorrow. I will be going to college.\n\nBest regards,\n[Your Name]",
        }
        res = checker.check(draft_placeholder)
        assert res.status == "WARNING"
        assert any(c.code == "UNRESOLVED_PLACEHOLDER" for c in res.checks)
        item = next(c for c in res.checks if c.code == "UNRESOLVED_PLACEHOLDER")
        assert "[Your Name]" in item.message

        # Once replaced, placeholder warning is gone
        draft_clean = {
            "to_email": "vidhanshji01@gmail.com",
            "subject": "Unable to Meet Tomorrow",
            "body": "Dear Vidhansh,\n\nI won't be able to meet tomorrow. I will be going to college.\n\nBest regards,\nVidhansh",
        }
        res_clean = checker.check(draft_clean)
        assert not any(c.code == "UNRESOLVED_PLACEHOLDER" for c in res_clean.checks)


# ---------------------------------------------------------------------------
# Integration Tests: Orchestrator includes quality_check
# ---------------------------------------------------------------------------

class TestOrchestratorQualityIntegration:
    def test_orchestrator_attaches_quality_check_to_draft_card(self):
        """Orchestrator reply branch should run quality checker and embed results."""
        from unittest.mock import patch
        orchestrator = MasterOrchestrator()
        with patch.object(orchestrator.writer, "generate_draft") as mock_gen:
            mock_gen.return_value = DraftProposal(
                to_email="alex@example.com",
                subject="Job Application",
                body="Dear John,\n\nI have attached my resume for the role.\n\nThanks!",
                draft_id="d-q1",
                attachment_requests=["resume"],
            )
            result = orchestrator.process_message(
                message="Reply to alex@example.com saying I attached my resume for the job.",
            )
            assert result["draft_card"] is not None
            dc = result["draft_card"]
            assert "quality_check" in dc
            qc = dc["quality_check"]
            assert "status" in qc
            assert "checks" in qc
            assert qc["status"] in ("WARNING", "BLOCK")
            codes = [c["code"] for c in qc["checks"]]
            assert "MISSING_ATTACHMENT" in codes
            assert "RECIPIENT_MISMATCH" in codes


# ---------------------------------------------------------------------------
# Integration Tests: API Endpoints
# ---------------------------------------------------------------------------

class TestQualityApiEndpoints:
    @pytest.fixture
    def client(self):
        from langmail.api.app import app
        return TestClient(app)

    def test_validate_draft_endpoint(self, client):
        """POST /api/drafts/validate should return structured quality check results."""
        payload = {
            "to_email": "alex@example.com",
            "subject": "Greetings",
            "body": "Dear John,\n\nPlease find attached the secret report.\n\nBest,\nMe",
        }
        res = client.post("/api/drafts/validate", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "WARNING"
        codes = [c["code"] for c in data["checks"]]
        assert "MISSING_ATTACHMENT" in codes
        assert "RECIPIENT_MISMATCH" in codes

    def test_validate_persisted_draft_endpoint(self, client):
        """GET /api/drafts/{id}/quality-check should check saved draft in DB."""
        # Create a test draft
        draft = DraftService.create_draft(
            to_email="colleague@test.com",
            subject="Notes",
            body="Hi colleague,\n\nHere are the notes from our discussion.\n\nAlex",
        )
        draft_id = draft["id"]

        res = client.get(f"/api/drafts/{draft_id}/quality-check")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "PASS"

    def test_send_blocked_when_quality_check_fails(self, client):
        """POST /api/actions/send should reject sending if draft contains BLOCK errors."""
        # Draft with empty body and sensitive password
        payload = {
            "to_email": "target@example.com",
            "subject": "Leaked",
            "body": "",  # Empty body is a BLOCK error
            "user_approved": True,
        }
        res = client.post("/api/actions/send", json=payload)
        assert res.status_code == 400
        assert "blocking quality errors" in res.json()["detail"].lower()

        # Sensitive credential leak
        payload_secret = {
            "to_email": "target@example.com",
            "subject": "Secret",
            "body": "Here is the master password: SuperSecretKey999!",
            "user_approved": True,
        }
        res_secret = client.post("/api/actions/send", json=payload_secret)
        assert res_secret.status_code == 400
        assert "blocking quality errors" in res_secret.json()["detail"].lower()
