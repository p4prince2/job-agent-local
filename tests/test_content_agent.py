"""Tests for Content Agent (per SPEC.md §7)."""

import unittest
from db.session import init_db, SessionLocal
from db.models import Draft
from agents.content_agent import ContentAgent


class TestContentAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.db = SessionLocal()
        self.agent = ContentAgent()

    def tearDown(self):
        self.db.close()

    def test_original_post_pipeline(self):
        """Verify original post pipeline creates drafts for LinkedIn, Medium, and X."""
        result = self.agent.execute("Write an analysis on fine-tuning vs RAG trade-offs", db=self.db)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["pipeline"], "original")
        
        # Verify drafts exist in database
        d_ids = result["drafts"]
        for key in ["linkedin_id", "medium_id", "x_id"]:
            draft = self.db.query(Draft).filter(Draft.id == d_ids[key]).first()
            self.assertIsNotNone(draft)
            self.assertEqual(draft.status, "draft")

    def test_reply_quality_gate(self):
        """Verify reply pipeline cleans banned patterns (generic praise, hashtags, emoji)."""
        dirty_reply = "Great post! 🚀 I really love this breakdown. #AI #LLM Check out this tradeoff: latency vs throughput."
        cleaned = self.agent._apply_reply_quality_gate(dirty_reply)
        
        self.assertNotIn("🚀", cleaned)
        self.assertNotIn("#AI", cleaned)
        self.assertNotIn("#LLM", cleaned)


if __name__ == "__main__":
    unittest.main()
