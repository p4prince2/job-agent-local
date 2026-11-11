"""Tests for Daily Work Agent (per SPEC.md §9)."""

import unittest
from db.session import init_db, SessionLocal
from db.models import WorkItem, Reminder
from llm.base import LLMProvider
from agents.daily_work_agent import DailyWorkAgent


class DummyWorkLLM(LLMProvider):
    def check_status(self):
        return {"online": True, "provider": "dummy"}

    def generate(self, messages, system_prompt=None, temperature=0.7, json_mode=False):
        return """
### Daily Breakdown
- Title: GATE Prep: Graph Theory & Shortest Paths (High Priority)
- Title: Review Dijkstra and Bellman-Ford edge cases
- Title: Solve 10 GATE previous year questions
"""


class TestDailyWorkAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.db = SessionLocal()
        self.agent = DailyWorkAgent(llm=DummyWorkLLM())

    def tearDown(self):
        self.db.close()

    def test_goal_breakdown_preserves_colons_and_parent_hierarchy(self):
        """Verify parent goal, child subtasks, priority, tag, and colon preservation."""
        result = self.agent.execute("Plan my GATE study session", db=self.db)
        self.assertEqual(result["status"], "success")
        created = result["work_items_created"]
        self.assertEqual(len(created), 3)

        # First item is Parent Goal; remaining items link to it via parent_id
        parent_info = created[0]
        self.assertIsNone(parent_info["parent_id"])
        self.assertEqual(parent_info["project_tag"], "gate_prep")
        self.assertEqual(parent_info["priority"], "high")
        self.assertIn("GATE Prep: Graph Theory & Shortest Paths", parent_info["title"])

        for child in created[1:]:
            self.assertEqual(child["parent_id"], parent_info["id"])

        # Cleanup created test items
        for item_info in reversed(created):
            obj = self.db.query(WorkItem).filter(WorkItem.id == item_info["id"]).first()
            if obj:
                self.db.delete(obj)
        self.db.commit()

    def test_content_tag_and_in_app_reminder_creation(self):
        """Verify content tag classification and automatic in-app reminder creation."""
        result = self.agent.execute("Draft a LinkedIn article and remind me to review it", db=self.db)
        self.assertEqual(result["status"], "success")
        created = result["work_items_created"]
        reminders = result["reminders_created"]

        self.assertTrue(all(it["project_tag"] == "content" for it in created))
        self.assertEqual(len(reminders), 1)
        self.assertEqual(reminders[0]["type"], "in-app")

        # Cleanup
        for r_info in reminders:
            rem_obj = self.db.query(Reminder).filter(Reminder.id == r_info["id"]).first()
            if rem_obj:
                self.db.delete(rem_obj)
        for item_info in reversed(created):
            obj = self.db.query(WorkItem).filter(WorkItem.id == item_info["id"]).first()
            if obj:
                self.db.delete(obj)
        self.db.commit()


if __name__ == "__main__":
    unittest.main()
