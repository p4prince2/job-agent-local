"""Approval Queue and Safety Gate Manager (per SPEC.md §11).

Enforces strict human-in-the-loop approval before any risky, irreversible,
or publishing action can proceed.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from db.models import Approval
from db.session import SessionLocal
from logging_utils.logger import get_logger

logger = get_logger("ApprovalManager")

# Master dictionary of actions requiring mandatory human approval per §11
DANGEROUS_ACTIONS: Dict[str, str] = {
    "publish_content": "Publishing content directly to social media (LinkedIn, Medium, X)",
    "send_message": "Sending an external email or direct message",
    "delete_file": "Deleting a file or folder from the filesystem",
    "purchase": "Purchasing anything or executing financial transactions",
    "modify_system": "Changing system configuration, registry, or environment variables",
    "github_branch_create": "Creating a new branch on GitHub",
    "github_commit": "Committing changes to a repository",
    "github_pr_create": "Opening a Pull Request on GitHub",
    "automation_action": "Executing automated computer or browser actions"
}


class ApprovalManager:
    """Manages creation, verification, and resolution of sensitive actions."""

    @staticmethod
    def requires_approval(action_type: str) -> bool:
        """Returns True if the action is categorized as risky or publishing."""
        return action_type.lower() in DANGEROUS_ACTIONS

    @staticmethod
    def request_approval(
        action_type: str,
        description: str,
        payload: Dict[str, Any],
        requested_by_agent: str,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Creates a pending approval record and halts execution until user confirms."""
        owns_db = False
        if db is None:
            db = SessionLocal()
            owns_db = True

        try:
            payload_str = json.dumps(payload or {})
            approval = Approval(
                action_type=action_type,
                description=description,
                payload_json=payload_str,
                requested_by_agent=requested_by_agent,
                status="pending",
                created_at=datetime.utcnow()
            )
            db.add(approval)
            db.commit()
            db.refresh(approval)

            msg = f"Action halted: '{action_type}' by {requested_by_agent} requires human approval (Request #{approval.id})"
            logger.warning(msg)

            return {
                "approval_id": approval.id,
                "status": "pending_approval",
                "action_type": action_type,
                "description": description,
                "message": msg
            }
        finally:
            if owns_db:
                db.close()

    @staticmethod
    def is_approved(approval_id: int, db: Optional[Session] = None) -> bool:
        """Checks if a previously submitted action has been granted approval."""
        owns_db = False
        if db is None:
            db = SessionLocal()
            owns_db = True

        try:
            approval = db.query(Approval).filter(Approval.id == approval_id).first()
            if approval and approval.status == "approved":
                return True
            return False
        finally:
            if owns_db:
                db.close()

    @staticmethod
    def resolve_approval(
        approval_id: int,
        decision: str,
        db: Optional[Session] = None
    ) -> bool:
        """Sets status to 'approved' or 'rejected' with timestamp."""
        if decision not in ("approved", "rejected"):
            raise ValueError("Decision must be 'approved' or 'rejected'")

        owns_db = False
        if db is None:
            db = SessionLocal()
            owns_db = True

        try:
            approval = db.query(Approval).filter(Approval.id == approval_id).first()
            if not approval:
                return False

            approval.status = decision
            approval.resolved_at = datetime.utcnow()
            db.commit()

            logger.info(f"Approval request #{approval_id} ({approval.action_type}) marked as {decision.upper()}")
            return True
        finally:
            if owns_db:
                db.close()

    @staticmethod
    def get_pending_approvals(db: Optional[Session] = None) -> List[Approval]:
        """Returns list of all pending approval requests."""
        owns_db = False
        if db is None:
            db = SessionLocal()
            owns_db = True

        try:
            return db.query(Approval).filter(Approval.status == "pending").order_by(Approval.created_at.asc()).all()
        finally:
            if owns_db:
                db.close()

    @staticmethod
    def get_all_approvals(limit: int = 50, db: Optional[Session] = None) -> List[Approval]:
        """Returns history of all approval requests."""
        owns_db = False
        if db is None:
            db = SessionLocal()
            owns_db = True

        try:
            return db.query(Approval).order_by(Approval.created_at.desc()).limit(limit).all()
        finally:
            if owns_db:
                db.close()


default_approval_manager = ApprovalManager()
