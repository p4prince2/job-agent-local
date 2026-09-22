"""SQLite Database module for Prince AI Team.

Provides persistent storage for tasks, reminders, drafts, reviews,
approval queue, chat history, and detailed agent logs.
"""

import sqlite3
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from core.config import DATABASE_PATH


def get_connection() -> sqlite3.Connection:
    """Returns a SQLite connection configured with row factory."""
    conn = sqlite3.connect(str(DATABASE_PATH), timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initializes all required database tables if they do not exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Daily Tasks
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        category TEXT NOT NULL DEFAULT 'General',
        priority TEXT NOT NULL DEFAULT 'medium',
        status TEXT NOT NULL DEFAULT 'pending',
        due_date TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    # 2. Reminders
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        title TEXT NOT NULL,
        remind_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL,
        FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
    );
    """)

    # 3. Content Drafts (LinkedIn & X)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS content_drafts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        hook_variations TEXT,
        tags TEXT,
        status TEXT NOT NULL DEFAULT 'draft',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    # 4. GitHub Reviews
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS github_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        repo_name TEXT NOT NULL,
        repo_url TEXT NOT NULL,
        summary TEXT NOT NULL,
        structure_analysis TEXT,
        findings_json TEXT,
        recommendations_json TEXT,
        created_at TEXT NOT NULL
    );
    """)

    # 5. Human Approval Queue (Safety Mechanism)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS approval_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_name TEXT NOT NULL,
        action_type TEXT NOT NULL,
        description TEXT NOT NULL,
        payload_json TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,
        decided_at TEXT
    );
    """)

    # 6. Agent Logs (Audit Trail)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agent_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        agent_name TEXT NOT NULL,
        level TEXT NOT NULL DEFAULT 'INFO',
        message TEXT NOT NULL,
        details_json TEXT,
        created_at TEXT NOT NULL
    );
    """)

    # 7. Chat History
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        agent_name TEXT,
        meta_json TEXT,
        created_at TEXT NOT NULL
    );
    """)

    conn.commit()
    conn.close()


# ----------------------------------------------------------------------
# Task Operations
# ----------------------------------------------------------------------

def create_task(title: str, description: str = "", category: str = "General",
                priority: str = "medium", due_date: Optional[str] = None) -> int:
    """Inserts a new task into the database."""
    now = datetime.now().isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tasks (title, description, category, priority, status, due_date, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)
    """, (title, description, category, priority, due_date, now, now))
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id


