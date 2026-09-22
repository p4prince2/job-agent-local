"""Approval Guardrail for Prince AI Team.

Intercepts dangerous, irreversible, or publishing actions,
stores them in the approval queue, and prevents automatic execution.
"""

from typing import Any, Dict, Optional
from core.database import add_approval_request, list_pending_approvals, decide_approval

DANGEROUS_ACTIONS = {
    "publish_content": "Publishing content directly to social media (LinkedIn / X)",
    "delete_file": "Deleting a file or folder from the filesystem",
    "modify_system": "Changing system configuration, registry, or environment variables",
    "git_push": "Pushing git commits or merging pull requests",
    "git_delete": "Deleting a branch, tag, or repository",
    "send_message": "Sending an external email or message automatically",
    "financial": "Any transaction or purchase"
}


class ApprovalGuard:
    """Guards actions by requiring explicit user approval before execution."""

    @staticmethod
    def requires_approval(action_type: str) -> bool:
        """Determines whether an action type is sensitive or dangerous."""
        return action_type.lower() in DANGEROUS_ACTIONS

    @staticmethod
    def submit_for_approval(agent_name: str, action_type: str, description: str,
                            payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Queues an action for Prince's review."""
        req_id = add_approval_request(
            agent_name=agent_name,
            action_type=action_type,
            description=description,
            payload=payload or {}
        )
        action_label = DANGEROUS_ACTIONS.get(action_type, action_type)
        return {
            "status": "requires_approval",
            "approval_id": req_id,
            "agent": agent_name,
            "action": action_type,
            "description": description,
            "message": f"Action paused for safety: {action_label}. Request #{req_id} added to Approval Queue."
        }

    @staticmethod
    def get_pending_count() -> int:
        """Returns the number of pending approvals."""
        return len(list_pending_approvals())


default_approval_guard = ApprovalGuard()
