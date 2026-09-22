"""Supervisor Agent for Prince AI Team.

Orchestrates all specialized agents, analyzes intent, plans multi-agent workflows,
routes context between agents, and synthesizes unified responses for Prince.
"""

import json
from typing import Any, Dict, List, Optional
from agents.base_agent import BaseAgent
from agents.content_agent import ContentAgent
from agents.github_agent import GitHubAgent
from agents.daily_work_agent import DailyWorkAgent
from agents.computer_agent import ComputerAgent
from core.database import save_chat_message


SUPERVISOR_PROMPT = """You are the SUPERVISOR AGENT and Team Lead for "Prince AI Team".
Your role is to orchestrate a team of 4 specialized AI agents:
1. ContentAgent: Writes LinkedIn/X posts, hooks, AI/ML thought leadership, saves local drafts.
2. GitHubAgent: Reviews github.com/p4prince2 repositories, analyzes code architecture, tests, deps.
3. DailyWorkAgent: Plans daily schedules, breaks down GATE prep & AI/ML goals, tracks tasks.
4. ComputerAgent: Inspects Windows project files, plans automation, enforces human approval.

When a user submits a prompt, you determine:
- Which agents should be called (one or multiple).
- The logical execution sequence (e.g., GitHubAgent first to gather repo insights, then ContentAgent to write a post).
- A unified, friendly, professional executive synthesis summarizing the actions taken, artifacts created, and next steps.
"""


class SupervisorAgent(BaseAgent):
    """Lead orchestrator agent for Prince AI Team."""

    def __init__(self):
        super().__init__(
            name="SupervisorAgent",
            role="Team Orchestrator & Manager",
            description="Coordinates specialized agents, plans multi-step workflows, and delivers final responses.",
            system_prompt=SUPERVISOR_PROMPT
        )
        # Initialize specialized subagents
        self.content_agent = ContentAgent()
        self.github_agent = GitHubAgent()
        self.daily_work_agent = DailyWorkAgent()
        self.computer_agent = ComputerAgent()

    def plan_workflow(self, user_prompt: str) -> List[str]:
        """Determines which agents are required based on intent and keywords."""
        p_lower = user_prompt.lower()
        required_agents = []

        # Check GitHub cues
        is_github = any(k in p_lower for k in [
            "github", "repo", "repository", "code review", "p4prince2", "codebase", "branch", "pull request"
        ])

        # Check Content cues
        is_content = any(k in p_lower for k in [
            "linkedin", "twitter", "tweet", "post", "write a post", "draft", "hook", "social media", "content"
        ])

        # Check Daily Work cues
        is_daily = any(k in p_lower for k in [
            "plan my day", "daily", "schedule", "gate", "task", "todo", "break down", "goal", "remind"
        ])

        # Check Computer Automation cues
        is_computer = any(k in p_lower for k in [
            "file", "folder", "automate", "system", "delete", "cleanup", "directory", "windows"
        ])

        # Sequence planning for multi-agent workflows
        if is_github and is_content:
            # Common compound task: review repo -> write post about it
            required_agents = ["GitHubAgent", "ContentAgent"]
        elif is_daily and is_github:
            required_agents = ["DailyWorkAgent", "GitHubAgent"]
        elif is_github:
            required_agents = ["GitHubAgent"]
        elif is_content:
            required_agents = ["ContentAgent"]
        elif is_daily:
            required_agents = ["DailyWorkAgent"]
        elif is_computer:
            required_agents = ["ComputerAgent"]
        else:
            # General fallback: if unsure, inspect or use Content or Daily work
            required_agents = ["ContentAgent"]

        return required_agents

    def execute_workflow(self, user_prompt: str, session_id: str = "default") -> Dict[str, Any]:
        """Executes the full multi-agent workflow and returns step trace + final answer."""
        self.log(f"Supervisor received prompt: '{user_prompt}'", level="INFO")
        save_chat_message(session_id=session_id, role="user", content=user_prompt)

        # 1. Plan agents
        agents_needed = self.plan_workflow(user_prompt)
        self.log(f"Supervisor planned execution pipeline: {agents_needed}", level="INFO")

        step_results = []
        shared_context = {}

        # 2. Sequential execution with context passing
        for agent_name in agents_needed:
            self.log(f"Dispatching task to {agent_name}...", level="INFO")

            if agent_name == "GitHubAgent":
                res = self.github_agent.execute(user_prompt, shared_context)
                step_results.append({
                    "agent": "GitHubAgent",
                    "role": self.github_agent.role,
                    "status": res.get("status", "success"),
                    "summary": f"Reviewed {res.get('repo_name', 'repository')}",
                    "details": res
                })
                # Pass review highlights forward to subsequent agents
                shared_context["github_summary"] = res.get("review", "")[:1200]
                shared_context["recommendations"] = res.get("recommendations", [])

            elif agent_name == "ContentAgent":
                res = self.content_agent.execute(user_prompt, shared_context)
                step_results.append({
                    "agent": "ContentAgent",
                    "role": self.content_agent.role,
                    "status": res.get("status", "success"),
                    "summary": f"Generated {res.get('platform', 'content')} draft #{res.get('draft_id')}",
                    "details": res
                })
                shared_context["draft_id"] = res.get("draft_id")

            elif agent_name == "DailyWorkAgent":
                res = self.daily_work_agent.execute(user_prompt, shared_context)
                step_results.append({
                    "agent": "DailyWorkAgent",
                    "role": self.daily_work_agent.role,
                    "status": res.get("status", "success"),
                    "summary": f"Created {len(res.get('tasks_created', []))} tasks in SQLite",
                    "details": res
                })

            elif agent_name == "ComputerAgent":
                res = self.computer_agent.execute(user_prompt, shared_context)
                step_results.append({
                    "agent": "ComputerAgent",
                    "role": self.computer_agent.role,
                    "status": res.get("status", "success"),
                    "summary": "Completed safe workspace inspection" if not res.get("approval_required") else "Submitted sensitive action for approval",
                    "details": res
                })

        # 3. Supervisor Synthesizes Final Executive Response
        summary_prompt = f"""
Prince asked: "{user_prompt}"

The team completed the following steps:
{json.dumps([{
    'agent': s['agent'],
    'summary': s['summary'],
    'status': s['status']
} for s in step_results], indent=2)}

Please write a concise, friendly executive summary directly to Prince:
- Acknowledge what was accomplished.
- Mention any drafts, tasks, reviews, or approvals that were created in the database.
- Offer next actionable recommendations.
"""
        synthesis = self.call_llm(summary_prompt, temperature=0.5)

        # Save assistant answer to chat history
        save_chat_message(
            session_id=session_id,
            role="assistant",
            content=synthesis,
            agent_name="SupervisorAgent",
            meta={"pipeline": agents_needed, "step_count": len(step_results)}
        )

        return {
            "user_prompt": user_prompt,
            "pipeline": agents_needed,
            "steps": step_results,
            "final_response": synthesis,
            "status": "completed"
        }


# Singleton default supervisor
default_supervisor = SupervisorAgent()
