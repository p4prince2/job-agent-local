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


    def test_generate_variation(self):
        """Verify generating an alternative variation / re-roll creates a new linked draft."""
        orig_draft = Draft(
            platform="linkedin",
            type="original",
            status="draft",
            content="Original deep dive into fine-tuning parameters and loss curves.",
            source_ref="Test Source #1"
        )
        self.db.add(orig_draft)
        self.db.commit()
        self.db.refresh(orig_draft)

        res = self.agent.generate_variation(orig_draft.id, db=self.db, angle_hint="Focus on production latency")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["original_id"], orig_draft.id)
        
        var_draft = self.db.query(Draft).filter(Draft.id == res["new_draft_id"]).first()
        self.assertIsNotNone(var_draft)
        self.assertEqual(var_draft.platform, "linkedin")
        self.assertEqual(var_draft.type, "original_variation")
        self.assertIn("Fine-tuning vs RAG", var_draft.content)

    def test_adapt_draft_platform(self):
        """Verify cross-platform adaptation (e.g. LinkedIn -> X or Medium)."""
        li_draft = Draft(
            platform="linkedin",
            type="original",
            status="draft",
            content="Extensive engineering post discussing memory bandwidth tradeoffs in modern LLM serving.",
            source_ref="Test Source #2"
        )
        self.db.add(li_draft)
        self.db.commit()
        self.db.refresh(li_draft)

        res = self.agent.adapt_draft_platform(li_draft.id, target_platform="x", db=self.db)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["target_platform"], "x")

        adapted = self.db.query(Draft).filter(Draft.id == res["new_draft_id"]).first()
        self.assertIsNotNone(adapted)
        self.assertEqual(adapted.platform, "x")
        self.assertEqual(adapted.type, "adapted_from_linkedin")
        self.assertLessEqual(len(adapted.content), 280)

    def test_polish_draft_tone(self):
        """Verify tone polishing creates a new polished draft with specified style."""
        x_draft = Draft(
            platform="x",
            type="original",
            status="draft",
            content="Multi-agent systems require careful coordination and state checking.",
            source_ref="Test Source #3"
        )
        self.db.add(x_draft)
        self.db.commit()
        self.db.refresh(x_draft)

        res = self.agent.polish_draft_tone(x_draft.id, tone="concise", db=self.db)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["tone"], "concise")

        polished = self.db.query(Draft).filter(Draft.id == res["new_draft_id"]).first()
        self.assertIsNotNone(polished)
        self.assertEqual(polished.platform, "x")
        self.assertEqual(polished.type, "polished_concise")
        self.assertIn("RAG gives fresh context", polished.content)


if __name__ == "__main__":
    unittest.main()
