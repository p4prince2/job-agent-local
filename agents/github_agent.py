"""GitHub Agent for Prince AI Team.

Specialized in reviewing GitHub repositories for Prince (https://github.com/p4prince2),
inspecting code structure, dependencies, READMEs, tests, and recommending
architecture improvements. Never makes destructive git changes without approval.
"""

import json
from typing import Any, Dict, List, Optional
from agents.base_agent import BaseAgent
from core.database import save_github_review
from tools.github_tools import default_github_tools


GITHUB_AGENT_PROMPT = """You are the GITHUB REVIEW & ARCHITECTURE AGENT for Prince's AI team.
Prince is an AI/ML engineer (GitHub: https://github.com/p4prince2).

Your core responsibilities:
1. Review repositories thoroughly: project structure, README completeness, dependency hygiene, tests, CI/CD, and code organization.
2. Identify bugs, architectural bottlenecks, missing unit tests, or unclear documentation.
3. Recommend concrete, step-by-step improvements.
4. Suggest a clean branch name for improvements (e.g. `refactor/modular-pipeline` or `fix/test-coverage`).
5. NEVER make destructive changes, delete repositories, or merge PRs without explicit human approval.

When providing a review, use this clean structure:
### 1. Executive Summary & Health Score (/10)
### 2. Architecture & Code Structure
### 3. Dependencies & Hygiene
### 4. Testing & CI/CD Status
### 5. Priority Improvement Recommendations
### 6. Proposed Git Branch & Action Plan
"""


class GitHubAgent(BaseAgent):
    """Specialized GitHub review and code organization agent."""

    def __init__(self):
        super().__init__(
            name="GitHubAgent",
            role="GitHub Repository Reviewer & Code Architect",
            description="Reviews repositories on github.com/p4prince2, checks code structure, tests, deps, and suggests improvements.",
            system_prompt=GITHUB_AGENT_PROMPT
        )
        self.github = default_github_tools

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Executes repository review by inspecting metadata, files, readme, and generating analysis."""
        self.log(f"Received GitHub task: {task[:80]}...")

        # Parse target repo from task or context
        target_repo = self._detect_repo_target(task, context)
        is_local = target_repo.startswith(".") or "/" in target_repo and "\\" in target_repo or target_repo.startswith("c:")

        repo_info = {}
        readme_info = {}
        structure_info = {}

        if is_local:
            self.log(f"Inspecting local repository path: {target_repo}")
            local_data = self.github.inspect_local_repo(target_repo)
            repo_name = f"Local: {target_repo}"
            repo_url = f"file:///{target_repo}"
            structure_summary = json.dumps(local_data, indent=2)
        else:
            self.log(f"Fetching GitHub data for repo: {target_repo}")
            repo_info = self.github.get_repo_details(target_repo)
            readme_info = self.github.get_repo_readme(target_repo)
            structure_info = self.github.get_repo_structure(target_repo)

            repo_name = repo_info.get("name") or target_repo
            repo_url = repo_info.get("html_url") or f"https://github.com/p4prince2/{target_repo}"

            structure_summary = f"""
Top-level Directories: {structure_info.get('top_dirs', [])}
Top-level Files: {structure_info.get('top_files', [])}
Dependency Files: {structure_info.get('dependency_files', [])}
Tests Found: {structure_info.get('has_tests', False)}
CI Workflows Found: {structure_info.get('has_ci_workflows', False)}
License Present: {structure_info.get('has_license', False)}
Docker Present: {structure_info.get('has_docker', False)}
Open Issues: {repo_info.get('open_issues', 0)}
Default Branch: {repo_info.get('default_branch', 'main')}
"""

        readme_text = readme_info.get("content", "No README found or accessible.")[:2500] if not is_local else local_data.get("readme_snippet", "")

        prompt = f"""
Review the following repository for Prince:
Repository: {repo_name}
URL: {repo_url}

Structural Inspection:
{structure_summary}

README Snippet:
{readme_text}

Task Request:
{task}

Provide your detailed architectural review following the standard format. Include actionable recommendations.
"""

        review_text = self.call_llm(prompt, temperature=0.6)

        # Extract recommendations
        recommendations = self._extract_recommendations(review_text)

        # Save review to SQLite
        review_id = save_github_review(
            repo_name=repo_name,
            repo_url=repo_url,
            summary=review_text[:500] + "...",
            structure_analysis=structure_summary,
            findings=["Structural check completed", f"Tests present: {structure_info.get('has_tests', False)}"],
            recommendations=recommendations
        )
        self.log(f"Saved GitHub review #{review_id} for {repo_name}.", level="INFO")

        return {
            "agent": self.name,
            "status": "success",
            "review_id": review_id,
            "repo_name": repo_name,
            "repo_url": repo_url,
            "structure": structure_info,
            "review": review_text,
            "recommendations": recommendations,
            "proposed_branch": "improvements/code-quality-and-tests"
        }

    def _detect_repo_target(self, task: str, context: Optional[Dict[str, Any]]) -> str:
        """Heuristic to detect repo name in task or context."""
        if context and context.get("repo"):
            return context["repo"]

        # Check for specific words or default to prince-ai-team or most active
        words = task.split()
        for w in words:
            if "github.com/" in w:
                parts = w.rstrip("/").split("github.com/")[-1].split("/")
                return "/".join(parts[:2])
            if "/" in w and not w.startswith("http"):
                return w.strip(",.?!")

        # If user says "my repo" or "my github project", check user repos
        repos = self.github.list_user_repos(limit=3)
        if repos and isinstance(repos, list) and not repos[0].get("error"):
            return repos[0]["name"]

        return "prince-ai-team"

    def _extract_recommendations(self, text: str) -> List[str]:
        """Extracts recommendations from markdown bullets."""
        recs = []
        for line in text.split("\n"):
            if line.strip().startswith(("-", "*", "1.", "2.", "3.", "4.", "5.")):
                clean = line.strip().lstrip("-*0123456789. ")
                if 15 < len(clean) < 200:
                    recs.append(clean)
                    if len(recs) >= 5:
                        break
        return recs or [
            "Add automated unit tests covering core agent functions.",
            "Include GitHub Actions CI pipeline for automated linting and testing.",
            "Enhance README with quickstart command and architecture diagram."
        ]