def list_tasks(category: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves tasks with optional category or status filters."""
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM tasks WHERE 1=1"
    params = []
    if category and category != "All":
        query += " AND category = ?"
        params.append(category)
    if status and status != "All":
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, created_at DESC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def update_task_status(task_id: int, status: str) -> bool:
    """Updates task status ('pending', 'in_progress', 'completed')."""
    now = datetime.now().isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?", (status, now, task_id))
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected


def delete_task(task_id: int) -> bool:
    """Deletes a task by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected


# ----------------------------------------------------------------------
# Reminder Operations
# ----------------------------------------------------------------------

def create_reminder(title: str, remind_at: str, task_id: Optional[int] = None) -> int:
    """Stores a real reminder record."""
    now = datetime.now().isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO reminders (task_id, title, remind_at, status, created_at)
        VALUES (?, ?, ?, 'active', ?)
    """, (task_id, title, remind_at, now))
    rem_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return rem_id


def list_reminders(status: str = "active") -> List[Dict[str, Any]]:
    """Lists reminders."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reminders WHERE status = ? ORDER BY remind_at ASC", (status,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


# ----------------------------------------------------------------------
# Content Draft Operations
# ----------------------------------------------------------------------

def save_draft(platform: str, title: str, content: str,
               hook_variations: Optional[List[str]] = None, tags: str = "") -> int:
    """Saves a LinkedIn or X/Twitter content draft."""
    now = datetime.now().isoformat()
    hooks_json = json.dumps(hook_variations or [])
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO content_drafts (platform, title, content, hook_variations, tags, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 'draft', ?, ?)
    """, (platform, title, content, hooks_json, tags, now, now))
    draft_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return draft_id


def list_drafts(platform: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists saved drafts, optionally filtered by platform."""
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM content_drafts WHERE 1=1"
    params = []
    if platform and platform != "All":
        query += " AND platform = ?"
        params.append(platform)
    query += " ORDER BY created_at DESC"
    cursor.execute(query, params)
    rows = []
    for r in cursor.fetchall():
        d = dict(r)
        d["hook_variations"] = json.loads(d["hook_variations"]) if d.get("hook_variations") else []
        rows.append(d)
    conn.close()
    return rows


def update_draft(draft_id: int, content: str, status: Optional[str] = None) -> bool:
    """Updates content draft text or status."""
    now = datetime.now().isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    if status:
        cursor.execute("UPDATE content_drafts SET content = ?, status = ?, updated_at = ? WHERE id = ?",
                       (content, status, now, draft_id))
    else:
        cursor.execute("UPDATE content_drafts SET content = ?, updated_at = ? WHERE id = ?",
                       (content, now, draft_id))
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected


# ----------------------------------------------------------------------
# GitHub Review Operations
# ----------------------------------------------------------------------

def save_github_review(repo_name: str, repo_url: str, summary: str,
                       structure_analysis: str = "", findings: Optional[List[str]] = None,
                       recommendations: Optional[List[str]] = None) -> int:
    """Saves a completed GitHub repo review."""
    now = datetime.now().isoformat()
    findings_json = json.dumps(findings or [])
    recs_json = json.dumps(recommendations or [])
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO github_reviews (repo_name, repo_url, summary, structure_analysis, findings_json, recommendations_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (repo_name, repo_url, summary, structure_analysis, findings_json, recs_json, now))
    review_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return review_id


def list_github_reviews(limit: int = 10) -> List[Dict[str, Any]]:
    """Lists saved GitHub repository reviews."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM github_reviews ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = []
    for r in cursor.fetchall():
        d = dict(r)
        d["findings"] = json.loads(d["findings_json"]) if d.get("findings_json") else []
        d["recommendations"] = json.loads(d["recommendations_json"]) if d.get("recommendations_json") else []
        rows.append(d)
    conn.close()
    return rows


# ----------------------------------------------------------------------
# Approval Queue Operations
# ----------------------------------------------------------------------

def add_approval_request(agent_name: str, action_type: str, description: str,
                         payload: Optional[Dict[str, Any]] = None) -> int:
    """Adds a sensitive or destructive action to the human approval queue."""
    now = datetime.now().isoformat()
    payload_json = json.dumps(payload or {})
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO approval_queue (agent_name, action_type, description, payload_json, status, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?)
    """, (agent_name, action_type, description, payload_json, now))
    req_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return req_id


def list_pending_approvals() -> List[Dict[str, Any]]:
    """Returns all pending approval items."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM approval_queue WHERE status = 'pending' ORDER BY created_at ASC")
    rows = []
    for r in cursor.fetchall():
        d = dict(r)
        d["payload"] = json.loads(d["payload_json"]) if d.get("payload_json") else {}
        rows.append(d)
    conn.close()
    return rows


def list_all_approvals(limit: int = 50) -> List[Dict[str, Any]]:
    """Returns all approval items (history)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM approval_queue ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = []
    for r in cursor.fetchall():
        d = dict(r)
        d["payload"] = json.loads(d["payload_json"]) if d.get("payload_json") else {}
        rows.append(d)
    conn.close()
    return rows


def decide_approval(approval_id: int, decision: str) -> bool:
    """Sets approval status to 'approved' or 'rejected'."""
    if decision not in ("approved", "rejected"):
        raise ValueError("Decision must be 'approved' or 'rejected'")
    now = datetime.now().isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE approval_queue SET status = ?, decided_at = ? WHERE id = ?",
                   (decision, now, approval_id))
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected


# ----------------------------------------------------------------------
# Agent Logging Operations
# ----------------------------------------------------------------------

def log_agent_action(agent_name: str, message: str, level: str = "INFO",
                     session_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> int:
    """Logs an agent action to SQLite."""
    now = datetime.now().isoformat()
    details_json = json.dumps(details or {})
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO agent_logs (session_id, agent_name, level, message, details_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (session_id, agent_name, level, message, details_json, now))
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return log_id


def get_recent_logs(limit: int = 100, agent_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches recent agent logs."""
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM agent_logs WHERE 1=1"
    params = []
    if agent_name and agent_name != "All":
        query += " AND agent_name = ?"
        params.append(agent_name)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


# ----------------------------------------------------------------------
# Chat History Operations
# ----------------------------------------------------------------------

def save_chat_message(session_id: str, role: str, content: str,
                      agent_name: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> int:
    """Saves a chat turn."""
    now = datetime.now().isoformat()
    meta_json = json.dumps(meta or {})
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO chat_history (session_id, role, content, agent_name, meta_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (session_id, role, content, agent_name, meta_json, now))
    msg_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return msg_id


def get_chat_history(session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Gets chat messages for a session."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM chat_history WHERE session_id = ? ORDER BY created_at ASC LIMIT ?
    """, (session_id, limit))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows
