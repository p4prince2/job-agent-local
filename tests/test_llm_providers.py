"""Tests for LLM providers (per SPEC.md §3)."""

import unittest
from llm.mock_provider import MockProvider
from llm.base import LLMProvider


class TestLLMProviders(unittest.TestCase):
    def test_mock_provider_status(self):
        provider = MockProvider()
        status = provider.check_status()
        self.assertTrue(status["online"])
        self.assertEqual(status["provider"], "mock")

    def test_mock_provider_original_post_generation(self):
        provider = MockProvider()
        text = provider.generate(
            messages=[{"role": "user", "content": "Write about multi-agent systems"}],
            system_prompt="You are executing the ORIGINAL POST PIPELINE"
        )
        self.assertIn("1. LinkedIn Post", text)
        self.assertIn("2. Expanded Medium Article", text)
        self.assertIn("3. Condensed X (Twitter) Post", text)
        self.assertIn("4. Cover Image Generation Prompt", text)

    def test_mock_provider_reply_generation(self):
        provider = MockProvider()
        text = provider.generate(
            messages=[{"role": "user", "content": "Reply to this post"}],
            system_prompt="REPLY & COMMENT PIPELINE"
        )
        self.assertIn("Option 1", text)


if __name__ == "__main__":
    unittest.main()
