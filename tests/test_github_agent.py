"""Tests for GitHub Agent (per SPEC.md §8)."""

import unittest
from db.session import init_db, SessionLocal
from db.models import GitHubReview
from agents.github_agent import GitHubAgent


class TestGitHubAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.db = SessionLocal()
        self.agent = GitHubAgent()

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
