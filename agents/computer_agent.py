"""Computer Automation Agent for Prince AI Team.

Automates file workflows, processes approved directories, and acts as the
safeguarded executor for Windows system tasks.
Strictly requires explicit human approval before any file deletion, modification,
or system-level change.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from agents.base_agent import BaseAgent
from tools.system_tools import default_system_tools
from tools.approval_guard import default_approval_guard


COMPUTER_AGENT_PROMPT = """You are the COMPUTER AUTOMATION AGENT for Prince.
Your role is to help automate tasks on his Windows machine safely and transparently.

Strict Rules:
1. ALWAYS inspect and show what actions will be performed BEFORE doing anything.
2. NEVER delete files, rename folders, or change system settings without explicit approval.
3. Keep file operations scoped strictly to authorized project workspaces.
4. Clearly state what step is completed versus what step is pending human approval.

When formulating an action plan:
- State the target directory/files inspected.
- Explain the planned operation in plain English.
- Highlight if an approval request was submitted.
"""


class ComputerAgent(BaseAgent):
    """Specialized Windows automation and file workflow agent with human approval guardrails."""

    def __init__(self):
        super().__init__(
            name="ComputerAgent",
            role="Windows Computer & File Automation Assistant",
            description="Inspects project files, automates file workflows, and safely routes system changes through human approval.",
            system_prompt=COMPUTER_AGENT_PROMPT
        )
        self.sys_tools = default_system_tools

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Executes computer automation request safely."""
        self.log(f"Received computer automation task: {task[:80]}...")

        task_lower = task.lower()

        # Check if user is asking to list or inspect files
        dir_listing = self.sys_tools.list_directory(".")

        # Check if the task requests a sensitive or destructive action
        is_destructive = any(word in task_lower for word in ["delete", "remove", "clean", "modify", "rename", "overwrite", "kill"])

        approval_result = None
        if is_destructive:
            # Enforce human-in-the-loop approval
            approval_result = self.request_approval(
                action_type="delete_file" if "delete" in task_lower or "remove" in task_lower else "modify_system",
                description=f"Action requested: {task}",
                payload={
                    "task": task,
                    "target_directory": str(Path(".").resolve()),
                    "requires_confirmation": True
                }
            )

        prompt = f"""
User Task: {task}

Safe Workspace Context:
Available workspace items: {[e['name'] for e in dir_listing.get('entries', [])[:10]]}

Approval Status:
{'Requires human approval (Submitted to Approval Queue)' if is_destructive else 'Safe read-only operation'}

Explain what actions were verified, what the file layout is, and what needs Prince's confirmation if applicable.
"""

        response_text = self.call_llm(prompt, temperature=0.5)

        return {
            "agent": self.name,
            "status": "pending_approval" if is_destructive else "success",
            "task": task,
            "analysis": response_text,
            "directory_checked": dir_listing.get("directory"),
            "approval_required": is_destructive,
            "approval_details": approval_result
        }
