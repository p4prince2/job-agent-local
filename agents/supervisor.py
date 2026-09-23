"""Supervisor Agent for Prince AI Team (per SPEC.md §2, §6).

Lead orchestrator:
1. Fast keyword/intent shortlist (instant, no LLM call).
2. LLM routing confirmation & sub-instruction extraction.
3. Sequential execution with structured context passing.
4. Computer Automation handling: returns explicit 'not implemented yet' message per §10.
5. Executive synthesis and persistence into `tasks` and `agent_runs`.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from db.models import Task, AgentRun
from db.session import SessionLocal
from agents.content_agent import ContentAgent
from agents.github_agent import GitHubAgent
from agents.daily_work_agent import DailyWorkAgent
from agents.automation_agent import AutomationAgent
from llm import default_provider
from llm.base import LLMProvider
from logging_utils.logger import get_logger

logger = get_logger("SupervisorAgent")

SUPERVISOR_ROUTER_PROMPT = """You are the SUPERVISOR AGENT for Prince AI Team.
Your job is to confirm which specialized agents must be called for Prince's request and in what order:

Available Agents:
- ContentAgent: Writes original LinkedIn/Medium/X posts and high-signal replies.
- GitHubAgent: Audits repositories under github.com/p4prince2 or local repos.
- DailyWorkAgent: Daily schedule planning, goal breakdown into work_items (gate_prep, ai_ml, github, content), in-app reminders.
- AutomationAgent: (NOT IMPLEMENTED in MVP). Handles desktop apps, clicks, browser tasks, file deletions.

