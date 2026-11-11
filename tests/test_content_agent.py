"""Tests for Content Agent (per SPEC.md §7)."""

import unittest
from db.session import init_db, SessionLocal
from db.models import Draft
from llm.base import LLMProvider
from agents.content_agent import ContentAgent


class DummyLLM(LLMProvider):
    def check_status(self):
        return {"online": True, "provider": "dummy"}

    def generate(self, messages, system_prompt=None, temperature=0.7, json_mode=False):
        return """
### 1. LinkedIn Post
Fine-tuning vs RAG trade-offs in modern production systems.

### 2. Expanded Medium Article
An extensive analysis of parameter tuning against dynamic retrieval architectures.

### 3. Condensed X (Twitter) Post
RAG gives fresh context; fine-tuning instills domain style. Choose based on latency.

### 4. Cover Image Generation Prompt
Minimalist diagram showing vector retriever beside neural network weights.
"""


class TestContentAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.db = SessionLocal()
        self.agent = ContentAgent(llm=DummyLLM())

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
        self.assertFalse(cleaned.startswith("!"))
        self.assertNotIn("  ", cleaned)


if __name__ == "__main__":
    unittest.main()
