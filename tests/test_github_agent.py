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


if __name__ == "__main__":
    unittest.main()
