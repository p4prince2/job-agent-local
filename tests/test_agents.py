"""Unit and integration tests for Prince AI Team agents."""

import unittest
from core.database import (
    init_db, list_tasks, list_drafts, list_github_reviews,
    list_pending_approvals, decide_approval, create_task
)
from agents.supervisor import default_supervisor
from agents.content_agent import ContentAgent
from agents.daily_work_agent import DailyWorkAgent
from agents.github_agent import GitHubAgent
from agents.computer_agent import ComputerAgent
from tools.approval_guard import default_approval_guard


class TestPrinceAITeam(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_workflow_planning(self):
        """Verify Supervisor accurately selects agents based on prompt cues."""
        p1 = "Review my GitHub repository and create a LinkedIn post about it"
        plan1 = default_supervisor.plan_workflow(p1)
        self.assertIn("GitHubAgent", plan1)
        self.assertIn("ContentAgent", plan1)

        p2 = "Help me plan my day with 3 hours of GATE prep"
        plan2 = default_supervisor.plan_workflow(p2)
        self.assertIn("DailyWorkAgent", plan2)

        p3 = "Inspect project files and delete temporary data"
        plan3 = default_supervisor.plan_workflow(p3)
        self.assertIn("ComputerAgent", plan3)

    def test_daily_work_agent_tasks(self):
        """Verify DailyWorkAgent creates genuine database tasks."""
        agent = DailyWorkAgent()
        res = agent.execute("Plan a 2-hour study session for GATE Algorithms and Graph Theory")
        self.assertEqual(res["status"], "success")
        self.assertGreater(len(res["tasks_created"]), 0)

        # Verify tasks are in SQLite
        tasks = list_tasks(category="GATE Prep")
        self.assertGreater(len(tasks), 0)

    def test_content_agent_draft_creation(self):
        """Verify ContentAgent generates posts and saves local draft without publishing."""
        agent = ContentAgent()
        res = agent.execute("Write a LinkedIn post explaining the difference between fine-tuning and RAG")
        self.assertEqual(res["status"], "success")
        self.assertFalse(res["published"])
        self.assertIn("draft_id", res)

        # Verify draft exists in DB
        drafts = list_drafts(platform="linkedin")
        self.assertGreater(len(drafts), 0)

    def test_safety_approval_guard(self):
        """Verify dangerous actions are quarantined in the approval queue."""
        agent = ComputerAgent()
        res = agent.execute("Please delete all temporary logs and obsolete files")
        self.assertTrue(res["approval_required"])

        # Check pending approvals
        pending = list_pending_approvals()
        self.assertGreater(len(pending), 0)
        app_id = pending[-1]["id"]

        # Test deciding approval
        success = decide_approval(app_id, "approved")
        self.assertTrue(success)


if __name__ == "__main__":
    unittest.main()
