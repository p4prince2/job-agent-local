"""Tests for Web & Social Media Ingestion Tools (per SPEC.md §7)."""

import unittest
from tools.web_tools import WebTools
from agents.supervisor import SupervisorAgent
from llm.mock_provider import MockProvider


class TestWebTools(unittest.TestCase):
    def setUp(self):
        self.tools = WebTools(timeout=5)

    def test_extract_urls(self):
        text = "Check this post: https://x.com/satyanadella/status/2109631106404487523?s=20 and https://github.com/p4prince2"
        urls = self.tools.extract_urls(text)
        self.assertEqual(len(urls), 2)
        self.assertIn("https://x.com/satyanadella/status/2109631106404487523?s=20", urls)
        self.assertIn("https://github.com/p4prince2", urls)

    def test_clean_tweet_html(self):
        html_snippet = '<blockquote class="twitter-tweet"><p lang="en">Today we announce our biggest bet on silicon.<br><br>Scaling Maia family to multi-gigawatt deployments.</p>&mdash; Satya Nadella (@satyanadella) <a href="...">October 12, 2026</a></blockquote>'
        cleaned = self.tools._clean_tweet_html(html_snippet)
        self.assertIn("Today we announce our biggest bet on silicon.", cleaned)
        self.assertIn("Scaling Maia family to multi-gigawatt deployments.", cleaned)
        self.assertNotIn("<blockquote", cleaned)
        self.assertNotIn("<p>", cleaned)
        self.assertNotIn("&mdash;", cleaned)

    def test_supervisor_url_routing(self):
        supervisor = SupervisorAgent(llm=MockProvider())
        url_prompt = "https://x.com/satyanadella/status/2109631106404487523?s=20"
        route = supervisor.route_task(url_prompt)
        self.assertIn("ContentAgent", route)


if __name__ == "__main__":
    unittest.main()
