"""Base Agent abstraction for Prince AI Team.

All specialized agents inherit from BaseAgent to maintain consistent
logging, LLM invocation, memory, and approval guardrails.
"""

from typing import Any, Dict, List, Optional
from core.llm import LLMClient, default_llm
from core.logger import AgentLogger, get_agent_logger
from tools.approval_guard import default_approval_guard


class BaseAgent:
    """Base class for all agents in the Prince AI Team."""

    def __init__(
        self,
        name: str,
        role: str,
        description: str,
        system_prompt: str,
        llm_client: Optional[LLMClient] = None
    ):
        self.name = name
        self.role = role
        self.description = description
        self.system_prompt = system_prompt
        self.llm = llm_client or default_llm
        self.logger = get_agent_logger(name)

    def log(self, message: str, level: str = "INFO", details: Optional[Dict[str, Any]] = None) -> None:
        """Logs an action to both console and SQLite audit trail."""
        if level == "INFO":
            self.logger.info(message, details)
        elif level == "WARNING":
            self.logger.warning(message, details)
        elif level == "ERROR":
            self.logger.error(message, details)
        elif level == "DEBUG":
            self.logger.debug(message, details)

    def call_llm(
        self,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        json_mode: bool = False
    ) -> str:
        """Invokes the underlying modular LLM (Ollama llama3.2 by default)."""
        messages = list(history or [])
        messages.append({"role": "user", "content": prompt})
        self.log(f"Invoking LLM for {self.name}...", level="DEBUG", details={"prompt_length": len(prompt)})
        response = self.llm.generate(
            messages=messages,
            system_prompt=self.system_prompt,
            temperature=temperature,
            json_mode=json_mode
        )
        return response

    def request_approval(
        self,
        action_type: str,
        description: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Submits an action to the human approval queue if dangerous or publishing."""
        self.log(f"Requesting human approval for {action_type}: {description}", level="WARNING")
        return default_approval_guard.submit_for_approval(
            agent_name=self.name,
            action_type=action_type,
            description=description,
            payload=payload
        )

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Subclasses must implement their execution logic."""
        raise NotImplementedError("Subclasses must implement execute()")
