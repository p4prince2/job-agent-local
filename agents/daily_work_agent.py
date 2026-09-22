"""Daily Work Agent for Prince AI Team.

Specialized in planning Prince's day, decomposing high-level goals into
atomic prioritized tasks, and maintaining a persistent SQLite database
across GATE Prep, AI/ML Projects, GitHub Work, and Content Creation.
Never falsely claims a reminder is set unless a database record was created.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from agents.base_agent import BaseAgent
from core.database import create_task, list_tasks, create_reminder, list_reminders
from core.config import TASK_CATEGORIES


DAILY_WORK_PROMPT = f"""You are the DAILY WORK & TASK MANAGEMENT AGENT for Prince.
Prince balances high-stakes preparation and engineering across:
{', '.join(TASK_CATEGORIES)}.

Your core responsibilities:
1. Help Prince plan his daily schedule with realistic time blocks.
2. Decompose large, overwhelming goals (e.g. "Prepare GATE Computer Science algorithms" or "Implement LoRA fine-tuning") into 3-5 concrete, bite-sized tasks.
3. Assign appropriate categories ({', '.join(TASK_CATEGORIES)}) and priorities (high, medium, low).
4. Accurately report what tasks and reminders were stored in the database.
5. STRICT RULE: Never claim a reminder was created unless it was actually saved in the reminders database with a real timestamp.

Format your responses with clear schedule breakdowns, prioritized action lists, and explicit task records.
"""


class DailyWorkAgent(BaseAgent):
    """Specialized task planner, day organizer, and goal decomposition agent."""

    def __init__(self):
        super().__init__(
            name="DailyWorkAgent",
            role="Daily Work & Schedule Planner",
            description="Decomposes goals, manages daily tasks across GATE and AI/ML, and tracks progress in SQLite.",
            system_prompt=DAILY_WORK_PROMPT
        )

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Executes planning request, creates tasks/reminders in SQLite, and returns action plan."""
        self.log(f"Received daily work task: {task[:80]}...")

        # Fetch current pending tasks for context
        current_tasks = list_tasks(status="pending")
        task_summary = f"{len(current_tasks)} pending tasks currently in database."

        prompt = f"""
Prince's Request: {task}

Current Context:
{task_summary}

Please provide:
1. Structured daily plan / schedule breakdown.
2. 2-4 concrete, actionable subtasks to add to the task tracker.
For each subtask, provide:
- Title: concise action title
- Category: choose one of [{', '.join(TASK_CATEGORIES)}]
- Priority: high, medium, or low
- Estimated Duration

3. Optional reminder recommendation if requested.
"""

        response_text = self.call_llm(prompt, temperature=0.6)

        # Parse and persist tasks into SQLite
        created_tasks = self._parse_and_store_tasks(task, response_text)

        # Handle explicit reminder creation if requested
        created_reminders = []
        task_lower = task.lower()
        if "remind" in task_lower or "reminder" in task_lower:
            rem_title = f"Follow-up: {task[:40]}"
            # Set reminder 3 hours from now as a sensible default
            remind_time = (datetime.now() + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
            rem_id = create_reminder(
                title=rem_title,
                remind_at=remind_time,
                task_id=created_tasks[0]["id"] if created_tasks else None
            )
            created_reminders.append({
                "id": rem_id,
                "title": rem_title,
                "remind_at": remind_time,
                "status": "active"
            })
            self.log(f"Created verified reminder #{rem_id} for {remind_time}.")

        return {
            "agent": self.name,
            "status": "success",
            "plan": response_text,
            "tasks_created": created_tasks,
            "reminders_created": created_reminders,
            "active_tasks_count": len(current_tasks) + len(created_tasks)
        }

    def _parse_and_store_tasks(self, user_request: str, response_text: str) -> List[Dict[str, Any]]:
        """Extracts task items from LLM response and creates records in SQLite."""
        tasks_to_add = []

        # Categorize based on keywords in request or response
        category = "General"
        req_lower = user_request.lower()
        if "gate" in req_lower:
            category = "GATE Prep"
        elif "ml" in req_lower or "ai" in req_lower or "model" in req_lower:
            category = "AI/ML Projects"
        elif "git" in req_lower or "repo" in req_lower or "code" in req_lower:
            category = "GitHub Work"
        elif "post" in req_lower or "linkedin" in req_lower or "content" in req_lower:
            category = "Content Creation"

        # Search for numbered or bullet lines
        for line in response_text.split("\n"):
            line_clean = line.strip()
            if (line_clean.startswith(("- Title:", "Title:", "- **Title:**", "**Title:**")) or
                (line_clean.startswith(("-", "*", "1.", "2.", "3.", "4.")) and len(line_clean) > 15 and ":" in line_clean)):
                clean_title = line_clean.split(":")[-1].strip().strip("*\"'")
                if 10 < len(clean_title) < 120 and clean_title not in [t["title"] for t in tasks_to_add]:
                    priority = "high" if "high" in line.lower() else "medium"
                    tasks_to_add.append({
                        "title": clean_title,
                        "category": category,
                        "priority": priority
                    })
                    if len(tasks_to_add) >= 4:
                        break

        # Fallback if specific titles weren't extracted
        if not tasks_to_add:
            tasks_to_add.append({
                "title": f"Execute: {user_request[:60]}",
                "category": category,
                "priority": "medium"
            })

        stored = []
        for t in tasks_to_add:
            tid = create_task(
                title=t["title"],
                description=f"Generated via DailyWorkAgent for: {user_request[:80]}",
                category=t["category"],
                priority=t["priority"]
            )
            stored.append({
                "id": tid,
                "title": t["title"],
                "category": t["category"],
                "priority": t["priority"]
            })
            self.log(f"Created task #{tid}: '{t['title']}' ({t['category']})")

        return stored
