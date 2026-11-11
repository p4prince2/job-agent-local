"""Tests for GitHub Agent (per SPEC.md §8)."""

import unittest
from db.session import init_db, SessionLocal
from db.models import GitHubReview
from llm.base import LLMProvider
from agents.github_agent import GitHubAgent


class DummyLLM(LLMProvider):
    def check_status(self):
        return {"online": True, "provider": "dummy"}

    def generate(self, messages, system_prompt=None, temperature=0.7, json_mode=False):
        return """
### 1. Executive Summary & Health Score (9/10)
Solid modern project with clean modular architecture.

### 2. Architecture & File Organization
Well-structured directories separating agents, db, and dashboard.

### 3. Dependencies & Tooling
Standard Python dependencies managed via requirements.txt.

### 4. Testing & CI/CD Status
Unit tests in tests/ covering core business flows.

### 5. Priority Action Items
1. Add more test coverage for edge cases.

### 6. Recommended Branch Name
`feat/architecture-enhancement`
"""


class TestGitHubAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.db = SessionLocal()
        self.agent = GitHubAgent(llm=DummyLLM())

    def tearDown(self):
        self.db.close()

    def test_local_or_mock_repo_audit(self):
        """Verify GitHubAgent inspects directory and writes report to github_reviews."""
        result = self.agent.execute("Review current directory .", db=self.db)
        self.assertEqual(result["status"], "success")
        
        # Verify stored in DB
        rev_id = result["review_id"]
        review = self.db.query(GitHubReview).filter(GitHubReview.id == rev_id).first()
        self.assertIsNotNone(review)
        self.assertTrue(bool(review.human_summary))
        self.assertIn("(.)", result["repo"])

    def test_target_repo_dot_resolution_and_telemetry(self):
        """Verify standalone dot paths resolve cleanly without stripping to empty strings."""
        self.assertEqual(self.agent._resolve_target_repo("Review repository .", None), ".")
        self.assertEqual(self.agent._resolve_target_repo("Audit ./tests.", None), "./tests")
        self.assertEqual(self.agent._resolve_target_repo("Inspect ..", None), "..")

        telemetry = self.agent.github_tools.inspect_local_repo(".")
        self.assertTrue(telemetry.get("is_local"))
        self.assertTrue(telemetry.get("has_tests"))
        self.assertIn("has_env_example", telemetry)
        self.assertIn("has_gitignore", telemetry)
        self.assertIn("test_files", telemetry)
        self.assertGreater(telemetry.get("python_files_count", 0), 5)

    def test_github_write_action_triggers_approval_gate(self):
        """Verify write intents (create branch / open PR) queue safety approvals per §11."""
        from db.models import Approval
        result = self.agent.execute("Review . and create branch feat/new-tests", db=self.db)
        self.assertIn("approval_request", result)
        req = result["approval_request"]
        self.assertEqual(req["status"], "pending_approval")
        self.assertEqual(req["action_type"], "github_branch_create")

        app = self.db.query(Approval).filter(Approval.id == req["approval_id"]).first()
        self.assertIsNotNone(app)
        self.db.delete(app)
        self.db.commit()


if __name__ == "__main__":
    unittest.main()
