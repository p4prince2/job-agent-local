"""Centralized logging for Prince AI Team.

Writes formatted logs to both standard console and SQLite database for UI display.
"""

import logging
import sys
from typing import Any, Dict, Optional
from core.database import log_agent_action

# Standard logger setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)


class AgentLogger:
    """Agent-aware logger that records to both Python logging and SQLite."""

    def __init__(self, agent_name: str, session_id: Optional[str] = None):
        self.agent_name = agent_name
        self.session_id = session_id
        self._logger = logging.getLogger(f"PrinceAI.{agent_name}")

    def info(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        self._logger.info(message)
        try:
            log_agent_action(self.agent_name, message, level="INFO",
                             session_id=self.session_id, details=details)
        except Exception:
            pass

    def warning(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        self._logger.warning(message)
        try:
            log_agent_action(self.agent_name, message, level="WARNING",
                             session_id=self.session_id, details=details)
        except Exception:
            pass

    def error(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        self._logger.error(message)
        try:
            log_agent_action(self.agent_name, message, level="ERROR",
                             session_id=self.session_id, details=details)
        except Exception:
            pass

    def debug(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        self._logger.debug(message)
        try:
            log_agent_action(self.agent_name, message, level="DEBUG",
                             session_id=self.session_id, details=details)
        except Exception:
            pass


def get_agent_logger(agent_name: str, session_id: Optional[str] = None) -> AgentLogger:
    """Factory function for an AgentLogger instance."""
    return AgentLogger(agent_name, session_id)
