"""Abstract LLM Provider interface (per SPEC.md §3)."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class LLMProvider(ABC):
    """Abstract base class for all LLM backends."""

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        json_mode: bool = False
    ) -> str:
        """Generates completion given a list of messages (role, content)."""
        pass

    @abstractmethod
    def check_status(self) -> Dict[str, Any]:
        """Returns provider availability and model details."""
        pass
