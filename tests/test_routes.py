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

    def test_due_reminder_banner_and_snooze(self):
        from db.session import SessionLocal
        from db.models import WorkItem, Reminder
        import uuid

        unique_title = f"Due Mock Test Review {uuid.uuid4().hex[:6]}"
        db = SessionLocal()
        w = WorkItem(title=unique_title, project_tag="gate_prep", priority="high", status="todo")
        db.add(w)
        db.commit()
        db.refresh(w)

        rem = Reminder(work_item_id=w.id, remind_at="2020-01-01 00:00", fired=False)
        db.add(rem)
        db.commit()
        db.refresh(rem)
        rem_id = rem.id
        w_id = w.id
        db.close()

        # 1. Opening homepage triggers and surfaces the due reminder banner with linked WorkItem title
        home_resp = self.client.get("/")
        self.assertEqual(home_resp.status_code, 200)
        self.assertIn("In-App Reminder Due:", home_resp.text)
        self.assertIn(unique_title, home_resp.text)

        # 2. Snooze the reminder via HTMX
        snooze_resp = self.client.post(
            f"/work/reminders/snooze/{rem_id}",
            data={"minutes": "60"},
            headers={"HX-Request": "true"}
        )
        self.assertEqual(snooze_resp.status_code, 200)
        self.assertEqual(snooze_resp.text, "")

        db = SessionLocal()
        rem_snoozed = db.query(Reminder).filter(Reminder.id == rem_id).first()
        self.assertFalse(rem_snoozed.fired)
        # Clean up test records
        db.delete(rem_snoozed)
        work_obj = db.query(WorkItem).filter(WorkItem.id == w_id).first()
        if work_obj:
            db.delete(work_obj)
        db.commit()
        db.close()

    def test_health_badge_endpoint(self):
        with patch("main.default_provider.check_status", return_value={
            "online": True,
            "model": "llama3.2",
            "available_models": ["llama3.2", "qwen3"],
            "message": "Ollama online"
        }):
            online_resp = self.client.get("/api/health-badge")
            self.assertEqual(online_resp.status_code, 200)
            self.assertIn("badge-content", online_resp.text)
            self.assertIn("llama3.2", online_resp.text)

        with patch("main.default_provider.check_status", return_value={
            "online": False,
            "model": "llama3.2",
            "message": "Offline"
        }):
            offline_resp = self.client.get("/api/health-badge")
            self.assertEqual(offline_resp.status_code, 200)
            self.assertIn("badge-automation", offline_resp.text)
            self.assertIn("Offline", offline_resp.text)

    def test_drafts_clean_form_structure_and_work_completed_at(self):
        from db.session import SessionLocal
        from db.models import Draft, WorkItem
        import uuid

        db = SessionLocal()
        d = Draft(platform="linkedin", type="original", status="draft", content="Valid non-nested draft form test")
        db.add(d)
        w = WorkItem(title=f"Complete Timestamp Check {uuid.uuid4().hex[:6]}", project_tag="ai_ml", priority="medium", status="todo")
        db.add(w)
        db.commit()
        db.refresh(d)
        db.refresh(w)
        d_id, w_id = d.id, w.id
        db.close()

        # Verify drafts page uses non-nested form="draft-form-{id}" association
        drafts_resp = self.client.get("/drafts")
        self.assertEqual(drafts_resp.status_code, 200)
        self.assertIn(f'id="draft-form-{d_id}"', drafts_resp.text)
        self.assertIn(f'form="draft-form-{d_id}"', drafts_resp.text)

        # Verify toggling work item records and clears completed_at
        self.client.post(f"/work/toggle/{w_id}", headers={"HX-Request": "true"})
        db = SessionLocal()
        done_item = db.query(WorkItem).filter(WorkItem.id == w_id).first()
        self.assertEqual(done_item.status, "done")
        self.assertIsNotNone(done_item.completed_at)
        db.close()

        self.client.post(f"/work/toggle/{w_id}", headers={"HX-Request": "true"})
        db = SessionLocal()
        undone_item = db.query(WorkItem).filter(WorkItem.id == w_id).first()
        self.assertEqual(undone_item.status, "todo")
        self.assertIsNone(undone_item.completed_at)
        # Cleanup test artifacts
        db.delete(undone_item)
        draft_obj = db.query(Draft).filter(Draft.id == d_id).first()
        if draft_obj:
            db.delete(draft_obj)
        db.commit()
        db.close()

    def test_settings_page_and_model_switch_approval(self):
        from db.session import SessionLocal
        from db.models import Approval
        from llm import default_provider

        orig_model = getattr(default_provider, "model", "llama3.2")
        try:
            with patch("main.default_provider.check_status", return_value={
                "online": True,
                "provider": "ollama",
                "model": orig_model,
                "available_models": [orig_model, "qwen3:latest"],
                "message": "Ollama online"
            }):
                settings_resp = self.client.get("/settings")
                self.assertEqual(settings_resp.status_code, 200)
                self.assertIn("LLM Engine", settings_resp.text)
                self.assertIn("qwen3:latest", settings_resp.text)

            req_resp = self.client.post(
                "/settings/request-model-change",
                data={"new_model": "qwen3:latest"},
                follow_redirects=False
            )
            self.assertEqual(req_resp.status_code, 303)

            db = SessionLocal()
            app = db.query(Approval).filter(
                Approval.action_type == "modify_system",
                Approval.status == "pending"
            ).order_by(Approval.id.desc()).first()
            self.assertIsNotNone(app)
            app_id = app.id
            db.close()

            self.client.post(f"/approvals/resolve/{app_id}", data={"decision": "approved"}, headers={"HX-Request": "true"})
            self.assertEqual(default_provider.model, "qwen3:latest")
        finally:
            default_provider.model = orig_model

    def test_draft_reroll_and_variation_endpoint(self):
        from db.session import SessionLocal
        from db.models import Draft

        db = SessionLocal()
        d = Draft(platform="linkedin", type="original", status="draft", content="Initial draft regarding latency optimizations.")
        db.add(d)
        db.commit()
        db.refresh(d)
        d_id = d.id
        db.close()

        resp = self.client.post(f"/drafts/re-roll/{d_id}", follow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(resp.headers["location"], "/drafts")

        db = SessionLocal()
        variations = db.query(Draft).filter(Draft.type == "original_variation").all()
        self.assertTrue(len(variations) > 0)
        self.assertEqual(variations[-1].platform, "linkedin")
        db.close()

    def test_work_status_filter_and_due_date(self):
        import uuid
        from db.session import SessionLocal
        from db.models import WorkItem

        uid = uuid.uuid4().hex[:6]
        due_val = "2026-12-31"
        create_resp = self.client.post("/work/create", data={
            "title": f"Due Date Task {uid}",
            "project_tag": "gate_prep",
            "priority": "high",
            "due_date": due_val
        }, follow_redirects=False)
        self.assertEqual(create_resp.status_code, 303)

        # Check /work page contains due date and status filters
        page_resp = self.client.get("/work?status=todo")
        self.assertEqual(page_resp.status_code, 200)
        self.assertIn(f"Due Date Task {uid}", page_resp.text)
        self.assertIn(due_val, page_resp.text)
        self.assertIn("status=todo", page_resp.text)
        self.assertIn("status=done", page_resp.text)

        # Export check includes due date
        export_resp = self.client.get("/work/export?tag=gate_prep")
        self.assertEqual(export_resp.status_code, 200)
        self.assertIn(f"(Due: {due_val})", export_resp.text)

    def test_adapt_draft_endpoint(self):
        from db.session import SessionLocal
        from db.models import Draft

        db = SessionLocal()
        d = Draft(platform="linkedin", type="original", status="draft", content="Detailed architecture design for agent safety.")
        db.add(d)
        db.commit()
        db.refresh(d)
        d_id = d.id
        db.close()

        resp = self.client.post(f"/drafts/adapt/{d_id}", data={"target_platform": "x"}, follow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(resp.headers["location"], "/drafts")

        db = SessionLocal()
        adapted = db.query(Draft).filter(Draft.type == "adapted_from_linkedin").all()
        self.assertTrue(len(adapted) > 0)
        self.assertEqual(adapted[-1].platform, "x")
        db.close()

    def test_overdue_work_item_badge(self):
        import uuid
        from db.session import SessionLocal
        from db.models import WorkItem

        uid = uuid.uuid4().hex[:6]
        past_due = "2020-01-01"
        create_resp = self.client.post("/work/create", data={
            "title": f"Overdue Task {uid}",
            "project_tag": "ai_ml",
            "priority": "high",
            "due_date": past_due
        }, follow_redirects=False)
        self.assertEqual(create_resp.status_code, 303)

        page_resp = self.client.get("/work")
        self.assertEqual(page_resp.status_code, 200)
        self.assertIn(f"Overdue Task {uid}", page_resp.text)
        self.assertIn("⚠️ Overdue", page_resp.text)

    def test_github_search_and_telemetry_chips(self):
        import uuid
        import json
        from db.session import SessionLocal
        from db.models import GitHubReview

        uid = uuid.uuid4().hex[:6]
        mock_telemetry = {
            "git_branch": f"feature/{uid}",
            "git_commit": "a1b2c3d4",
            "has_tests": True,
            "test_files": ["test_core.py"],
            "has_ci_workflows": True,
            "ci_workflows": ["ci.yml"],
            "python_files_count": 18,
            "has_readme": True
        }
        db = SessionLocal()
        rev = GitHubReview(
            repo=f"Local: test-repo-{uid}",
            summary_json=json.dumps(mock_telemetry),
            human_summary=f"Architecture audit summary for {uid}"
        )
        db.add(rev)
        db.commit()
        db.refresh(rev)
        db.close()

        # Test search filter matches repo
        search_resp = self.client.get(f"/github?q={uid}")
        self.assertEqual(search_resp.status_code, 200)
        self.assertIn(f"test-repo-{uid}", search_resp.text)
        self.assertIn(f"feature/{uid}", search_resp.text)
        self.assertIn("18 Python files", search_resp.text)

    def test_bulk_resolve_approvals_endpoint(self):
        from approvals.manager import ApprovalManager
        from db.session import SessionLocal

        db = SessionLocal()
        ApprovalManager.request_approval("delete_file", "Bulk action A", requested_by_agent="AgentA", db=db)
        ApprovalManager.request_approval("send_message", "Bulk action B", requested_by_agent="AgentB", db=db)
        db.close()

        resp = self.client.post("/approvals/bulk-resolve", data={"decision": "approved"}, follow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(resp.headers["location"], "/approvals")

        db = SessionLocal()
        pending = ApprovalManager.get_pending_approvals(db=db)
        self.assertEqual(len(pending), 0)
        db.close()

    def test_polish_draft_endpoint(self):
        from db.session import SessionLocal
        from db.models import Draft

        db = SessionLocal()
        d = Draft(platform="linkedin", type="original", status="draft", content="Raw ideas about model routing bottlenecks.")
        db.add(d)
        db.commit()
        db.refresh(d)
        d_id = d.id
        db.close()

        resp = self.client.post(f"/drafts/polish/{d_id}", data={"tone": "concise"}, follow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(resp.headers["location"], "/drafts")

        db = SessionLocal()
        polished = db.query(Draft).filter(Draft.type == "polished_concise").all()
        self.assertTrue(len(polished) > 0)
        db.close()

    def test_work_priority_filtering(self):
        import uuid
        from db.session import SessionLocal
        from db.models import WorkItem

        uid = uuid.uuid4().hex[:6]
        high_title = f"High Prio Task {uid}"
        low_title = f"Low Prio Task {uid}"
        db = SessionLocal()
        db.add(WorkItem(title=high_title, project_tag="gate_prep", priority="high", status="todo"))
        db.add(WorkItem(title=low_title, project_tag="gate_prep", priority="low", status="todo"))
        db.commit()
        db.close()

        resp_high = self.client.get("/work?priority=high")
        self.assertEqual(resp_high.status_code, 200)
        self.assertIn(high_title, resp_high.text)
        self.assertNotIn(low_title, resp_high.text)

    def test_github_compare_page(self):
        import json
        from db.session import SessionLocal
        from db.models import GitHubReview

        db = SessionLocal()
        rev1 = GitHubReview(
            repo="p4prince2/job-agent-local",
            summary_json=json.dumps({
                "git_branch": "main",
                "git_commit": "856ae75",
                "python_files_count": 25,
                "has_tests": True,
                "test_files": ["test_a.py", "test_b.py"],
                "has_ci_workflows": False
            }),
            human_summary="Audit 1 baseline report."
        )
        rev2 = GitHubReview(
            repo="p4prince2/job-agent-local",
            summary_json=json.dumps({
                "git_branch": "feature-audit",
                "git_commit": "f94f4c6",
                "python_files_count": 30,
                "has_tests": True,
                "test_files": ["test_a.py", "test_b.py", "test_c.py"],
                "has_ci_workflows": True,
                "ci_workflows": ["ci.yml"]
            }),
            human_summary="Audit 2 comparison report."
        )
        db.add(rev1)
        db.add(rev2)
        db.commit()
        db.refresh(rev1)
        db.refresh(rev2)
        r1_id, r2_id = rev1.id, rev2.id
        db.close()

        resp = self.client.get(f"/github/compare?id1={r1_id}&id2={r2_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Repository Audit Comparison", resp.text)
        self.assertIn("Audit 1 baseline report", resp.text)
        self.assertIn("Audit 2 comparison report", resp.text)
        self.assertIn("feature-audit", resp.text)

    def test_work_subtask_progress_and_badge(self):
        import uuid
        from db.session import SessionLocal
        from db.models import WorkItem

        uid = uuid.uuid4().hex[:6]
        parent_title = f"Epic Goal {uid}"
        db = SessionLocal()
        parent = WorkItem(title=parent_title, project_tag="general", priority="high", status="todo")
        db.add(parent)
        db.commit()
        db.refresh(parent)

        sub1 = WorkItem(title=f"Subtask 1 {uid}", project_tag="general", priority="medium", status="done", parent_id=parent.id)
        sub2 = WorkItem(title=f"Subtask 2 {uid}", project_tag="general", priority="medium", status="todo", parent_id=parent.id)
        db.add(sub1)
        db.add(sub2)
        db.commit()
        db.refresh(parent)

        prog = parent.get_subtask_progress()
        self.assertEqual(prog["total"], 2)
        self.assertEqual(prog["completed"], 1)
        self.assertEqual(prog["percent"], 50)
        db.close()

        resp = self.client.get("/work")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("1/2 subtasks (50%)", resp.text)

    def test_drafts_x_character_limit_counter(self):
        from db.session import SessionLocal
        from db.models import Draft

        db = SessionLocal()
        long_content = "This is a long tweet that definitely exceeds the standard X (Twitter) limit of 280 characters. " * 5
        d = Draft(platform="x", type="original", status="draft", content=long_content)
        db.add(d)
        db.commit()
        db.close()

        resp = self.client.get("/drafts")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Exceeds 280 limit", resp.text)

    def test_work_export_csv_format(self):
        import uuid
        from db.session import SessionLocal
        from db.models import WorkItem

        uid = uuid.uuid4().hex[:6]
        title = f"Task CSV Test {uid}"
        db = SessionLocal()
        db.add(WorkItem(title=title, project_tag="ai_ml", priority="high", status="todo"))
        db.commit()
        db.close()

        resp = self.client.get("/work/export?tag=ai_ml&format=csv")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "text/csv; charset=utf-8")
        self.assertIn("id,title,project_tag,priority,status,due_date,parent_id,created_at", resp.text)
        self.assertIn(title, resp.text)

    def test_drafts_export_csv_and_read_time(self):
        import uuid
        from db.session import SessionLocal
        from db.models import Draft

        uid = uuid.uuid4().hex[:6]
        body = "Comprehensive architectural overview of local AI multi-agent orchestration. " * 30
        db = SessionLocal()
        d = Draft(platform="medium", type="original", status="draft", content=f"{body} (Ref: {uid})")
        db.add(d)
        db.commit()
        db.close()

        # Test CSV export
        csv_resp = self.client.get("/drafts/export-all?platform=medium&format=csv")
        self.assertEqual(csv_resp.status_code, 200)
        self.assertEqual(csv_resp.headers["content-type"], "text/csv; charset=utf-8")
        self.assertIn("id,platform,type,status,source_ref,content,created_at", csv_resp.text)
        self.assertIn(uid, csv_resp.text)

        # Test read time estimate rendering
        html_resp = self.client.get("/drafts?platform=medium")
        self.assertEqual(html_resp.status_code, 200)
        self.assertIn("min read", html_resp.text)

    def test_tasks_search_and_filter(self):
        import uuid
        from datetime import datetime, timezone
        from db.session import SessionLocal
        from db.models import Task

        uid = uuid.uuid4().hex[:6]
        req_text = f"Audit mission critical gateway {uid}"
        db = SessionLocal()
        t = Task(raw_input=req_text, status="completed", executive_summary=f"Audit completed for {uid}", created_at=datetime.now(timezone.utc))
        db.add(t)
        db.commit()
        db.close()

        resp = self.client.get(f"/tasks?q={uid}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(req_text, resp.text)
        self.assertIn(f"Audit completed for {uid}", resp.text)

    def test_tasks_export_all_md_and_csv(self):
        import uuid
        from datetime import datetime, timezone
        from db.session import SessionLocal
        from db.models import Task

        uid = uuid.uuid4().hex[:6]
        db = SessionLocal()
        t = Task(raw_input=f"Task for export {uid}", status="completed", executive_summary=f"Summary for {uid}", created_at=datetime.now(timezone.utc))
        db.add(t)
        db.commit()
        db.close()

        # Markdown export
        md_resp = self.client.get(f"/tasks/export-all?q={uid}&format=md")
        self.assertEqual(md_resp.status_code, 200)
        self.assertEqual(md_resp.headers["content-type"], "text/markdown; charset=utf-8")
        self.assertIn("Task History Digest", md_resp.text)
        self.assertIn(f"Task for export {uid}", md_resp.text)

        # CSV export
        csv_resp = self.client.get(f"/tasks/export-all?q={uid}&format=csv")
        self.assertEqual(csv_resp.status_code, 200)
        self.assertEqual(csv_resp.headers["content-type"], "text/csv; charset=utf-8")
        self.assertIn("id,raw_input,status,routed_agents,executive_summary,created_at,completed_at", csv_resp.text)
        self.assertIn(f"Task for export {uid}", csv_resp.text)

    def test_tasks_delete_endpoint(self):
        from datetime import datetime, timezone
        from db.session import SessionLocal
        from db.models import Task

        db = SessionLocal()
        t = Task(raw_input="Task to be deleted", status="failed", created_at=datetime.now(timezone.utc))
        db.add(t)
        db.commit()
        db.refresh(t)
        t_id = t.id
        db.close()

        # Test HTMX delete
        del_resp = self.client.post(f"/tasks/delete/{t_id}", headers={"HX-Request": "true"})
        self.assertEqual(del_resp.status_code, 200)
        self.assertEqual(del_resp.text, "")

        db = SessionLocal()
        deleted = db.query(Task).filter(Task.id == t_id).first()
        self.assertIsNone(deleted)
        db.close()

    def test_draft_duplicate_endpoint(self):
        import uuid
        from db.session import SessionLocal
        from db.models import Draft

        uid = uuid.uuid4().hex[:6]
        db = SessionLocal()
        d = Draft(platform="linkedin", type="original", status="draft", content=f"Original high-signal draft {uid}")
        db.add(d)
        db.commit()
        db.refresh(d)
        d_id = d.id
        db.close()

        dup_resp = self.client.post(f"/drafts/duplicate/{d_id}", follow_redirects=False)
        self.assertEqual(dup_resp.status_code, 303)

        db = SessionLocal()
        copies = db.query(Draft).filter(Draft.type == "original_copy").all()
        self.assertTrue(any(uid in c.content for c in copies))
        db.close()

    def test_work_complete_all_endpoint(self):
        import uuid
        from db.session import SessionLocal
        from db.models import WorkItem

        uid = uuid.uuid4().hex[:6]
        tag_name = f"tag_{uid}"
        db = SessionLocal()
        w1 = WorkItem(title=f"Sub-goal A {uid}", project_tag=tag_name, priority="high", status="todo")
        w2 = WorkItem(title=f"Sub-goal B {uid}", project_tag=tag_name, priority="low", status="todo")
        db.add(w1)
        db.add(w2)
        db.commit()
        db.close()

        resp = self.client.post("/work/complete-all", data={"tag": tag_name}, follow_redirects=False)
        self.assertEqual(resp.status_code, 303)

        db = SessionLocal()
        items = db.query(WorkItem).filter(WorkItem.project_tag == tag_name).all()
        self.assertEqual(len(items), 2)
        self.assertTrue(all(it.status == "done" for it in items))
        self.assertTrue(all(it.completed_at is not None for it in items))
        db.close()

    def test_approvals_search_and_action_type_filter(self):
        import uuid
        from db.session import SessionLocal
        from approvals.manager import ApprovalManager

        uid = uuid.uuid4().hex[:6]
        desc1 = f"Delete config backup {uid}"
        desc2 = f"Post announcement update {uid}"
        db = SessionLocal()
        ApprovalManager.request_approval("delete_file", desc1, requested_by_agent="AgentDel", db=db)
        ApprovalManager.request_approval("publish_post", desc2, requested_by_agent="AgentPub", db=db)
        db.close()

        # Filter by action type
        resp_act = self.client.get("/approvals?action_type=delete_file")
        self.assertEqual(resp_act.status_code, 200)
        self.assertIn(desc1, resp_act.text)
        self.assertNotIn(desc2, resp_act.text)

        # Filter by keyword search
        resp_q = self.client.get(f"/approvals?q={uid}")
        self.assertEqual(resp_q.status_code, 200)
        self.assertIn(desc1, resp_q.text)
        self.assertIn(desc2, resp_q.text)

    def test_approvals_export_csv_and_md(self):
        import uuid
        from db.session import SessionLocal
        from approvals.manager import ApprovalManager

        uid = uuid.uuid4().hex[:6]
        desc = f"Critical safety action {uid}"
        db = SessionLocal()
        ApprovalManager.request_approval("modify_system", desc, requested_by_agent="TestAgent", db=db)
        db.close()

        # Test CSV export
        csv_resp = self.client.get(f"/approvals/export?q={uid}&format=csv")
        self.assertEqual(csv_resp.status_code, 200)
        self.assertEqual(csv_resp.headers["content-type"], "text/csv; charset=utf-8")
        self.assertIn("id,action_type,requested_by_agent,description,status,created_at,resolved_at", csv_resp.text)
        self.assertIn(desc, csv_resp.text)

        # Test MD export
        md_resp = self.client.get(f"/approvals/export?q={uid}&format=md")
        self.assertEqual(md_resp.status_code, 200)
        self.assertEqual(md_resp.headers["content-type"], "text/markdown; charset=utf-8")
        self.assertIn(desc, md_resp.text)

    def test_settings_db_storage_telemetry(self):
        resp = self.client.get("/settings")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("SQLite Storage &amp; Record Telemetry", resp.text)
        self.assertIn("KB", resp.text)
        self.assertIn("Tasks", resp.text)
        self.assertIn("Drafts", resp.text)
        self.assertIn("Work Items", resp.text)

    def test_logs_export_csv_and_txt(self):
        import uuid
        from db.session import SessionLocal
        from db.models import Log

        uid = uuid.uuid4().hex[:6]
        msg = f"Auditing subsystem logger {uid}"
        db = SessionLocal()
        db.add(Log(agent_name="TestAgent", level="INFO", message=msg))
        db.commit()
        db.close()

        # Test TXT export
        txt_resp = self.client.get(f"/logs/export?q={uid}&format=txt")
        self.assertEqual(txt_resp.status_code, 200)
        self.assertIn("text/plain", txt_resp.headers["content-type"])
        self.assertIn(msg, txt_resp.text)

        # Test CSV export
        csv_resp = self.client.get(f"/logs/export?q={uid}&format=csv")
        self.assertEqual(csv_resp.status_code, 200)
        self.assertEqual(csv_resp.headers["content-type"], "text/csv; charset=utf-8")
        self.assertIn("id,created_at,level,agent_name,message", csv_resp.text)
        self.assertIn(msg, csv_resp.text)

    def test_reroll_draft_with_angle_hint(self):
        import uuid
        from db.session import SessionLocal
        from db.models import Draft

        uid = uuid.uuid4().hex[:6]
        db = SessionLocal()
        d = Draft(platform="linkedin", type="original", status="draft", content=f"Initial technical post about caching {uid}")
        db.add(d)
        db.commit()
        db.refresh(d)
        d_id = d.id
        db.close()

        resp = self.client.post(f"/drafts/re-roll/{d_id}", data={"angle_hint": "contrarian_take"}, follow_redirects=False)
        self.assertEqual(resp.status_code, 303)

        db = SessionLocal()
        variations = db.query(Draft).filter(Draft.type == "original_variation").all()
        self.assertTrue(len(variations) > 0)
        db.close()

    def test_settings_backup_endpoint(self):
        resp = self.client.get("/settings/backup")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/x-sqlite3", resp.headers.get("content-type", ""))
        self.assertIn("attachment; filename=", resp.headers.get("content-disposition", ""))
        self.assertIn("prince_ai_team_backup_", resp.headers.get("content-disposition", ""))
        self.assertTrue(len(resp.content) > 0)

    def test_work_subtask_manual_add(self):
        import uuid
        from db.session import SessionLocal
        from db.models import WorkItem

        uid = uuid.uuid4().hex[:6]
        db = SessionLocal()
        parent = WorkItem(title=f"Parent Goal {uid}", project_tag="gate_prep", priority="high", status="todo")
        db.add(parent)
        db.commit()
        db.refresh(parent)
        p_id = parent.id
        db.close()

        # Add valid subtask
        resp = self.client.post(
            f"/work/subtasks/add/{p_id}",
            data={"title": f"Subtask Step 1 {uid}", "priority": "high", "due_date": "2026-12-01"},
            follow_redirects=False
        )
        self.assertEqual(resp.status_code, 303)

        db = SessionLocal()
        child = db.query(WorkItem).filter(WorkItem.parent_id == p_id).first()
        self.assertIsNotNone(child)
        self.assertEqual(child.title, f"Subtask Step 1 {uid}")
        self.assertEqual(child.project_tag, "gate_prep")
        self.assertEqual(child.priority, "high")
        self.assertEqual(child.due_date, "2026-12-01")
        db.close()

        # Reject empty title
        bad_resp = self.client.post(
            f"/work/subtasks/add/{p_id}",
            data={"title": "   ", "priority": "medium"},
            follow_redirects=False
        )
        self.assertEqual(bad_resp.status_code, 400)

        # Reject non-existent parent
        missing_resp = self.client.post(
            "/work/subtasks/add/999999",
            data={"title": "Invalid Child"},
            follow_redirects=False
        )
        self.assertEqual(missing_resp.status_code, 404)

    def test_work_priority_cycle(self):
        import uuid
        from db.session import SessionLocal
        from db.models import WorkItem

        uid = uuid.uuid4().hex[:6]
        db = SessionLocal()
        item = WorkItem(title=f"Task to Cycle {uid}", project_tag="ai_ml", priority="low", status="todo")
        db.add(item)
        db.commit()
        db.refresh(item)
        item_id = item.id
        db.close()

        # low -> medium
        r1 = self.client.post(f"/work/priority/cycle/{item_id}", follow_redirects=False)
        self.assertEqual(r1.status_code, 303)
        db = SessionLocal()
        i1 = db.query(WorkItem).filter(WorkItem.id == item_id).first()
        self.assertEqual(i1.priority, "medium")
        db.close()

        # medium -> high
        r2 = self.client.post(f"/work/priority/cycle/{item_id}", follow_redirects=False)
        self.assertEqual(r2.status_code, 303)
        db = SessionLocal()
        i2 = db.query(WorkItem).filter(WorkItem.id == item_id).first()
        self.assertEqual(i2.priority, "high")
        db.close()

        # high -> low
        r3 = self.client.post(f"/work/priority/cycle/{item_id}", follow_redirects=False)
        self.assertEqual(r3.status_code, 303)
        db = SessionLocal()
        i3 = db.query(WorkItem).filter(WorkItem.id == item_id).first()
        self.assertEqual(i3.priority, "low")
        db.close()

    def test_settings_self_test_endpoint(self):
        resp = self.client.post("/settings/self-test")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("System Diagnostics Report", resp.text)
        self.assertIn("SQLite Database", resp.text)
        self.assertIn("LLM Engine", resp.text)
        self.assertIn("Storage & I/O", resp.text)
        self.assertIn("Safety Gate", resp.text)

    def test_work_due_filter_overdue_today_upcoming(self):
        import uuid
        from datetime import datetime, timezone, timedelta
        from db.session import SessionLocal
        from db.models import WorkItem

        uid = uuid.uuid4().hex[:6]
        now = datetime.now(timezone.utc)
        yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        today_str = now.strftime("%Y-%m-%d")
        tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

        db = SessionLocal()
        w_overdue = WorkItem(title=f"Overdue Task {uid}", project_tag="ai_ml", due_date=yesterday_str, status="todo")
        w_today = WorkItem(title=f"Today Task {uid}", project_tag="ai_ml", due_date=today_str, status="todo")
        w_upcoming = WorkItem(title=f"Upcoming Task {uid}", project_tag="ai_ml", due_date=tomorrow_str, status="todo")
        db.add_all([w_overdue, w_today, w_upcoming])
        db.commit()
        db.close()

        # Query overdue
        r_overdue = self.client.get(f"/work?q={uid}&due=overdue")
        self.assertEqual(r_overdue.status_code, 200)
        self.assertIn(f"Overdue Task {uid}", r_overdue.text)
        self.assertNotIn(f"Upcoming Task {uid}", r_overdue.text)

        # Query today
        r_today = self.client.get(f"/work?q={uid}&due=today")
        self.assertEqual(r_today.status_code, 200)
        self.assertIn(f"Today Task {uid}", r_today.text)
        self.assertNotIn(f"Overdue Task {uid}", r_today.text)

        # Query upcoming
        r_upcoming = self.client.get(f"/work?q={uid}&due=upcoming")
        self.assertEqual(r_upcoming.status_code, 200)
        self.assertIn(f"Upcoming Task {uid}", r_upcoming.text)
        self.assertNotIn(f"Overdue Task {uid}", r_upcoming.text)

    def test_task_and_agent_run_duration_methods(self):
        from datetime import datetime, timezone, timedelta
        from db.models import Task, AgentRun

        t0 = datetime.now(timezone.utc)
        t1 = t0 + timedelta(seconds=4.32)

        task = Task(raw_input="Sample task", created_at=t0, completed_at=t1)
        self.assertEqual(task.get_duration_seconds(), 4.3)

        task_incomplete = Task(raw_input="Pending task", created_at=t0, completed_at=None)
        self.assertIsNone(task_incomplete.get_duration_seconds())

        run = AgentRun(task_id=1, agent_name="GitHubAgent", input="Audit", started_at=t0, finished_at=t1)
        self.assertEqual(run.get_duration_seconds(), 4.3)


if __name__ == "__main__":
    unittest.main()


