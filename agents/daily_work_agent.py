"""Daily Work Agent for Prince AI Team (per SPEC.md §9).

Manages work_items tagged by project (gate_prep, ai_ml, github, content),
decomposes large goals into prioritized subtasks, and tracks in-app reminders.
Never falsely claims an OS notification was set.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from db.models import WorkItem, Reminder
from db.session import SessionLocal
from llm import default_provider
from llm.base import LLMProvider
from logging_utils.logger import get_logger

logger = get_logger("DailyWorkAgent")

DAILY_WORK_PROMPT = """You are the DAILY WORK AGENT for Prince.
Prince focuses on:
- GATE Prep (gate_prep): CS fundamentals, algorithms, math, mock tests.
- AI/ML Projects (ai_ml): Model training, fine-tuning, RAG, agents, evaluations.
- GitHub Work (github): Repo maintenance, code quality, unit testing, docs.
- Content Creation (content): LinkedIn posts, Medium articles, X threads.

When asked to plan a day or break down a goal:
1. Provide a realistic time-blocked schedule.
2. Produce 2-4 concrete subtasks.
3. For each subtask, format cleanly:
   - Title: Clear, actionable title
   - Tag: exactly one of [gate_prep, ai_ml, github, content]
   - Priority: [high, medium, low]
   - Estimated Duration

Remember: Any reminder you propose is IN-APP ONLY (viewable on the dashboard).
"""


class DailyWorkAgent:
    """Specialized task manager, day planner, and goal breakdown agent."""

    def __init__(self, llm: Optional[LLMProvider] = None):
        self.name = "DailyWorkAgent"
        self.role = "Daily Work & Goal Breakdown Specialist"
        self.llm = llm or default_provider

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None, db: Optional[Session] = None) -> Dict[str, Any]:
        """Plans schedule, breaks down goals, and saves work_items and in-app reminders."""
        logger.info(f"DailyWorkAgent executing: {task[:80]}...")
        owns_db = False
        if db is None:
            db = SessionLocal()
            owns_db = True

        try:
            # Query existing active work items for context
            active_items = db.query(WorkItem).filter(WorkItem.status != "done").limit(10).all()
            context_summary = f"Current active items in DB: {len(active_items)}"

            prompt = f"""
Request from Prince: {task}
Context: {context_summary}

Please provide:
1. A structured daily schedule / breakdown.
2. 2-4 concrete subtasks to store into the work items tracker.
"""
            response_text = self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=DAILY_WORK_PROMPT,
                temperature=0.6
            )

            # Parse and insert tasks into work_items
            created_items = self._store_work_items(task, response_text, db)

            # Check for in-app reminder
            created_reminders = []
            if "remind" in task.lower():
                rem_time = (datetime.now(timezone.utc) + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
                parent_work_id = created_items[0]["id"] if created_items else None
                rem = Reminder(
                    work_item_id=parent_work_id,
                    remind_at=rem_time,
                    fired=False,
                    created_at=datetime.now(timezone.utc)
                )
                db.add(rem)
                db.commit()
                db.refresh(rem)
                created_reminders.append({
                    "id": rem.id,
                    "remind_at": rem_time,
                    "type": "in-app"
                })
                logger.info(f"Created in-app reminder #{rem.id} for {rem_time}")

            return {
                "agent": self.name,
                "status": "success",
                "plan": response_text,
                "work_items_created": created_items,
                "reminders_created": created_reminders,
                "note": "Reminders are in-app only and will be displayed on the dashboard."
            }
        finally:
            if owns_db:
                db.close()

    def _store_work_items(self, user_request: str, response_text: str, db: Session) -> List[Dict[str, Any]]:
        """Extracts task items from LLM text and saves to SQLite work_items table."""
        req_lower = user_request.lower()
        tag = "gate_prep" if "gate" in req_lower else "ai_ml" if ("ai" in req_lower or "ml" in req_lower) else "github" if "git" in req_lower else "content" if "post" in req_lower else "ai_ml"

        items = []
        for line in response_text.split("\n"):
            clean = line.strip()
            if (clean.startswith(("- Title:", "Title:", "- **Title:**", "**Title:**")) or
                (clean.startswith(("-", "*", "1.", "2.", "3.", "4.")) and len(clean) > 15 and ":" in clean)):
                title_part = clean.split(":")[-1].strip().strip("*\"'")
                if 10 < len(title_part) < 120 and title_part not in [it["title"] for it in items]:
                    prio = "high" if "high" in line.lower() else "medium"
                    items.append({"title": title_part, "tag": tag, "priority": prio})
                    if len(items) >= 4:
                        break

        if not items:
            items.append({"title": f"Execute: {user_request[:60]}", "tag": tag, "priority": "medium"})

        saved = []
        for it in items:
            work_item = WorkItem(
                title=it["title"],
                project_tag=it["tag"],
                priority=it["priority"],
                status="todo",
                created_at=datetime.now(timezone.utc)
            )
            db.add(work_item)
            db.commit()
            db.refresh(work_item)
            saved.append({
                "id": work_item.id,
                "title": work_item.title,
                "project_tag": work_item.project_tag,
                "priority": work_item.priority
            })
            logger.info(f"Saved WorkItem #{work_item.id}: '{work_item.title}' [{work_item.project_tag}]")

        return saved
