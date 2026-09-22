"""GitHub inspection tools for Prince AI Team.

Allows inspecting repositories for Prince (https://github.com/p4prince2)
or any other public repo, as well as local git repositories.
"""

import base64
import os
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional
from core.config import GITHUB_USERNAME, GITHUB_TOKEN


class GitHubTools:
    """Tools to inspect and analyze GitHub repositories safely."""

    def __init__(self, username: Optional[str] = None, token: Optional[str] = None):
        self.username = username or GITHUB_USERNAME
        self.token = token or GITHUB_TOKEN
        self.base_url = "https://api.github.com"

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Prince-AI-Team/1.0"
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def list_user_repos(self, username: Optional[str] = None, limit: int = 15) -> List[Dict[str, Any]]:
        """Lists public repositories for the user."""
        user = username or self.username
        url = f"{self.base_url}/users/{user}/repos?sort=updated&per_page={limit}"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=10)
            if resp.status_code == 200:
                repos = resp.json()
                return [{
                    "name": r.get("name"),
                    "full_name": r.get("full_name"),
                    "description": r.get("description") or "No description provided",
                    "html_url": r.get("html_url"),
                    "language": r.get("language") or "Not specified",
                    "stars": r.get("stargazers_count", 0),
                    "forks": r.get("forks_count", 0),
                    "open_issues": r.get("open_issues_count", 0),
                    "updated_at": r.get("updated_at")
                } for r in repos]
            elif resp.status_code == 403:
                return [{"error": "GitHub API rate limit reached. Consider adding GITHUB_TOKEN to .env."}]
            else:
                return [{"error": f"Failed to list repos: HTTP {resp.status_code}"}]
        except Exception as e:
            return [{"error": f"Error fetching repos: {str(e)}"}]

    def get_repo_details(self, repo_name: str, owner: Optional[str] = None) -> Dict[str, Any]:
        """Gets detailed repository metadata."""
        owner = owner or self.username
        if "/" in repo_name:
            full_name = repo_name
        else:
            full_name = f"{owner}/{repo_name}"

        url = f"{self.base_url}/repos/{full_name}"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "full_name": data.get("full_name"),
                    "name": data.get("name"),
                    "description": data.get("description"),
                    "default_branch": data.get("default_branch", "main"),
                    "language": data.get("language"),
                    "topics": data.get("topics", []),
                    "license": (data.get("license") or {}).get("name"),
                    "html_url": data.get("html_url"),
                    "size_kb": data.get("size", 0),
                    "open_issues": data.get("open_issues_count", 0)
                }
            return {"error": f"Repository not found or inaccessible: HTTP {resp.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def get_repo_readme(self, repo_name: str, owner: Optional[str] = None) -> Dict[str, Any]:
        """Fetches and decodes the README of a repo."""
        owner = owner or self.username
        if "/" in repo_name:
            full_name = repo_name
        else:
            full_name = f"{owner}/{repo_name}"

        url = f"{self.base_url}/repos/{full_name}/readme"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                content = base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
                return {
                    "has_readme": True,
                    "filename": data.get("name"),
                    "content": content[:4000]  # truncate to prevent context blowout
                }
            return {"has_readme": False, "message": "No README file found."}
        except Exception as e:
            return {"has_readme": False, "error": str(e)}

    def get_repo_structure(self, repo_name: str, owner: Optional[str] = None) -> Dict[str, Any]:
        """Fetches top-level files/directories and detects key project assets."""
        owner = owner or self.username
        if "/" in repo_name:
            full_name = repo_name
        else:
            full_name = f"{owner}/{repo_name}"

        url = f"{self.base_url}/repos/{full_name}/contents"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=10)
            if resp.status_code == 200:
                items = resp.json()
                files = [item["name"] for item in items if item["type"] == "file"]
                dirs = [item["name"] for item in items if item["type"] == "dir"]

                # Detect key components
                has_tests = any("test" in d.lower() for d in dirs) or any("test" in f.lower() for f in files)
                has_ci = ".github" in dirs
                deps_files = [f for f in files if f in (
                    "requirements.txt", "pyproject.toml", "setup.py",
                    "package.json", "go.mod", "Cargo.toml", "pom.xml"
                )]
                has_license = any("license" in f.lower() for f in files)
                has_docker = any("dockerfile" in f.lower() for f in files)

                return {
                    "top_files": files,
                    "top_dirs": dirs,
                    "has_tests": has_tests,
                    "has_ci_workflows": has_ci,
                    "dependency_files": deps_files,
                    "has_license": has_license,
                    "has_docker": has_docker
                }
            return {"error": f"Failed to get repo contents: HTTP {resp.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def inspect_local_repo(self, path_str: str) -> Dict[str, Any]:
        """Inspects a local repository on the file system."""
        p = Path(path_str).resolve()
        if not p.exists() or not p.is_dir():
            return {"error": f"Path '{path_str}' does not exist or is not a directory."}

        files = []
        dirs = []
        try:
            for item in p.iterdir():
                if item.name.startswith(".") and item.name != ".github":
                    continue
                if item.is_file():
                    files.append(item.name)
                elif item.is_dir():
                    dirs.append(item.name)

            readme_content = ""
            for readme_name in ("README.md", "readme.md", "README.txt", "README"):
                readme_path = p / readme_name
                if readme_path.exists():
                    readme_content = readme_path.read_text(encoding="utf-8", errors="replace")[:4000]
                    break

            has_tests = any("test" in d.lower() for d in dirs) or any("test" in f.lower() for f in files)
            deps_files = [f for f in files if f in (
                "requirements.txt", "pyproject.toml", "setup.py",
                "package.json", "go.mod", "Cargo.toml"
            )]

            return {
                "is_local": True,
                "path": str(p),
                "top_files": files,
                "top_dirs": dirs,
                "has_readme": bool(readme_content),
                "readme_snippet": readme_content[:1500],
                "has_tests": has_tests,
                "dependency_files": deps_files
            }
        except Exception as e:
            return {"error": f"Error inspecting local directory: {str(e)}"}


# Singleton instance
default_github_tools = GitHubTools()
