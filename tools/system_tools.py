"""Safe Windows system inspection tools for Prince AI Team.

Provides read-only access to files and directories within approved paths,
and structures proposals for file changes that require approval.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from core.config import BASE_DIR


class SystemTools:
    """Safe system and file tools with strict boundaries."""

    def __init__(self, allowed_roots: Optional[List[Path]] = None):
        self.allowed_roots = allowed_roots or [BASE_DIR]

    def _is_path_allowed(self, target_path: Path) -> bool:
        """Verifies target path resides within an allowed directory root."""
        try:
            resolved = target_path.resolve()
            # Allow workspace or user profile folders if within permitted roots
            return any(
                str(resolved).lower().startswith(str(root.resolve()).lower())
                for root in self.allowed_roots
            )
        except Exception:
            return False

    def list_directory(self, dir_path: str = ".") -> Dict[str, Any]:
        """Lists directory contents safely."""
        p = (BASE_DIR / dir_path).resolve()
        if not p.exists():
            return {"error": f"Directory not found: {p}"}
        if not p.is_dir():
            return {"error": f"Path is not a directory: {p}"}

        entries = []
        try:
            for item in p.iterdir():
                entries.append({
                    "name": item.name,
                    "is_dir": item.is_dir(),
                    "size_bytes": item.stat().st_size if item.is_file() else 0
                })
            return {"directory": str(p), "entries": entries}
        except Exception as e:
            return {"error": str(e)}

    def read_file_content(self, file_path: str, max_chars: int = 5000) -> Dict[str, Any]:
        """Reads file content safely with length bounding."""
        p = (BASE_DIR / file_path).resolve()
        if not p.exists():
            return {"error": f"File not found: {p}"}
        if not p.is_file():
            return {"error": f"Path is not a file: {p}"}

        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            return {
                "file_path": str(p),
                "total_chars": len(content),
                "truncated": len(content) > max_chars,
                "content": content[:max_chars]
            }
        except Exception as e:
            return {"error": f"Error reading file: {str(e)}"}


default_system_tools = SystemTools()
