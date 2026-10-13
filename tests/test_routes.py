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

    def test_api_status(self):
        resp = self.client.get("/api/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["app"], "Prince AI Team")
        self.assertIn("llm", data)
        self.assertIn("pending_approvals", data)

    def test_htmx_work_toggle_and_delete(self):
        create_resp = self.client.post("/work/create", data={"title": "Test HTMX Task", "project_tag": "ai_ml", "priority": "high"}, follow_redirects=False)
        self.assertEqual(create_resp.status_code, 303)

        from db.session import SessionLocal
        from db.models import WorkItem
        db = SessionLocal()
        item = db.query(WorkItem).filter(WorkItem.title == "Test HTMX Task").first()
        self.assertIsNotNone(item)
        item_id = item.id
        db.close()

        toggle_resp = self.client.post(f"/work/toggle/{item_id}", headers={"HX-Request": "true"})
        self.assertEqual(toggle_resp.status_code, 200)
        self.assertIn("line-through", toggle_resp.text)

        del_resp = self.client.post(f"/work/delete/{item_id}", headers={"HX-Request": "true"})
        self.assertEqual(del_resp.status_code, 200)
        self.assertEqual(del_resp.text, "")

    def test_htmx_approval_resolve(self):
        from approvals.manager import ApprovalManager
        from db.session import SessionLocal
        db = SessionLocal()
        res = ApprovalManager.request_approval("delete_file", "Test HTMX approval", requested_by_agent="TestAgent", db=db)
        app_id = res["approval_id"]
        db.close()

        resolve_resp = self.client.post(f"/approvals/resolve/{app_id}", data={"decision": "approved"}, headers={"HX-Request": "true"})
        self.assertEqual(resolve_resp.status_code, 200)
        self.assertIn("approved", resolve_resp.text.lower())


if __name__ == "__main__":
    unittest.main()
