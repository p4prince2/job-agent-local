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
        import uuid
        unique_title = f"Test HTMX Task {uuid.uuid4().hex[:6]}"
        create_resp = self.client.post("/work/create", data={"title": unique_title, "project_tag": "ai_ml", "priority": "high"}, follow_redirects=False)
        self.assertEqual(create_resp.status_code, 303)

        from db.session import SessionLocal
        from db.models import WorkItem
        db = SessionLocal()
        item = db.query(WorkItem).filter(WorkItem.title == unique_title).first()
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

    def test_export_draft(self):
        from db.session import SessionLocal
        from db.models import Draft
        db = SessionLocal()
        d = Draft(platform="linkedin", type="original", status="draft", content="Test export content")
        db.add(d)
        db.commit()
        db.refresh(d)
        d_id = d.id
        db.close()

        resp = self.client.get(f"/drafts/export/{d_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Test export content", resp.text)
        self.assertIn("attachment", resp.headers.get("content-disposition", ""))

    def test_github_audit_and_export(self):
        audit_resp = self.client.post("/github/audit", data={"repo": "."}, follow_redirects=False)
        self.assertEqual(audit_resp.status_code, 303)

        from db.session import SessionLocal
        from db.models import GitHubReview
        db = SessionLocal()
        latest_rev = db.query(GitHubReview).order_by(GitHubReview.created_at.desc()).first()
        self.assertIsNotNone(latest_rev)
        rev_id = latest_rev.id
        db.close()

        export_resp = self.client.get(f"/github/export/{rev_id}")
        self.assertEqual(export_resp.status_code, 200)
        self.assertIn("GitHub Audit Review", export_resp.text)

    def test_logs_filtering(self):
        resp = self.client.get("/logs?level=info&q=test")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Agent Activity Logs", resp.text)

    def test_draft_approval_lifecycle(self):
        from db.session import SessionLocal
        from db.models import Draft, Approval
        db = SessionLocal()
        draft = Draft(platform="x", type="repurpose", status="draft", content="Thread on Distributed Training")
        db.add(draft)
        db.commit()
        db.refresh(draft)
        d_id = draft.id
        db.close()

        # 1. Request approval via endpoint
        req_resp = self.client.post(f"/drafts/request-approval/{d_id}", follow_redirects=False)
        self.assertEqual(req_resp.status_code, 303)

        db = SessionLocal()
        approval = db.query(Approval).filter(
            Approval.action_type == "publish_content",
            Approval.status == "pending"
        ).order_by(Approval.id.desc()).first()
        self.assertIsNotNone(approval)
        app_id = approval.id
        self.assertEqual(approval.get_payload().get("draft_id"), d_id)
        db.close()

        # 2. Resolve approval as approved, triggering cascade to Draft
        res_resp = self.client.post(f"/approvals/resolve/{app_id}", data={"decision": "approved"}, headers={"HX-Request": "true"})
        self.assertEqual(res_resp.status_code, 200)

        db = SessionLocal()
        draft_after_resolve = db.query(Draft).filter(Draft.id == d_id).first()
        self.assertEqual(draft_after_resolve.status, "approved")
        db.close()

        # 3. Mark draft as posted manually
        posted_resp = self.client.post(f"/drafts/mark-posted/{d_id}", follow_redirects=False)
        self.assertEqual(posted_resp.status_code, 303)

        db = SessionLocal()
        draft_final = db.query(Draft).filter(Draft.id == d_id).first()
        self.assertEqual(draft_final.status, "posted_manually")
        db.close()

    def test_reminder_lifecycle(self):
        from db.session import SessionLocal
        from db.models import Reminder
        # Create reminder
        create_resp = self.client.post("/work/reminders/create", data={"remind_at": "2026-10-15 15:00"}, follow_redirects=False)
        self.assertEqual(create_resp.status_code, 303)

        db = SessionLocal()
        rem = db.query(Reminder).filter(Reminder.remind_at == "2026-10-15 15:00").order_by(Reminder.id.desc()).first()
        self.assertIsNotNone(rem)
        rem_id = rem.id
        db.close()

        # Delete reminder via HTMX
        del_resp = self.client.post(f"/work/reminders/delete/{rem_id}", headers={"HX-Request": "true"})
        self.assertEqual(del_resp.status_code, 200)
        self.assertEqual(del_resp.text, "")

        db = SessionLocal()
        rem_after = db.query(Reminder).filter(Reminder.id == rem_id).first()
        self.assertIsNone(rem_after)
        db.close()


if __name__ == "__main__":
    unittest.main()

