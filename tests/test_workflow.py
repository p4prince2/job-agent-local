"""End-to-end integration test of compound multi-agent workflow."""

import unittest
from core.database import init_db, list_drafts, list_github_reviews, get_chat_history
from agents.supervisor import default_supervisor


class TestEndToEndWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_compound_github_content_workflow(self):
        """Test the exact user workflow: Review GitHub project -> Write LinkedIn post."""
        prompt = "Review my GitHub project prince-ai-team and create a LinkedIn post about the improvements."
        result = default_supervisor.execute_workflow(prompt, session_id="test_e2e")

        self.assertEqual(result["status"], "completed")
        self.assertIn("GitHubAgent", result["pipeline"])
        self.assertIn("ContentAgent", result["pipeline"])
        self.assertGreater(len(result["steps"]), 1)
        self.assertTrue(bool(result["final_response"]))

        # Verify DB artifacts
        drafts = list_drafts()
        self.assertGreater(len(drafts), 0)

        reviews = list_github_reviews()
        self.assertGreater(len(reviews), 0)

        history = get_chat_history("test_e2e")
        self.assertGreater(len(history), 0)


if __name__ == "__main__":
    unittest.main()