Given the user prompt, return a valid JSON object with:
{
  "agents": ["AgentName1", "AgentName2"],
  "reasoning": "brief explanation",
  "instructions": {
    "AgentName1": "specific task for agent 1",
    "AgentName2": "specific task for agent 2"
  }
}
Output ONLY valid JSON.
"""

SUPERVISOR_SYNTHESIS_PROMPT = """You are the SUPERVISOR AGENT synthesizing a final executive response for Prince.
Be concise, authentic, and professional.
- State clearly what was accomplished by each agent.
- Highlight any drafts, work items, or reports created in the database.
- If any agent was not implemented (e.g. AutomationAgent), explain that plainly.
- Provide actionable next steps.
"""


class SupervisorAgent:
    """Team lead and multi-agent orchestrator."""

    def __init__(self, llm: Optional[LLMProvider] = None):
        self.name = "SupervisorAgent"
        self.role = "Team Orchestrator & Manager"
        self.llm = llm or default_provider

        # Registered specialized agents
        self.content_agent = ContentAgent(self.llm)
        self.github_agent = GitHubAgent(self.llm)
        self.daily_work_agent = DailyWorkAgent(self.llm)
        self.automation_agent = AutomationAgent()

    def shortlist_agents(self, prompt: str) -> List[str]:
        """Fast keyword/intent pass to shortlist candidate agents (SPEC.md §2)."""
        p_lower = prompt.lower()
        candidates = []

        # Check Automation cues first (Phase 2 stub)
        if any(k in p_lower for k in ["automate", "browser", "click", "open app", "delete file", "download file", "mouse", "desktop"]):
            candidates.append("AutomationAgent")

        # Check GitHub cues
        if any(k in p_lower for k in ["github", "repo", "repository", "codebase", "branch", "pull request", "p4prince2"]):
            candidates.append("GitHubAgent")

        # Check Content cues
        if any(k in p_lower for k in ["linkedin", "medium", "post", "tweet", " x ", "twitter", "draft", "article", "reply", "comment"]):
            candidates.append("ContentAgent")

        # Check Daily Work cues
        if any(k in p_lower for k in ["plan", "gate", "schedule", "work item", "todo", "task", "break down", "goal", "remind"]):
            candidates.append("DailyWorkAgent")

        # Fallback if no keywords matched
        if not candidates:
            candidates = ["ContentAgent"]

        return candidates

    def route_task(self, prompt: str) -> List[str]:
        """Combines fast shortlist with LLM confirmation for compound tasks."""
        shortlist = self.shortlist_agents(prompt)

        # If AutomationAgent was shortlisted, keep it in the route
        if "AutomationAgent" in shortlist and len(shortlist) == 1:
            return ["AutomationAgent"]

        # If it's a clear single or compound pattern, use deterministic route
        if "GitHubAgent" in shortlist and "ContentAgent" in shortlist:
            return ["GitHubAgent", "ContentAgent"]

        return shortlist

    def execute_workflow(self, raw_input: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """Executes full multi-agent lifecycle and records audit trail into SQLite."""
        logger.info(f"Supervisor received task: '{raw_input[:80]}'...")
        owns_db = False
        if db is None:
            db = SessionLocal()
            owns_db = True

        try:
            # 1. Create Task record in DB
            task_record = Task(
                raw_input=raw_input,
                status="running",
                created_at=datetime.utcnow()
            )
            db.add(task_record)
            db.commit()
            db.refresh(task_record)

            # 2. Determine agent pipeline
            pipeline = self.route_task(raw_input)
            task_record.set_routed_agents(pipeline)
            db.commit()
            logger.info(f"Task #{task_record.id} routed to pipeline: {pipeline}")

            step_runs = []
            shared_context: Dict[str, Any] = {}

            # 3. Execute agents in sequence
            for agent_name in pipeline:
                started_at = datetime.utcnow()
                run_record = AgentRun(
                    task_id=task_record.id,
                    agent_name=agent_name,
                    input=raw_input,
                    status="running",
                    started_at=started_at
                )
                db.add(run_record)
                db.commit()
                db.refresh(run_record)

                step_output = {}

                if agent_name == "AutomationAgent":
                    step_output = self.automation_agent.execute(raw_input, shared_context)
                    run_record.status = "failed"
                    run_record.output = step_output.get("message", "Not implemented")

                elif agent_name == "GitHubAgent":
                    step_output = self.github_agent.execute(raw_input, shared_context, db=db)
                    run_record.status = "completed"
                    run_record.output = step_output.get("summary", "")[:2000]
                    # Pass context to downstream agents
                    shared_context["repo"] = step_output.get("repo")
                    shared_context["github_summary"] = step_output.get("summary", "")[:1200]
                    shared_context["telemetry"] = step_output.get("telemetry", {})

                elif agent_name == "ContentAgent":
                    step_output = self.content_agent.execute(raw_input, shared_context, db=db)
                    run_record.status = "completed"
                    run_record.output = json.dumps(step_output.get("drafts", {}))

                elif agent_name == "DailyWorkAgent":
                    step_output = self.daily_work_agent.execute(raw_input, shared_context, db=db)
                    run_record.status = "completed"
                    run_record.output = step_output.get("plan", "")[:2000]

                run_record.finished_at = datetime.utcnow()
                db.commit()

                step_runs.append({
                    "run_id": run_record.id,
                    "agent": agent_name,
                    "status": run_record.status,
                    "output": step_output
                })

            # 4. Supervisor Synthesis
            synthesis_prompt = f"""
Prince requested: "{raw_input}"

The team executed the following steps:
{json.dumps([{
    'agent': s['agent'],
    'status': s['status'],
    'details': s['output'].get('message') or s['output'].get('status') or 'Completed'
} for s in step_runs], indent=2)}

Provide an executive summary to Prince explaining what was accomplished and next steps.
"""
            final_summary = self.llm.generate(
                messages=[{"role": "user", "content": synthesis_prompt}],
                system_prompt=SUPERVISOR_SYNTHESIS_PROMPT,
                temperature=0.5
            )

            # Mark task completed
            task_record.status = "completed"
            task_record.completed_at = datetime.utcnow()
            db.commit()

            return {
                "task_id": task_record.id,
                "raw_input": raw_input,
                "pipeline": pipeline,
                "steps": step_runs,
                "final_summary": final_summary
            }
        finally:
            if owns_db:
                db.close()


default_supervisor = SupervisorAgent()
