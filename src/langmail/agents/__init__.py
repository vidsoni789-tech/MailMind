"""PersonalMail AI Agents Package."""

from langmail.agents.attachment import AttachmentAgent
from langmail.agents.extractor import TaskExtractor
from langmail.agents.learning import LearnedPreference, LearningAgent, compute_edit_diff
from langmail.agents.orchestrator import MasterOrchestrator
from langmail.agents.quality import QualityChecker
from langmail.agents.router import IntentRouter
from langmail.agents.summarizer import EmailSummarizer
from langmail.agents.writer import ReplyWriter

__all__ = [
    "AttachmentAgent",
    "TaskExtractor",
    "LearningAgent",
    "LearnedPreference",
    "compute_edit_diff",
    "MasterOrchestrator",
    "QualityChecker",
    "IntentRouter",
    "EmailSummarizer",
    "ReplyWriter",
]


