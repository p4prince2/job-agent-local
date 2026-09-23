"""Tests for Supervisor Agent (per SPEC.md §6)."""

import unittest
from db.session import init_db, SessionLocal
from db.models import Task, AgentRun
from agents.supervisor import default_supervisor


class TestSupervisorAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_routing_rules(self):
        """Verify keyword shortlist and routing logic."""
        # Content cue
        r1 = default_supervisor.route_task("Write a LinkedIn post about AI safety")
        self.assertIn("ContentAgent", r1)

        # GitHub cue
        r2 = default_supervisor.route_task("Audit my GitHub repository code quality")
        self.assertIn("GitHubAgent", r2)

        # Daily Work cue
        r3 = default_supervisor.route_task("Help me plan my GATE prep schedule for today")
        self.assertIn("DailyWorkAgent", r3)

        # Automation cue (Phase 2 stub)
        r4 = default_supervisor.route_task("Automate opening my browser to download a file")
        self.assertIn("AutomationAgent", r4)

        # Compound task
        r5 = default_supervisor.route_task("Review my GitHub repo and draft a LinkedIn post about it")
        self.assertEqual(r5, ["GitHubAgent", "ContentAgent"])

    def test_automation_stub_handling(self):
        """Verify tasks meant for Computer Automation fail clearly per §10 instead of silently."""
        result = default_supervisor.execute_workflow("Open my browser and click a button", db=self.db)
        self.assertEqual(result["pipeline"], ["AutomationAgent"])
        
        # Check step status
        step = result["steps"][0]
        self.assertEqual(step["agent"], "AutomationAgent")
        self.assertEqual(step["output"]["status"], "not_implemented")
        self.assertIn("Phase 1 MVP", step["output"]["message"])


if __name__ == "__main__":
    unittest.main()
