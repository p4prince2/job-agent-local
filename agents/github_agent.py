"""GitHub Agent for Prince AI Team (per SPEC.md §8).

Read-only repository auditor for Prince (https://github.com/p4prince2).
Inspects repo tree, README, tests, CI workflows, and dependency manifests.
Saves structured JSON and human-readable reports to `github_reviews`.
"""

import json
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from config import GITHUB_USERNAME
from db.models import GitHubReview
from db.session import SessionLocal
from llm import default_provider
from llm.base import LLMProvider
from tools.github_tools import default_github_tools
from logging_utils.logger import get_logger

logger = get_logger("GitHubAgent")

GITHUB_AGENT_PROMPT = """You are the GITHUB AUDIT & ARCHITECTURE AGENT for Prince's AI team.
Prince is an AI/ML engineer (GitHub: https://github.com/p4prince2).

Your core responsibilities:
1. Audit project structure, README completeness, dependencies, test suites, and CI/CD.
2. Identify code quality issues, missing tests, or architecture bottlenecks.
3. Suggest concrete, step-by-step improvements.
4. Recommend a clean Git branch name for the improvements (e.g. `improvements/code-quality-and-tests`).

Structure your review:
### 1. Executive Summary & Health Score (/10)
### 2. Architecture & File Organization
### 3. Dependencies & Tooling
### 4. Testing & CI/CD Status
### 5. Priority Action Items
### 6. Recommended Branch Name
"""


class GitHubAgent:
    """Specialized read-only GitHub repository inspector."""

    def __init__(self, llm: Optional[LLMProvider] = None):
        self.name = "GitHubAgent"
        self.role = "GitHub Repository & Code Architecture Auditor"
        self.llm = llm or default_provider
        self.github_tools = default_github_tools

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None, db: Optional[Session] = None) -> Dict[str, Any]:
        """Audits target repository, produces structured and human report, and saves to github_reviews."""
        logger.info(f"GitHubAgent executing: {task[:80]}...")
        owns_db = False
        if db is None:
            db = SessionLocal()
            owns_db = True

        try:
            repo_target = self._resolve_target_repo(task, context)
            logger.info(f"Target repository identified as: {repo_target}")

            is_local = repo_target.startswith(".") or ("/" in repo_target and "\\" in repo_target) or repo_target.startswith("c:")

            if is_local:
                local_info = self.github_tools.inspect_local_repo(repo_target)
                repo_name = f"Local: {repo_target}"
                telemetry = local_info
                readme_text = local_info.get("readme_snippet", "")
            else:
                repo_info = self.github_tools.get_repo_details(repo_target)
                readme_info = self.github_tools.get_repo_readme(repo_target)
                structure_info = self.github_tools.get_repo_structure(repo_target)

                repo_name = repo_info.get("name") or repo_target
                telemetry = {
                    "repo_metadata": repo_info,
                    "structure": structure_info,
                    "has_readme": readme_info.get("has_readme", False)
                }
                readme_text = readme_info.get("content", "No README available")[:2500]

            prompt = f"""
Audit the following repository for Prince:
Target: {repo_name}

Telemetry:
{json.dumps(telemetry, indent=2)}

README Excerpt:
{readme_text}

Task Request:
{task}

Provide your structured architectural review and actionable recommendations.
"""
            review_text = self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=GITHUB_AGENT_PROMPT,
                temperature=0.6
            )

            # Store in github_reviews table
            review_record = GitHubReview(
                repo=repo_name,
                summary_json=json.dumps(telemetry),
                human_summary=review_text,
            )
            db.add(review_record)
            db.commit()
            db.refresh(review_record)
            logger.info(f"Saved GitHub review #{review_record.id} for {repo_name}")

            return {
                "agent": self.name,
                "status": "success",
                "review_id": review_record.id,
                "repo": repo_name,
                "telemetry": telemetry,
                "summary": review_text,
                "proposed_branch": "improvements/code-quality-and-tests"
            }
        finally:
            if owns_db:
                db.close()

    def _resolve_target_repo(self, task: str, context: Optional[Dict[str, Any]]) -> str:
        """Determines target repository name or path."""
        if context and context.get("repo"):
            return context["repo"]

        words = task.split()
        for w in words:
            if "github.com/" in w:
                return "/".join(w.rstrip("/").split("github.com/")[-1].split("/")[:2])
            if "/" in w and not w.startswith("http"):
                return w.strip(",.?!")

        # Check public repos
        repos = self.github_tools.list_user_repos(limit=3)
        if repos and isinstance(repos, list) and not repos[0].get("error"):
            return repos[0]["name"]

        return "prince-ai-team"
