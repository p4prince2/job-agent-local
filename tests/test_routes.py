"""Tests for FastAPI HTTP routes and HTML rendering (per SPEC.md §13)."""

import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from agents.supervisor import default_supervisor
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
        with patch.object(
            default_supervisor.github_agent.llm,
            "generate",
            return_value="Mock GitHub Architecture Review for testing."
        ):
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

    def test_metrics_in_homepage(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Tasks Run", resp.text)
        self.assertIn("Content Drafts", resp.text)
        self.assertIn("Active Tasks", resp.text)

    def test_work_item_decomposition(self):
        from db.session import SessionLocal
        from db.models import WorkItem
        db = SessionLocal()
        parent = WorkItem(title="Master Graph Algorithms & Dynamic Programming", project_tag="gate_prep", priority="high", status="todo")
        db.add(parent)
        db.commit()
        db.refresh(parent)
        parent_id = parent.id
        db.close()

        with patch.object(
            default_supervisor.daily_work_agent.llm,
            "generate",
            return_value="- Subtask: Study BFS & DFS traversals | Priority: high\n- Subtask: Solve 5 Dijkstra problems | Priority: medium"
        ):
            resp = self.client.post(f"/work/decompose/{parent_id}", follow_redirects=False)
            self.assertEqual(resp.status_code, 303)

        db = SessionLocal()
        subtasks = db.query(WorkItem).filter(WorkItem.parent_id == parent_id).all()
        self.assertGreaterEqual(len(subtasks), 1)
        self.assertEqual(subtasks[0].project_tag, "gate_prep")
        db.close()

    def test_github_review_repurpose(self):
        from db.session import SessionLocal
        from db.models import GitHubReview, Draft
        db = SessionLocal()
        rev = GitHubReview(
            repo="p4prince2/job-agent-local",
            summary_json='{"status": "ok"}',
            human_summary="Solid local agentic workflow implementation with modular architecture."
        )
        db.add(rev)
        db.commit()
        db.refresh(rev)
        rev_id = rev.id
        db.close()

        mock_content = """### 1. LinkedIn Post
Deep architectural insights from the job-agent-local audit.

### 2. Expanded Medium Article
Exploring local agent pipelines and safety gates.

### 3. Condensed X (Twitter) Post
Local-first agent architectures keep privacy intact.

### 4. Cover Image Generation Prompt
Architecture diagram with SQLite and local LLM icons.
"""
        with patch.object(default_supervisor.content_agent.llm, "generate", return_value=mock_content):
            resp = self.client.post(f"/github/repurpose/{rev_id}", follow_redirects=False)
            self.assertEqual(resp.status_code, 303)

        db = SessionLocal()
        linked_drafts = db.query(Draft).filter(Draft.source_ref.like("%p4prince2/job-agent-local%")).all()
        self.assertGreaterEqual(len(linked_drafts), 1)
        db.close()

    def test_task_export_and_rerun(self):
        from db.session import SessionLocal
        from db.models import Task, AgentRun
        from datetime import datetime, timezone

        db = SessionLocal()
        t = Task(
            raw_input="Test audit task for export and rerun",
            status="completed",
            executive_summary="All pipeline stages succeeded flawlessly.",
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc)
        )
        t.set_routed_agents(["ContentAgent", "GitHubAgent"])
        db.add(t)
        db.commit()
        db.refresh(t)

        run = AgentRun(
            task_id=t.id,
            agent_name="ContentAgent",
            input=t.raw_input,
            output="Generated mock drafts",
            status="completed",
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc)
        )
        db.add(run)
        db.commit()
        t_id = t.id
        db.close()

        # 1. Test Export .md
        export_resp = self.client.get(f"/tasks/export/{t_id}")
        self.assertEqual(export_resp.status_code, 200)
        self.assertIn("Task #", export_resp.text)
        self.assertIn("All pipeline stages succeeded flawlessly.", export_resp.text)
        self.assertIn("Generated mock drafts", export_resp.text)
        self.assertIn("attachment", export_resp.headers.get("content-disposition", ""))

        # 2. Test Rerun
        with patch("main.run_supervisor_task") as mock_runner:
            rerun_resp = self.client.post(f"/tasks/rerun/{t_id}", follow_redirects=False)
            self.assertEqual(rerun_resp.status_code, 303)

        db = SessionLocal()
        newest_task = db.query(Task).order_by(Task.id.desc()).first()
        self.assertEqual(newest_task.raw_input, t.raw_input)
        self.assertEqual(newest_task.status, "running")
        db.close()

    def test_tasks_page_filtering(self):
        resp = self.client.get("/tasks?status=completed")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Task History", resp.text)

    def test_drafts_search_and_export_all(self):
        from db.session import SessionLocal
        from db.models import Draft
        import uuid

        unique_marker = f"UniqueDraft_{uuid.uuid4().hex[:6]}"
        db = SessionLocal()
        d = Draft(
            platform="linkedin",
            type="original",
            status="approved",
            content=f"Engineering breakdown of {unique_marker} in local LLM pipelines."
        )
        db.add(d)
        db.commit()
        db.close()

        # 1. Search drafts
        search_resp = self.client.get(f"/drafts?q={unique_marker}")
        self.assertEqual(search_resp.status_code, 200)
        self.assertIn(unique_marker, search_resp.text)

        # 2. Filter by status
        status_resp = self.client.get("/drafts?status=approved")
        self.assertEqual(status_resp.status_code, 200)
        self.assertIn("APPROVED", status_resp.text)

        # 3. Export all
        export_resp = self.client.get("/drafts/export-all?platform=linkedin")
        self.assertEqual(export_resp.status_code, 200)
        self.assertIn("Content Lab Drafts Digest", export_resp.text)
        self.assertIn("attachment", export_resp.headers.get("content-disposition", ""))

    def test_work_export_and_clear_completed(self):
        from db.session import SessionLocal
        from db.models import WorkItem
        import uuid

        unique_title = f"Task To Be Cleared {uuid.uuid4().hex[:6]}"
        db = SessionLocal()
        w1 = WorkItem(title=unique_title, project_tag="ai_ml", priority="high", status="done")
        w2 = WorkItem(title="Active Keep Task", project_tag="ai_ml", priority="medium", status="todo")
        db.add_all([w1, w2])
        db.commit()
        db.close()

        # 1. Export work checklist
        export_resp = self.client.get("/work/export?tag=ai_ml")
        self.assertEqual(export_resp.status_code, 200)
        self.assertIn("Daily Work & Milestones Checklist", export_resp.text)
        self.assertIn("[x]", export_resp.text)
        self.assertIn("[ ]", export_resp.text)
        self.assertIn("attachment", export_resp.headers.get("content-disposition", ""))

        # 2. Search work items
        filter_resp = self.client.get(f"/work?q={unique_title}")
        self.assertEqual(filter_resp.status_code, 200)
        self.assertIn(unique_title, filter_resp.text)

        # 3. Clear completed
        clear_resp = self.client.post("/work/clear-completed", follow_redirects=False)
        self.assertEqual(clear_resp.status_code, 303)

        db = SessionLocal()
        cleared_item = db.query(WorkItem).filter(WorkItem.title == unique_title).first()
        self.assertIsNone(cleared_item)
        keep_item = db.query(WorkItem).filter(WorkItem.title == "Active Keep Task").first()
        self.assertIsNotNone(keep_item)
        db.close()

    def test_github_delete(self):
        from db.session import SessionLocal
        from db.models import GitHubReview
        db = SessionLocal()
        rev = GitHubReview(repo="test/delete-repo", summary_json="{}", human_summary="Test review to delete")
        db.add(rev)
        db.commit()
        db.refresh(rev)
        rev_id = rev.id
        db.close()

        del_resp = self.client.post(f"/github/delete/{rev_id}", headers={"HX-Request": "true"})
        self.assertEqual(del_resp.status_code, 200)
        self.assertEqual(del_resp.text, "")

        db = SessionLocal()
        found = db.query(GitHubReview).filter(GitHubReview.id == rev_id).first()
        self.assertIsNone(found)
        db.close()

    def test_approvals_export(self):
        export_resp = self.client.get("/approvals/export")
        self.assertEqual(export_resp.status_code, 200)
        self.assertIn("Human Approval & Safety Audit", export_resp.text)
        self.assertIn("attachment", export_resp.headers.get("content-disposition", ""))

    def test_logs_export_and_clear(self):
        from db.session import SessionLocal
        from db.models import Log
        db = SessionLocal()
        test_log = Log(agent_name="TestLogger", level="INFO", message="Unique test log message for export")
        db.add(test_log)
        db.commit()
        db.close()

        # 1. Export logs
        export_resp = self.client.get("/logs/export")
        self.assertEqual(export_resp.status_code, 200)
        self.assertIn("Unique test log message for export", export_resp.text)
        self.assertIn("attachment", export_resp.headers.get("content-disposition", ""))

        # 2. Clear logs
        clear_resp = self.client.post("/logs/clear", follow_redirects=False)
        self.assertEqual(clear_resp.status_code, 303)

        db = SessionLocal()
        count = db.query(Log).count()
        self.assertEqual(count, 0)
        db.close()


if __name__ == "__main__":
    unittest.main()


