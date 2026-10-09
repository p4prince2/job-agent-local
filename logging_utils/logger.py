"""Structured Dual Logger for Prince AI Team (per SPEC.md §14).

Writes structured JSON lines to rotating log file and mirrors directly
to the SQLite `logs` table for instant dashboard visibility.
"""

import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from typing import Optional
from config import LOG_DIR, LOG_LEVEL
from db.session import SessionLocal
from db.models import Log

# Setup rotating JSON file logger
LOG_FILE = LOG_DIR / "prince_ai_team.log"
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=3,
    encoding="utf-8"
)
console_handler = logging.StreamHandler()

# Standard python logger
_logger = logging.getLogger("PrinceAITeam")
_logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
_logger.addHandler(file_handler)
_logger.addHandler(console_handler)


def log_event(agent_name: str, message: str, level: str = "INFO") -> None:
    """Logs an event to both the rotating file (as JSON line) and SQLite `logs` table."""
    now = datetime.now(timezone.utc)
    payload = {
        "timestamp": now.isoformat(),
        "agent": agent_name,
        "level": level.upper(),
        "message": message
    }
    # 1. File log
    line = json.dumps(payload)
    if level.upper() == "ERROR":
        _logger.error(line)
    elif level.upper() == "WARNING":
        _logger.warning(line)
    elif level.upper() == "DEBUG":
        _logger.debug(line)
    else:
        _logger.info(line)

    # 2. SQLite log table mirror
    db = SessionLocal()
    try:
        log_entry = Log(
            agent_name=agent_name,
            level=level.upper(),
            message=message,
            created_at=now
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        _logger.error(f"Failed to mirror log to database: {e}")
        db.rollback()
    finally:
        db.close()


class AgentLogger:
    """Scoped logger helper for a specific agent."""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name

    def info(self, message: str) -> None:
        log_event(self.agent_name, message, level="INFO")

    def warning(self, message: str) -> None:
        log_event(self.agent_name, message, level="WARNING")

    def error(self, message: str) -> None:
        log_event(self.agent_name, message, level="ERROR")

    def debug(self, message: str) -> None:
        log_event(self.agent_name, message, level="DEBUG")


def get_logger(agent_name: str) -> AgentLogger:
    return AgentLogger(agent_name)
