"""SQLAlchemy ORM models for Prince AI Team (per SPEC.md §5)."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Task(Base):
    """Represents a user request and its lifecycle."""
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_input = Column(Text, nullable=False)
    routed_agents = Column(Text, nullable=False, default="[]")  # JSON list of agent names
    status = Column(String(50), nullable=False, default="pending")  # pending, running, completed, failed
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    agent_runs = relationship("AgentRun", back_populates="task", cascade="all, delete-orphan")

    def get_routed_agents(self) -> List[str]:
        try:
            return json.loads(self.routed_agents)
        except Exception:
            return []

    def set_routed_agents(self, agents: List[str]) -> None:
        self.routed_agents = json.dumps(agents)


class AgentRun(Base):
    """Audit trail of one invocation per agent."""
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    agent_name = Column(String(100), nullable=False)
    input = Column(Text, nullable=False)
    output = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="pending")  # pending, running, completed, failed, blocked_on_approval
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)

    task = relationship("Task", back_populates="agent_runs")


class Draft(Base):
    """Every Content Agent output (LinkedIn, Medium, X)."""
    __tablename__ = "drafts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False)  # linkedin, medium, x
    type = Column(String(50), nullable=False)      # original, reply
    status = Column(String(50), nullable=False, default="draft")  # draft, approved, rejected, posted_manually, posted_via_api
    content = Column(Text, nullable=False)
    source_ref = Column(String(255), nullable=True)  # e.g. a github_review id or URL
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class GitHubReview(Base):
    """GitHub Agent's structured reports."""
    __tablename__ = "github_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo = Column(String(255), nullable=False)
    summary_json = Column(Text, nullable=False)  # JSON telemetry & findings
    human_summary = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def get_summary_dict(self) -> Dict[str, Any]:
        try:
            return json.loads(self.summary_json)
        except Exception:
            return {}


class WorkItem(Base):
    """Daily Work Agent tasks and subtasks."""
    __tablename__ = "work_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    project_tag = Column(String(50), nullable=False, default="general")  # gate_prep, ai_ml, github, content
    parent_id = Column(Integer, ForeignKey("work_items.id"), nullable=True)
    status = Column(String(50), nullable=False, default="todo")  # todo, in_progress, done
    priority = Column(String(20), nullable=False, default="medium")  # high, medium, low
    due_date = Column(String(50), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    subtasks = relationship("WorkItem", backref="parent", remote_side=[id])


class Reminder(Base):
    """In-app reminders."""
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    work_item_id = Column(Integer, ForeignKey("work_items.id"), nullable=True)
    remind_at = Column(String(50), nullable=False)
    fired = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Approval(Base):
    """The single gate every risky or external action passes through (§11)."""
    __tablename__ = "approvals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action_type = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    payload_json = Column(Text, nullable=False, default="{}")
    requested_by_agent = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False, default="pending")  # pending, approved, rejected
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    def get_payload(self) -> Dict[str, Any]:
        try:
            return json.loads(self.payload_json)
        except Exception:
            return {}


class Log(Base):
    """Structured log mirrored into SQLite (§14)."""
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String(100), nullable=False)
    level = Column(String(20), nullable=False, default="INFO")
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
