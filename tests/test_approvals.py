"""Tests for Approval Queue & Safety Gate (per SPEC.md §11)."""

import unittest
from db.session import init_db, SessionLocal
from db.models import Approval
from approvals.manager import ApprovalManager, DANGEROUS_ACTIONS


class TestApprovalManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_dangerous_actions_covered(self):
        """Verify all critical actions from §11 require approval."""
        self.assertTrue(ApprovalManager.requires_approval("publish_content"))
        self.assertTrue(ApprovalManager.requires_approval("send_message"))
        self.assertTrue(ApprovalManager.requires_approval("delete_file"))
        self.assertTrue(ApprovalManager.requires_approval("purchase"))
        self.assertTrue(ApprovalManager.requires_approval("modify_system"))
        self.assertTrue(ApprovalManager.requires_approval("github_branch_create"))
        self.assertTrue(ApprovalManager.requires_approval("github_commit"))
        self.assertTrue(ApprovalManager.requires_approval("github_pr_create"))
        self.assertTrue(ApprovalManager.requires_approval("automation_action"))
        self.assertFalse(ApprovalManager.requires_approval("read_readme"))

    def test_approval_lifecycle(self):
        """Verify request -> pending -> resolved flow."""
        res = ApprovalManager.request_approval(
            action_type="delete_file",
            description="Delete temporary build files",
            payload={"files": ["temp.log"]},
            requested_by_agent="TestAgent",
            db=self.db
        )
        app_id = res["approval_id"]
        self.assertEqual(res["status"], "pending_approval")

        # Must not be approved yet
        self.assertFalse(ApprovalManager.is_approved(app_id, db=self.db))

        # Check pending list
        pending = ApprovalManager.get_pending_approvals(db=self.db)
        self.assertTrue(any(p.id == app_id for p in pending))

        # Resolve as approved
        success = ApprovalManager.resolve_approval(app_id, "approved", db=self.db)
        self.assertTrue(success)

        # Now is_approved must be True
        self.assertTrue(ApprovalManager.is_approved(app_id, db=self.db))


if __name__ == "__main__":
    unittest.main()
