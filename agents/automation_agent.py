"""Computer Automation Agent (Phase 2 Stub per SPEC.md §10).

This agent is explicitly deferred to Phase 2. Its interface and action
contracts are defined here, but the executor returns an explicit
'not implemented' status so tasks meant for it fail clearly instead of silently.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class AutomationAction(BaseModel):
    """Specification of an automation action for Phase 2."""
    action_type: str = Field(..., description="e.g. open_app, click, download_file, browser_navigate")
    target: str = Field(..., description="App name, file path, or target URL")
    params: Dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = Field(default=True, description="Always true by default")


class AutomationAgent:
    """Phase 2 Stub for Computer and Browser Automation."""

    def __init__(self):
        self.name = "AutomationAgent"
        self.role = "Computer Automation Agent (Phase 2 Stub)"
        self.is_implemented = False

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Returns clear, non-silent failure stating this agent is in Phase 2."""
        return {
            "agent": self.name,
            "status": "not_implemented",
            "task": task,
            "message": (
                "The Computer Automation Agent is not implemented in the Phase 1 MVP "
                "(per §10 of SPEC.md). Browser and OS automation will be introduced in Phase 2 "
                "with Playwright and pywinauto under the strict human approval gate."
            )
        }
