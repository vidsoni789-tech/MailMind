"""PersonalMail AI — Agent Pydantic Schemas.

Defines validated structured outputs for all agents according to new_update/agents.md:
- IntentResult
- TriageResult
- SummaryResult
- ActionItem & ActionExtractionResult
- DraftProposal
- QualityCheckItem & QualityCheckResult
- ActionProposal
"""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class IntentType(str, Enum):
    SEARCH = "SEARCH"
    SUMMARIZE = "SUMMARIZE"
    CLASSIFY = "CLASSIFY"
    REPLY = "REPLY"
    IMPROVE = "IMPROVE"
    REGENERATE = "REGENERATE"
    FORWARD = "FORWARD"
    SEND = "SEND"
    FIND_ATTACHMENT = "FIND_ATTACHMENT"
    TASKS = "TASKS"
    HISTORY = "HISTORY"
    PROFILE = "PROFILE"
    GENERAL_CHAT = "GENERAL_CHAT"


class IntentResult(BaseModel):
    """Result of Intent Router classification."""
    intent: IntentType = Field(description="Detected primary intent")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")
    target_thread_id: Optional[str] = Field(default=None, description="Target email thread ID if applicable")
    target_recipient: Optional[str] = Field(default=None, description="Target recipient email or name if applicable")
    needs_clarification: bool = Field(default=False, description="Whether agent needs more input from user")
    explanation: Optional[str] = Field(default=None, description="Brief rationale for the routing decision")


class TriageResult(BaseModel):
    """Output of Triage / Email Reader Agent."""
    category: str = Field(description="Category: job, work, college, personal, newsletter, spam, alert")
    priority: str = Field(description="Priority: urgent, high, medium, low")
    requires_reply: bool = Field(default=False, description="Whether this email expects a user response")
    action_required: bool = Field(default=False, description="Whether action is required")
    security_risk: str = Field(default="none", description="Risk level: none, low, medium, danger")
    reason: str = Field(description="Concise rationale for classification")


class SummaryResult(BaseModel):
    """Output of Thread / Email Summarizer Agent."""
    summary: str = Field(description="High level executive summary of conversation")
    decisions: list[str] = Field(default_factory=list, description="Decisions reached")
    requests: list[str] = Field(default_factory=list, description="Explicit questions or requests made")
    deadlines: list[str] = Field(default_factory=list, description="Mentioned deadlines with context")
    next_steps: list[str] = Field(default_factory=list, description="Recommended next actions")


class ActionItem(BaseModel):
    """A single extracted action item."""
    title: str = Field(description="Concise, actionable task description")
    deadline: Optional[str] = Field(default=None, description="ISO date or relative deadline mentioned (null if none)")
    priority: str = Field(default="medium", description="urgent, high, medium, low")
    source_quote: Optional[str] = Field(default=None, description="Verbatim quote from email that generated this task")


class ActionExtractionResult(BaseModel):
    """Output of Action Extraction Agent."""
    actions: list[ActionItem] = Field(default_factory=list, description="List of extracted actionable items")


class DraftProposal(BaseModel):
    """Output of Reply / Compose Writer Agent."""
    to_email: str = Field(description="Recipient email address")
    subject: str = Field(description="Subject line for email")
    body: str = Field(description="Complete composed email body")
    tone: str = Field(default="professional", description="Tone used: professional, friendly, formal, concise")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0, description="Confidence in generated draft")
    attachment_requests: list[str] = Field(default_factory=list, description="Documents mentioned needing attachment")
    thread_id: Optional[str] = Field(default=None, description="Gmail thread ID if replying")
    draft_id: Optional[str] = Field(default=None, description="Database draft ID if persisted")


class QualityCheckItem(BaseModel):
    """A single check performed by Quality Checker."""
    code: str = Field(description="Check code: MISSING_ATTACHMENT, RECIPIENT_MISMATCH, TONE_MISMATCH, EMPTY_BODY, SENSITIVE_DATA")
    severity: str = Field(description="Severity: INFO, WARNING, BLOCK")
    message: str = Field(description="Human readable explanation")


class QualityCheckResult(BaseModel):
    """Output of Quality Checker."""
    status: str = Field(default="PASS", description="Overall status: PASS, WARNING, BLOCK")
    checks: list[QualityCheckItem] = Field(default_factory=list, description="Individual checks evaluated")


class ActionProposal(BaseModel):
    """Structured action waiting for Human-in-the-Loop approval."""
    action_type: str = Field(description="Type: send, save_draft, forward")
    to_email: str = Field(description="Destination email")
    subject: str = Field(description="Email subject")
    body: str = Field(description="Email body text")
    thread_id: Optional[str] = Field(default=None)
    draft_id: Optional[str] = Field(default=None)
    requires_approval: bool = Field(default=True, description="Strictly true for all external sends")
    token: Optional[str] = Field(default=None, description="Idempotency / approval token")


class AttachmentSuggestion(BaseModel):
    """A single recommended attachment file."""
    file_id: str = Field(description="Unique ID of the indexed file")
    filename: str = Field(description="Name of the file")
    file_path: str = Field(description="Local filesystem path to the file")
    directory_path: Optional[str] = Field(default=None, description="Directory path containing the file")
    size_bytes: int = Field(default=0, description="File size in bytes")
    mime_type: Optional[str] = Field(default=None, description="MIME type")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Match confidence")
    reason: str = Field(description="Reason why this file is suggested")
    is_selected: bool = Field(default=False, description="Whether approved by user for sending")


class AttachmentRecommendation(BaseModel):
    """Output of Attachment Agent."""
    requested_files: list[str] = Field(default_factory=list, description="Documents requested in email/draft")
    suggestions: list[AttachmentSuggestion] = Field(default_factory=list, description="Ranked candidate files")

