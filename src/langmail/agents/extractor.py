"""Task Extractor sub-agent.

Reads email threads and extracts actionable tasks, deadlines, and commitments.
Produces structured ActionExtractionResult and persists tasks to the local SQLite database.
"""

import json
import re
from typing import Optional
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool

from langmail.config import settings
from langmail.models.agent_schemas import ActionExtractionResult, ActionItem
from langmail.prompts.templates import TASK_EXTRACTOR_SYSTEM
from langmail.services import TaskService
from langmail.state import GmailAgentState
from langmail.tools.gmail_tools import gmail_read_thread


EXTRACTION_PROMPT = """Extract all action items, tasks, and deadlines from this email.

=== EMAIL CONTENT ===
{content}

Respond ONLY with valid JSON using this exact schema:
{{
  "actions": [
    {{
      "title": "Clear concise actionable task",
      "deadline": "ISO date string or relative deadline, or null if none",
      "priority": "urgent | high | medium | low",
      "source_quote": "Exact short sentence from email"
    }}
  ]
}}
"""


@tool(parse_docstring=True)
def think_tasks(reflection: str) -> str:
    """Pause to reason about what tasks are genuinely actionable.

    Use this before finalizing your task list to avoid over-extracting
    vague or already-completed items.

    Args:
        reflection: Your analysis of what requires action vs. what doesn't.
    """
    return f"Task analysis recorded: {reflection}"


class TaskExtractor:
    """Agent that extracts actionable tasks from emails and persists them to SQLite."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.summarization_model

    def extract_and_persist(
        self,
        content: str,
        thread_id: Optional[str] = None,
        source_from: Optional[str] = None,
        persist: bool = True,
    ) -> ActionExtractionResult:
        """Extract tasks and save them directly to database tasks table."""
        model = init_chat_model(model=self.model_name, temperature=0.0)
        prompt = EXTRACTION_PROMPT.format(content=content[:5000])

        try:
            resp = model.invoke(prompt)
            raw = resp.content
            if isinstance(raw, list):
                raw = "".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in raw])
            raw = str(raw).strip()

            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                items = []
                for a in data.get("actions", []):
                    item = ActionItem(
                        title=a.get("title", "Action item"),
                        deadline=a.get("deadline"),
                        priority=a.get("priority", "medium").lower(),
                        source_quote=a.get("source_quote"),
                    )
                    items.append(item)

                    if persist and thread_id:
                        TaskService.create_task(
                            thread_id=thread_id,
                            title=item.title,
                            deadline=item.deadline,
                            priority=item.priority,
                            source_from=source_from,
                            source_text=item.source_quote,
                        )

                return ActionExtractionResult(actions=items)
        except Exception:
            pass

        return ActionExtractionResult(actions=[])


def create_task_extractor(model_name: str) -> object:
    """Build the Task Extractor sub-agent for backward compatibility.

    Args:
        model_name: Provider:model string.

    Returns:
        Compiled LangGraph agent ready to invoke.
    """
    model = init_chat_model(model=model_name, temperature=0.0)
    tools = [gmail_read_thread, think_tasks]

    agent = create_agent(
        model,
        tools,
        system_prompt=TASK_EXTRACTOR_SYSTEM,
        state_schema=GmailAgentState,
    )

    return agent


# Backward compatibility alias
ActionExtractor = TaskExtractor
