"""Unit and integration tests for Phase 4: Intent Router, Structured Schemas, and Orchestrator."""

import pytest
from unittest.mock import MagicMock, patch

from langmail.models.agent_schemas import (
    IntentResult,
    IntentType,
    TriageResult,
    SummaryResult,
    ActionItem,
    ActionExtractionResult,
    DraftProposal,
    QualityCheckItem,
    QualityCheckResult,
    ActionProposal,
)
from langmail.agents.router import IntentRouter
from langmail.agents.summarizer import EmailSummarizer
from langmail.agents.extractor import TaskExtractor
from langmail.agents.writer import ReplyWriter
from langmail.agents.orchestrator import MasterOrchestrator
from langmail.services import DraftService, TaskService, EmailService


def test_agent_schemas():
    """Verify all Pydantic schemas validate structured inputs properly."""
    intent = IntentResult(intent=IntentType.REPLY, confidence=0.98, target_thread_id="t123")
    assert intent.intent == IntentType.REPLY
    assert intent.confidence == 0.98

    triage = TriageResult(
        category="job",
        priority="high",
        requires_reply=True,
        action_required=True,
        security_risk="low",
        reason="Interview request",
    )
    assert triage.category == "job"
    assert triage.requires_reply is True

    summary = SummaryResult(
        summary="Overview of project status.",
        decisions=["Agreed on launch date"],
        requests=["Send report"],
        deadlines=["Oct 15"],
        next_steps=["Deploy"],
    )
    assert len(summary.decisions) == 1
    assert len(summary.deadlines) == 1

    action = ActionItem(title="Update resume", deadline="2026-10-15", priority="high")
    extraction = ActionExtractionResult(actions=[action])
    assert len(extraction.actions) == 1
    assert extraction.actions[0].title == "Update resume"

    proposal = DraftProposal(
        to_email="test@example.com",
        subject="Re: Update",
        body="Thank you for the update.",
        tone="professional",
    )
    assert proposal.to_email == "test@example.com"
    assert proposal.body.startswith("Thank you")

    qcheck = QualityCheckResult(
        status="WARNING",
        checks=[QualityCheckItem(code="MISSING_ATTACHMENT", severity="WARNING", message="Missing file")],
    )
    assert qcheck.status == "WARNING"


def test_intent_router_heuristics():
    """Verify IntentRouter fast heuristics for common email operations."""
    router = IntentRouter()

    res_reply = router.classify("Reply to John and say I'll attend", thread_id="t1")
    assert res_reply.intent == IntentType.REPLY
    assert res_reply.target_thread_id == "t1"

    res_compose = router.classify("Compose an email to HR asking about benefits")
    assert res_compose.intent == IntentType.REPLY

    res_improve = router.classify("Make it more formal and concise")
    assert res_improve.intent == IntentType.IMPROVE

    res_tasks = router.classify("Extract action items and deadlines from this thread")
    assert res_tasks.intent == IntentType.TASKS

    res_summarize = router.classify("Summarize my important emails")
    assert res_summarize.intent == IntentType.SUMMARIZE

    res_search = router.classify("Search for emails from google")
    assert res_search.intent == IntentType.SEARCH

    res_chat = router.classify("Hi, what can you do?")
    assert res_chat.intent == IntentType.GENERAL_CHAT


def test_reply_writer_generates_and_persists_draft():
    """Verify ReplyWriter creates a draft and records it in DraftService."""
    writer = ReplyWriter()

    # Mock the LLM call to return valid draft JSON
    mock_response = MagicMock()
    mock_response.content = '{"to_email": "hr@company.com", "subject": "Job Application", "body": "Dear HR,\\n\\nI am interested.\\n\\nBest regards,", "tone": "formal", "confidence": 0.95, "attachment_requests": ["resume"]}'

    with patch("langmail.agents.writer.init_chat_model") as mock_init:
        mock_model = MagicMock()
        mock_model.invoke.return_value = mock_response
        mock_init.return_value = mock_model

        proposal = writer.generate_draft(
            instruction="Apply for the software engineer position",
            recipient="hr@company.com",
            thread_id="t_job_1",
            persist=True,
        )

        assert proposal.to_email == "hr@company.com"
        assert proposal.subject == "Job Application"
        assert "resume" in proposal.attachment_requests
        assert proposal.draft_id is not None

        # Verify draft was recorded in SQLite
        db_draft = DraftService.get_draft(proposal.draft_id)
        assert db_draft is not None
        assert db_draft["to_email"] == "hr@company.com"


def test_task_extractor_persists_tasks():
    """Verify TaskExtractor extracts action items and records them in TaskService."""
    extractor = TaskExtractor()

    mock_response = MagicMock()
    mock_response.content = '{"actions": [{"title": "Submit tax form", "deadline": "2026-10-20", "priority": "urgent", "source_quote": "Please submit your tax form by Oct 20"}]}'

    with patch("langmail.agents.extractor.init_chat_model") as mock_init:
        mock_model = MagicMock()
        mock_model.invoke.return_value = mock_response
        mock_init.return_value = mock_model

        res = extractor.extract_and_persist(
            content="Important notice: Please submit your tax form by Oct 20.",
            thread_id="t_tax_1",
            source_from="finance@company.com",
            persist=True,
        )

        assert len(res.actions) == 1
        assert res.actions[0].title == "Submit tax form"
        assert res.actions[0].priority == "urgent"

        # Verify task exists in SQLite
        tasks = TaskService.list_tasks(status="pending")
        found = [t for t in tasks if t["title"] == "Submit tax form"]
        assert len(found) > 0


def test_orchestrator_reply_branch():
    """Verify MasterOrchestrator routes reply intent to generate draft card with approval flag."""
    orchestrator = MasterOrchestrator()

    with patch.object(orchestrator.writer, "generate_draft") as mock_gen:
        mock_gen.return_value = DraftProposal(
            to_email="colleague@example.com",
            subject="Re: Meeting",
            body="I will attend.",
            draft_id="d-1234",
            thread_id="t-meet",
        )

        result = orchestrator.process_message(
            message="Reply to colleague: I will attend the meeting",
            selected_thread_id="t-meet",
        )

        assert result["intent"] == "REPLY"
        assert result["draft_card"] is not None
        assert result["draft_card"]["id"] == "d-1234"
        assert result["draft_card"]["requires_approval"] is True
        assert "colleague@example.com" in result["draft_card"]["to_email"]
