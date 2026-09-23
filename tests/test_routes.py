"""Tests for FastAPI HTTP routes and HTML rendering (per SPEC.md §13)."""

import unittest
from fastapi.testclient import TestClient
from main import app
from db.session import init_db


class TestFastAPIRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def test_homepage(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Prince AI Team", resp.text)
        self.assertIn("Supervisor Command Center", resp.text)

    def test_tasks_page(self):
        resp = self.client.get("/tasks")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Task History", resp.text)

    def test_drafts_page(self):
        resp = self.client.get("/drafts")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Technical Content Lab", resp.text)

    def test_work_page(self):
        resp = self.client.get("/work")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Work Items", resp.text)

    def test_github_page(self):
        resp = self.client.get("/github")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("GitHub Repository Audits", resp.text)

    def test_approvals_page(self):
        resp = self.client.get("/approvals")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Human Approval", resp.text)

    def test_logs_page(self):
        resp = self.client.get("/logs")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Agent Activity Logs", resp.text)


if __name__ == "__main__":
    unittest.main()
