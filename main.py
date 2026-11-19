"""Main FastAPI application for Prince AI Team (per SPEC.md v2).

Serves server-rendered Jinja2 + HTMX dashboard on 127.0.0.1:8000.
Supports asynchronous background agent runs with HTMX live polling,
in-process APScheduler reminders, and safety approval management.
"""

from typing import Optional
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Request, Form, Depends, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler

from config import (
    BASE_DIR, DATABASE_URL, LLM_PROVIDER, OLLAMA_HOST, OLLAMA_MODEL,
    GITHUB_USERNAME, LOG_LEVEL, TECH_NICHES, PROJECT_TAGS
)
from db.models import Task, AgentRun, Draft, GitHubReview, WorkItem, Reminder, Approval, Log
from db.session import init_db, get_db, SessionLocal
from agents.supervisor import default_supervisor
from approvals.manager import ApprovalManager
from llm import default_provider
from logging_utils.logger import get_logger, log_event

logger = get_logger("MainApp")

# Initialize FastAPI application
app = FastAPI(title="Prince AI Team", description="Personal Multi-Agent AI Assistant")

# Mount static files and Jinja2 templates
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "dashboard" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "dashboard" / "templates"))

# APScheduler for in-process reminders (§3)
scheduler = BackgroundScheduler()


def _process_due_reminders(db: Session) -> None:
    """Marks due reminders as fired and emits structured activity logs."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    due_reminders = db.query(Reminder).filter(
        Reminder.fired == False,
        Reminder.remind_at <= now_str
    ).all()

    for rem in due_reminders:
        rem.fired = True
        db.commit()
        task_title = rem.work_item.title if rem.work_item else "Scheduled Check-in"
        msg = f"🔔 IN-APP REMINDER: Check-in due for '{task_title}' (Scheduled: {rem.remind_at})"
        log_event("DailyWorkAgent", msg, level="INFO")
        logger.info(msg)


def check_due_reminders():
    """Background check for due in-app reminders (§3)."""
    db = SessionLocal()
    try:
        _process_due_reminders(db)
    except Exception as e:
        logger.error(f"Error checking reminders: {e}")
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    """Initializes SQLite database tables, logger, and reminder scheduler."""
    init_db()
    try:
        scheduler.add_job(check_due_reminders, "interval", seconds=30, id="reminder_check", replace_existing=True)
        scheduler.start()
        logger.info("APScheduler reminder job started (running every 30s)")
    except Exception as e:
        logger.warning(f"Could not start APScheduler: {e}")
    logger.info("Prince AI Team FastAPI server ready on http://127.0.0.1:8000")


@app.on_event("shutdown")
def on_shutdown():
    """Shuts down scheduler cleanly."""
    if scheduler.running:
        scheduler.shutdown(wait=False)


def get_common_context(db: Session, active_tab: str = "chat") -> dict:
    """Helper providing global variables to templates like approvals, fired reminders, and metrics."""
    try:
        _process_due_reminders(db)
    except Exception as e:
        logger.debug(f"Could not process due reminders on request: {e}")

    pending_count = len(ApprovalManager.get_pending_approvals(db=db))
    fired_reminders = db.query(Reminder).filter(Reminder.fired == True).order_by(Reminder.remind_at.asc()).all()
    total_tasks = db.query(Task).count()
    completed_tasks = db.query(Task).filter(Task.status == "completed").count()
    total_drafts = db.query(Draft).count()
    active_work_items = db.query(WorkItem).filter(WorkItem.status != "done").count()
    total_reviews = db.query(GitHubReview).count()
    active_model = getattr(default_provider, "model", OLLAMA_MODEL)
    today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return {
        "active_tab": active_tab,
        "pending_approvals_count": pending_count,
        "fired_reminders": fired_reminders,
        "llm_provider_name": LLM_PROVIDER,
        "llm_model": active_model,
        "today_date": today_date,
        "metrics": {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "total_drafts": total_drafts,
            "active_work_items": active_work_items,
            "total_reviews": total_reviews
        }
    }


def run_supervisor_task(task_id: int, prompt: str):
    """Background task runner to prevent blocking HTTP request on Ollama inference."""
    db = SessionLocal()
    try:
        default_supervisor.execute_workflow(raw_input=prompt, db=db, task_id=task_id)
    except Exception as e:
        logger.error(f"Error in background supervisor execution: {e}")
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "failed"
            task.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


# ----------------------------------------------------------------------
# 1. Console / Home (Task Submission & Live Polling)
# ----------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    latest_task = db.query(Task).order_by(Task.created_at.desc()).first()
    context = get_common_context(db, active_tab="chat")
    context.update({
        "latest_task": latest_task,
        "executive_summary": latest_task.executive_summary if latest_task else None
    })
    return templates.TemplateResponse(request=request, name="index.html", context=context)


@app.post("/submit-task", response_class=HTMLResponse)
def submit_task(
    request: Request,
    background_tasks: BackgroundTasks,
    prompt: str = Form(...),
    db: Session = Depends(get_db)
):
    # Create task with status 'running' immediately
    new_task = Task(
        raw_input=prompt.strip(),
        status="running",
        created_at=datetime.now(timezone.utc)
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    # Launch supervisor in background thread
    background_tasks.add_task(run_supervisor_task, new_task.id, prompt.strip())

    # Return partial task card with HTMX polling enabled
    context = {"task": new_task}
    return templates.TemplateResponse(request=request, name="partials/task_card.html", context=context)


@app.get("/api/tasks/{task_id}/poll", response_class=HTMLResponse)
def poll_task_status(task_id: int, request: Request, db: Session = Depends(get_db)):
    """Endpoint called periodically by HTMX to update task progress."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    context = {"task": task}
    return templates.TemplateResponse(request=request, name="partials/task_card.html", context=context)


@app.get("/api/status")
def system_status_endpoint(db: Session = Depends(get_db)):
    """Health check and provider status inspection endpoint."""
    llm_info = default_provider.check_status()
    pending_approvals = len(ApprovalManager.get_pending_approvals(db=db))
    return {
        "status": "healthy",
        "app": "Prince AI Team",
        "version": "1.0.0",
        "llm": llm_info,
        "scheduler_running": scheduler.running,
        "pending_approvals": pending_approvals,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/health-badge", response_class=HTMLResponse)
def health_badge_endpoint():
    """HTMX partial reporting live LLM provider connectivity."""
    info = default_provider.check_status()
    model = info.get("model") or OLLAMA_MODEL
    if info.get("online"):
        models_count = len(info.get("available_models", []))
        title = f"{info.get('message', 'Online')} ({models_count} local models)" if models_count else info.get("message", "Online")
        return HTMLResponse(
            f'<span class="badge badge-content" hx-get="/api/health-badge" hx-trigger="every 30s" hx-swap="outerHTML" title="{title}">🟢 {LLM_PROVIDER.title()}: {model}</span>'
        )
    return HTMLResponse(
        f'<span class="badge badge-automation" hx-get="/api/health-badge" hx-trigger="every 30s" hx-swap="outerHTML" title="{info.get("message", "Offline")}">🔴 {LLM_PROVIDER.title()} Offline ({model})</span>'
    )


# ----------------------------------------------------------------------
# 2. Tasks History
# ----------------------------------------------------------------------
@app.get("/tasks", response_class=HTMLResponse)
def tasks_page(
    request: Request,
    status: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Task)
    if status and status != "all":
        query = query.filter(Task.status == status.lower())
    if q and q.strip():
        search_term = f"%{q.strip()}%"
        query = query.filter(Task.raw_input.ilike(search_term) | Task.executive_summary.ilike(search_term))
    tasks = query.order_by(Task.created_at.desc()).limit(100).all()
    context = get_common_context(db, active_tab="tasks")
    context.update({
        "tasks": tasks,
        "selected_status": status or "all",
        "search_query": q or ""
    })
    return templates.TemplateResponse(request=request, name="tasks.html", context=context)


@app.post("/tasks/rerun/{task_id}")
def rerun_task_endpoint(
    task_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    old_task = db.query(Task).filter(Task.id == task_id).first()
    if not old_task:
        raise HTTPException(status_code=404, detail="Task not found")

    new_task = Task(
        raw_input=old_task.raw_input,
        status="running",
        created_at=datetime.now(timezone.utc)
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    background_tasks.add_task(run_supervisor_task, new_task.id, old_task.raw_input)
    return RedirectResponse(url="/", status_code=303)


@app.get("/tasks/export/{task_id}")
def export_task_audit_endpoint(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    filename = f"task_{task.id}_audit.md"
    body = f"# Task #{task.id} Audit Report\n\n"
    body += f"- **Request:** {task.raw_input}\n"
    body += f"- **Status:** {task.status.upper()}\n"
    body += f"- **Created At:** {task.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
    if task.completed_at:
        body += f"- **Completed At:** {task.completed_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
    body += f"- **Routed Pipeline:** {', '.join(task.get_routed_agents())}\n\n"

    if task.executive_summary:
        body += f"## Supervisor Executive Summary\n\n{task.executive_summary}\n\n"

    if task.agent_runs:
        body += "## Agent Execution Trace\n\n"
        for idx, run in enumerate(task.agent_runs, 1):
            body += f"### {idx}. {run.agent_name} ({run.status.upper()})\n\n"
            if run.started_at:
                body += f"- **Started:** {run.started_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            if run.finished_at:
                body += f"- **Finished:** {run.finished_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            body += f"\n```\n{run.output or '(No output)'}\n```\n\n"

    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.get("/tasks/export-all")
def export_all_tasks_endpoint(
    status: Optional[str] = None,
    q: Optional[str] = None,
    format: Optional[str] = "md",
    db: Session = Depends(get_db)
):
    query = db.query(Task)
    if status and status != "all":
        query = query.filter(Task.status == status.lower())
    if q and q.strip():
        search_term = f"%{q.strip()}%"
        query = query.filter(Task.raw_input.ilike(search_term) | Task.executive_summary.ilike(search_term))
    tasks = query.order_by(Task.created_at.desc()).all()

    if format and format.lower() == "csv":
        import io, csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "raw_input", "status", "routed_agents", "executive_summary", "created_at", "completed_at"])
        for t in tasks:
            writer.writerow([
                t.id,
                t.raw_input,
                t.status,
                ", ".join(t.get_routed_agents()),
                t.executive_summary or "",
                t.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                t.completed_at.strftime('%Y-%m-%d %H:%M:%S') if t.completed_at else ""
            ])
        filename = f"tasks_history_{status or 'all'}.csv"
        return Response(
            content=output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    filename = f"tasks_history_{status or 'all'}.md"
    body = f"# Prince AI Team - Task History Digest\n\n"
    body += f"- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
    body += f"- Filter: Status={status or 'all'}, Query='{q or ''}'\n"
    body += f"- Total Tasks: {len(tasks)}\n\n---\n\n"

    for t in tasks:
        body += f"## Task #{t.id} - {t.status.upper()}\n\n"
        body += f"- **Request:** {t.raw_input}\n"
        body += f"- **Pipeline:** {', '.join(t.get_routed_agents())}\n"
        body += f"- **Created:** {t.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        if t.completed_at:
            body += f"- **Completed:** {t.completed_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        if t.executive_summary:
            body += f"\n### Executive Summary\n\n{t.executive_summary}\n"
        if t.agent_runs:
            body += "\n### Agent Steps\n\n"
            for run in t.agent_runs:
                body += f"- **{run.agent_name}** ({run.status})\n"
        body += "\n---\n\n"

    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.post("/tasks/delete/{task_id}")
def delete_task_endpoint(request: Request, task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        db.delete(task)
        db.commit()
    if request.headers.get("HX-Request"):
        return HTMLResponse("")
    return RedirectResponse(url="/tasks", status_code=303)


# ----------------------------------------------------------------------
# 3. Content Drafts (CRUD)
# ----------------------------------------------------------------------
@app.get("/drafts", response_class=HTMLResponse)
def drafts_page(
    request: Request,
    platform: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Draft)
    if platform and platform != "all":
        query = query.filter(Draft.platform == platform.lower())
    if status and status != "all":
        query = query.filter(Draft.status == status.lower())
    if q and q.strip():
        search_term = f"%{q.strip()}%"
        query = query.filter(Draft.content.ilike(search_term))
    drafts = query.order_by(Draft.created_at.desc()).all()

    context = get_common_context(db, active_tab="drafts")
    context.update({
        "drafts": drafts,
        "selected_platform": platform or "all",
        "selected_status": status or "all",
        "search_query": q or ""
    })
    return templates.TemplateResponse(request=request, name="drafts.html", context=context)


@app.get("/drafts/export-all")
def export_all_drafts_endpoint(
    platform: Optional[str] = None,
    status: Optional[str] = None,
    format: Optional[str] = "md",
    db: Session = Depends(get_db)
):
    query = db.query(Draft)
    if platform and platform != "all":
        query = query.filter(Draft.platform == platform.lower())
    if status and status != "all":
        query = query.filter(Draft.status == status.lower())
    drafts = query.order_by(Draft.created_at.desc()).all()

    if format and format.lower() == "csv":
        import io, csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "platform", "type", "status", "source_ref", "content", "created_at"])
        for d in drafts:
            writer.writerow([d.id, d.platform, d.type, d.status, d.source_ref or "", d.content, d.created_at.strftime('%Y-%m-%d %H:%M:%S')])
        filename = f"drafts_{platform or 'all'}.csv"
        return Response(
            content=output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    filename = f"drafts_digest_{platform or 'all'}.md"
    body = f"# Content Lab Drafts Digest\n\n"
    body += f"- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
    body += f"- Filter: Platform={platform or 'all'}, Status={status or 'all'}\n"
    body += f"- Total Drafts: {len(drafts)}\n\n---\n\n"

    for d in drafts:
        body += f"## Draft #{d.id} [{d.platform.upper()}] - {d.status.upper()}\n\n"
        body += f"- **Type:** {d.type}\n"
        body += f"- **Created:** {d.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        if d.source_ref:
            body += f"- **Source:** {d.source_ref}\n"
        body += f"\n{d.content}\n\n---\n\n"

    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.post("/drafts/update/{draft_id}")
def update_draft_endpoint(
    draft_id: int,
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if draft:
        draft.content = content
        db.commit()
    return RedirectResponse(url="/drafts", status_code=303)


@app.post("/drafts/delete/{draft_id}")
def delete_draft_endpoint(request: Request, draft_id: int, db: Session = Depends(get_db)):
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if draft:
        db.delete(draft)
        db.commit()
    if request.headers.get("HX-Request"):
        return HTMLResponse("")
    return RedirectResponse(url="/drafts", status_code=303)


@app.get("/drafts/export/{draft_id}")
def export_draft_endpoint(draft_id: int, db: Session = Depends(get_db)):
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    filename = f"draft_{draft.platform}_{draft.id}.md"
    body = f"# Prince AI Team Draft #{draft.id} ({draft.platform.upper()})\n\n"
    if draft.source_ref:
        body += f"> Source: {draft.source_ref}\n\n"
    body += draft.content
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.post("/drafts/request-approval/{draft_id}")
def request_draft_approval_endpoint(draft_id: int, db: Session = Depends(get_db)):
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    ApprovalManager.request_approval(
        action_type="publish_content",
        description=f"Publish {draft.platform.upper()} draft #{draft.id}: '{draft.content[:80]}...'",
        payload={"draft_id": draft.id, "platform": draft.platform, "snippet": draft.content[:150]},
        requested_by_agent="ContentAgent",
        db=db
    )
    return RedirectResponse(url="/drafts", status_code=303)


@app.post("/drafts/mark-posted/{draft_id}")
def mark_draft_posted_endpoint(draft_id: int, db: Session = Depends(get_db)):
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if draft:
        draft.status = "posted_manually"
        db.commit()
    return RedirectResponse(url="/drafts", status_code=303)


@app.post("/drafts/re-roll/{draft_id}")
def reroll_draft_endpoint(
    draft_id: int,
    angle_hint: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Re-rolls / crafts an alternative angle or hook variation for an existing draft."""
    try:
        res = default_supervisor.content_agent.generate_variation(draft_id=draft_id, db=db, angle_hint=angle_hint)
        logger.info(f"Re-rolled draft #{draft_id} -> new variation #{res.get('new_draft_id')}")
    except Exception as e:
        logger.error(f"Failed to re-roll draft #{draft_id}: {e}")
    return RedirectResponse(url="/drafts", status_code=303)


@app.post("/drafts/adapt/{draft_id}")
def adapt_draft_endpoint(
    draft_id: int,
    target_platform: str = Form(...),
    db: Session = Depends(get_db)
):
    """Cross-adapts an existing draft into another platform (linkedin, medium, x, image_prompt)."""
    try:
        res = default_supervisor.content_agent.adapt_draft_platform(
            draft_id=draft_id,
            target_platform=target_platform,
            db=db
        )
        logger.info(f"Adapted draft #{draft_id} to #{res.get('new_draft_id')} ({target_platform})")
    except Exception as e:
        logger.error(f"Failed to adapt draft #{draft_id} to {target_platform}: {e}")
    return RedirectResponse(url="/drafts", status_code=303)


@app.post("/drafts/polish/{draft_id}")
def polish_draft_endpoint(
    draft_id: int,
    tone: str = Form("concise"),
    db: Session = Depends(get_db)
):
    """Polishes an existing draft's tone (concise, research_grade, contrarian)."""
    try:
        res = default_supervisor.content_agent.polish_draft_tone(draft_id=draft_id, tone=tone, db=db)
        logger.info(f"Polished draft #{draft_id} ({tone}) -> new draft #{res.get('new_draft_id')}")
    except Exception as e:
        logger.error(f"Failed to polish draft #{draft_id} ({tone}): {e}")
    return RedirectResponse(url="/drafts", status_code=303)


@app.post("/drafts/duplicate/{draft_id}")
def duplicate_draft_endpoint(draft_id: int, db: Session = Depends(get_db)):
    """Duplicates an existing draft to enable non-destructive branch editing."""
    original = db.query(Draft).filter(Draft.id == draft_id).first()
    if not original:
        raise HTTPException(status_code=404, detail="Draft not found")
    dup = Draft(
        platform=original.platform,
        type=f"{original.type}_copy",
        status="draft",
        source_ref=original.source_ref,
        content=original.content,
        created_at=datetime.now(timezone.utc)
    )
    db.add(dup)
    db.commit()
    db.refresh(dup)
    logger.info(f"Duplicated draft #{original.id} -> #{dup.id}")
    return RedirectResponse(url="/drafts", status_code=303)


# ----------------------------------------------------------------------
# 4. Daily Work & Reminders (CRUD)
# ----------------------------------------------------------------------
@app.get("/work", response_class=HTMLResponse)
def work_page(
    request: Request,
    tag: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    due: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(WorkItem)
    if tag and tag != "all":
        query = query.filter(WorkItem.project_tag == tag.lower())
    if status and status != "all":
        query = query.filter(WorkItem.status == status.lower())
    if priority and priority != "all":
        query = query.filter(WorkItem.priority == priority.lower())

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if due and due != "all":
        if due == "overdue":
            query = query.filter(WorkItem.status != "done", WorkItem.due_date != None, WorkItem.due_date < today_str)
        elif due == "today":
            query = query.filter(WorkItem.status != "done", WorkItem.due_date == today_str)
        elif due == "upcoming":
            query = query.filter(WorkItem.status != "done", WorkItem.due_date != None, WorkItem.due_date > today_str)

    if q and q.strip():
        search_term = f"%{q.strip()}%"
        query = query.filter(WorkItem.title.ilike(search_term))
    work_items = query.order_by(WorkItem.created_at.desc()).all()
    reminders = db.query(Reminder).order_by(Reminder.remind_at.asc()).all()

    # Pre-calculate counts for overdue / today badges
    all_active = db.query(WorkItem).filter(WorkItem.status != "done").all()
    overdue_count = sum(1 for it in all_active if it.due_date and it.due_date < today_str)
    today_count = sum(1 for it in all_active if it.due_date and it.due_date == today_str)

    context = get_common_context(db, active_tab="work")
    context.update({
        "work_items": work_items,
        "reminders": reminders,
        "selected_tag": tag or "all",
        "selected_status": status or "all",
        "selected_priority": priority or "all",
        "selected_due": due or "all",
        "search_query": q or "",
        "overdue_count": overdue_count,
        "today_count": today_count
    })
    return templates.TemplateResponse(request=request, name="work.html", context=context)


@app.get("/work/export")
def export_work_items_endpoint(
    tag: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    due: Optional[str] = None,
    format: Optional[str] = "md",
    db: Session = Depends(get_db)
):
    query = db.query(WorkItem)
    if tag and tag != "all":
        query = query.filter(WorkItem.project_tag == tag.lower())
    if status and status != "all":
        query = query.filter(WorkItem.status == status.lower())
    if priority and priority != "all":
        query = query.filter(WorkItem.priority == priority.lower())

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if due and due != "all":
        if due == "overdue":
            query = query.filter(WorkItem.status != "done", WorkItem.due_date != None, WorkItem.due_date < today_str)
        elif due == "today":
            query = query.filter(WorkItem.status != "done", WorkItem.due_date == today_str)
        elif due == "upcoming":
            query = query.filter(WorkItem.status != "done", WorkItem.due_date != None, WorkItem.due_date > today_str)

    items = query.order_by(WorkItem.created_at.desc()).all()

    if format and format.lower() == "csv":
        import io, csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "title", "project_tag", "priority", "status", "due_date", "parent_id", "created_at"])
        for it in items:
            writer.writerow([it.id, it.title, it.project_tag, it.priority, it.status, it.due_date or "", it.parent_id or "", it.created_at.strftime('%Y-%m-%d %H:%M:%S')])
        filename = f"work_items_{tag or 'all'}.csv"
        return Response(
            content=output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    tag_str = f" ({tag.upper()})" if tag and tag != "all" else ""
    filename = f"work_items_{tag or 'all'}.md"
    body = f"# Daily Work & Milestones Checklist{tag_str}\n\n"
    body += f"- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
    body += f"- Total Items: {len(items)}\n\n"

    for it in items:
        status_box = "[x]" if it.status == "done" else "[ ]"
        indent = "  " if it.parent_id else ""
        sub_info = f" (Subtask of #{it.parent_id})" if it.parent_id else ""
        due_str = f" `(Due: {it.due_date})`" if it.due_date else ""
        body += f"{indent}- {status_box} **{it.title}** `[{it.project_tag.upper()}]` `[{it.priority.upper()}]`{due_str}{sub_info}\n"

    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.post("/work/clear-completed")
def clear_completed_work_items(db: Session = Depends(get_db)):
    completed = db.query(WorkItem).filter(WorkItem.status == "done").all()
    for item in completed:
        db.delete(item)
    db.commit()
    return RedirectResponse(url="/work", status_code=303)


@app.post("/work/complete-all")
def complete_all_work_items_endpoint(
    tag: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    query = db.query(WorkItem).filter(WorkItem.status != "done")
    if tag and tag != "all":
        query = query.filter(WorkItem.project_tag == tag.lower())
    items = query.all()
    now_utc = datetime.now(timezone.utc)
    for it in items:
        it.status = "done"
        it.completed_at = now_utc
    db.commit()
    logger.info(f"Marked {len(items)} work items as done (tag: {tag or 'all'})")
    return RedirectResponse(url="/work", status_code=303)


@app.post("/work/create")
def create_work_item_endpoint(
    title: str = Form(...),
    project_tag: str = Form("general"),
    priority: str = Form("medium"),
    due_date: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    clean_due = due_date.strip() if due_date and due_date.strip() else None
    item = WorkItem(
        title=title.strip(),
        project_tag=project_tag,
        priority=priority,
        due_date=clean_due,
        status="todo",
        created_at=datetime.now(timezone.utc)
    )
    db.add(item)
    db.commit()
    return RedirectResponse(url="/work", status_code=303)


@app.post("/work/toggle/{item_id}")
def toggle_work_item(request: Request, item_id: int, db: Session = Depends(get_db)):
    item = db.query(WorkItem).filter(WorkItem.id == item_id).first()
    if item:
        item.status = "done" if item.status != "done" else "todo"
        item.completed_at = datetime.now(timezone.utc) if item.status == "done" else None
        db.commit()
        db.refresh(item)
    if request.headers.get("HX-Request") and item:
        is_done = item.status == "done"
        checked = "checked" if is_done else ""
        line_style = "text-decoration: line-through; color: var(--text-muted);" if is_done else "font-weight: 600;"
        bg_style = "var(--surface-alt)" if is_done else "var(--surface)"
        badge_cls = "badge-content" if is_done else "badge-daily"
        subtask_style = "margin-left: 1.5rem; border-left: 3px solid var(--primary);" if item.parent_id else ""
        subtask_prefix = '<span style="color: var(--primary); font-size: 0.85rem; margin-right: 0.2rem;">↳</span>' if item.parent_id else ""
        subtask_note = f'<span style="font-size: 0.7rem; color: var(--primary); margin-left: 0.4rem;">[Subtask of #{item.parent_id}]</span>' if item.parent_id else ""
        today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if item.due_date:
            if not is_done and item.due_date < today_date:
                due_chip = f'<span class="badge badge-automation" style="font-size: 0.7rem; font-weight: 700; margin-left: 0.4rem;">⚠️ Overdue: {item.due_date}</span>'
            elif not is_done and item.due_date == today_date:
                due_chip = f'<span class="badge badge-daily" style="font-size: 0.7rem; font-weight: 700; margin-left: 0.4rem;">🚨 Due Today</span>'
            else:
                due_chip = f'<span class="badge" style="font-size: 0.7rem; background: var(--bg); border: 1px solid var(--border); color: var(--text-main); margin-left: 0.4rem;">📅 Due: {item.due_date}</span>'
        else:
            due_chip = ""
        return HTMLResponse(f"""
        <div id="work-item-{item.id}" style="border: 1px solid var(--border); padding: 0.75rem; border-radius: 6px; display: flex; justify-content: space-between; align-items: center; background: {bg_style}; {subtask_style}">
          <div style="display: flex; align-items: center; gap: 0.75rem;">
            <form action="/work/toggle/{item.id}" method="POST"
                  hx-post="/work/toggle/{item.id}"
                  hx-target="#work-item-{item.id}"
                  hx-swap="outerHTML" style="margin: 0;">
              <input type="checkbox" onChange="this.form.requestSubmit()" {checked} title="Toggle complete">
            </form>
            <div>
              <div style="{line_style}">
                {subtask_prefix}{item.title}
              </div>
              <span class="badge badge-daily" style="font-size: 0.7rem; padding: 0.1rem 0.4rem;">
                {item.project_tag}
              </span>
              <span style="font-size: 0.75rem; color: var(--text-muted); margin-left: 0.4rem;">Priority: {item.priority}</span>
              {due_chip}
              {subtask_note}
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <span class="badge {badge_cls}" style="font-size: 0.75rem;">
              {item.status}
            </span>
            <form action="/work/delete/{item.id}" method="POST"
                  hx-post="/work/delete/{item.id}"
                  hx-target="#work-item-{item.id}"
                  hx-swap="outerHTML swap:300ms"
                  style="margin: 0;" onsubmit="return confirm('Delete this task?');">
              <button type="submit" class="btn btn-secondary" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;" title="Delete task">🗑️</button>
            </form>
          </div>
        </div>
        """)
    return RedirectResponse(url="/work", status_code=303)


@app.post("/work/delete/{item_id}")
def delete_work_item_endpoint(request: Request, item_id: int, db: Session = Depends(get_db)):
    item = db.query(WorkItem).filter(WorkItem.id == item_id).first()
    if item:
        db.delete(item)
        db.commit()
    if request.headers.get("HX-Request"):
        return HTMLResponse("")
    return RedirectResponse(url="/work", status_code=303)


@app.post("/work/subtasks/add/{parent_id}")
def add_subtask_endpoint(
    parent_id: int,
    title: str = Form(...),
    priority: Optional[str] = Form("medium"),
    due_date: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    parent = db.query(WorkItem).filter(WorkItem.id == parent_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent work item not found")

    clean_title = title.strip()
    if not clean_title:
        raise HTTPException(status_code=400, detail="Subtask title cannot be empty")

    clean_due = due_date.strip() if due_date and due_date.strip() else None
    clean_pri = priority.strip().lower() if priority and priority.strip().lower() in ["high", "medium", "low"] else "medium"

    subtask = WorkItem(
        title=clean_title,
        project_tag=parent.project_tag,
        priority=clean_pri,
        due_date=clean_due,
        parent_id=parent.id,
        status="todo",
        created_at=datetime.now(timezone.utc)
    )
    db.add(subtask)
    db.commit()
    db.refresh(subtask)
    log_event("DailyWorkAgent", f"Added manual subtask '{subtask.title}' under WorkItem #{parent.id}")
    return RedirectResponse(url="/work", status_code=303)


@app.post("/work/priority/cycle/{item_id}")
def cycle_work_item_priority(
    item_id: int,
    db: Session = Depends(get_db)
):
    item = db.query(WorkItem).filter(WorkItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Work item not found")

    cycle_map = {"low": "medium", "medium": "high", "high": "low"}
    old_pri = (item.priority or "medium").lower()
    item.priority = cycle_map.get(old_pri, "medium")
    db.commit()
    db.refresh(item)
    log_event("DailyWorkAgent", f"Updated priority for WorkItem #{item.id}: {old_pri} -> {item.priority}")
    return RedirectResponse(url="/work", status_code=303)


@app.post("/work/reminders/create")
def create_reminder_endpoint(
    work_item_id: Optional[str] = Form(None),
    remind_at: str = Form(...),
    db: Session = Depends(get_db)
):
    item_id = int(work_item_id) if work_item_id and work_item_id.isdigit() else None
    rem = Reminder(
        work_item_id=item_id,
        remind_at=remind_at.strip(),
        fired=False,
        created_at=datetime.now(timezone.utc)
    )
    db.add(rem)
    db.commit()
    return RedirectResponse(url="/work", status_code=303)


@app.post("/work/reminders/delete/{reminder_id}")
def delete_reminder_endpoint(request: Request, reminder_id: int, db: Session = Depends(get_db)):
    rem = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if rem:
        db.delete(rem)
        db.commit()
    if request.headers.get("HX-Request"):
        return HTMLResponse("")
    return RedirectResponse(url="/work", status_code=303)


@app.post("/work/reminders/snooze/{reminder_id}")
def snooze_reminder_endpoint(
    request: Request,
    reminder_id: int,
    minutes: int = Form(60),
    db: Session = Depends(get_db)
):
    rem = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if rem:
        rem.remind_at = (datetime.now(timezone.utc) + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M")
        rem.fired = False
        db.commit()
    if request.headers.get("HX-Request"):
        return HTMLResponse("")
    return RedirectResponse(url="/work", status_code=303)


@app.post("/work/decompose/{item_id}")
def decompose_work_item_endpoint(item_id: int, db: Session = Depends(get_db)):
    parent_item = db.query(WorkItem).filter(WorkItem.id == item_id).first()
    if not parent_item:
        raise HTTPException(status_code=404, detail="Work item not found")

    prompt = f"""You are the Daily Work Agent for Prince.
Decompose this major goal/task into 2 to 4 concrete, actionable subtasks:
Goal: "{parent_item.title}"
Project Tag: {parent_item.project_tag}
Priority: {parent_item.priority}

For each subtask, output on a new line strictly formatted as:
- Subtask: [Concise actionable title] | Priority: [high/medium/low]
"""
    try:
        response_text = default_supervisor.daily_work_agent.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="You are an expert productivity engineer decomposing high-level milestones into atomic subtasks.",
            temperature=0.5
        )
        created_count = 0
        for line in response_text.split("\n"):
            clean = line.strip()
            if "subtask:" in clean.lower() or (clean.startswith(("-", "*", "1.", "2.", "3.", "4.")) and len(clean) > 10):
                title_part = clean
                priority = parent_item.priority or "medium"
                if "|" in clean:
                    parts = clean.split("|")
                    title_part = parts[0]
                    if len(parts) > 1 and "priority:" in parts[1].lower():
                        p_val = parts[1].lower().replace("priority:", "").strip()
                        if p_val in ["high", "medium", "low"]:
                            priority = p_val
                if ":" in title_part:
                    title_part = title_part.split(":", 1)[1]
                title_clean = title_part.strip().strip("*\"'- ")
                if 5 < len(title_clean) < 150:
                    sub_item = WorkItem(
                        title=title_clean,
                        project_tag=parent_item.project_tag,
                        priority=priority,
                        parent_id=parent_item.id,
                        status="todo",
                        created_at=datetime.now(timezone.utc)
                    )
                    db.add(sub_item)
                    created_count += 1
                    if created_count >= 4:
                        break
        if created_count == 0:
            sub_item = WorkItem(
                title=f"Execute Phase 1 of '{parent_item.title[:45]}'",
                project_tag=parent_item.project_tag,
                priority=parent_item.priority,
                parent_id=parent_item.id,
                status="todo",
                created_at=datetime.now(timezone.utc)
            )
            db.add(sub_item)
        db.commit()
        logger.info(f"Decomposed WorkItem #{parent_item.id} into subtasks")
    except Exception as e:
        logger.error(f"Error decomposing work item #{item_id}: {e}")

    return RedirectResponse(url="/work", status_code=303)


# ----------------------------------------------------------------------
# 5. GitHub Reviews
# ----------------------------------------------------------------------
@app.get("/github", response_class=HTMLResponse)
def github_page(request: Request, q: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(GitHubReview)
    if q and q.strip():
        search_term = f"%{q.strip()}%"
        query = query.filter(GitHubReview.repo.ilike(search_term) | GitHubReview.human_summary.ilike(search_term))
    reviews = query.order_by(GitHubReview.created_at.desc()).all()
    context = get_common_context(db, active_tab="github")
    context.update({
        "reviews": reviews,
        "search_query": q or ""
    })
    return templates.TemplateResponse(request=request, name="github.html", context=context)


@app.get("/github/compare", response_class=HTMLResponse)
def compare_github_reviews_page(
    request: Request,
    id1: Optional[int] = None,
    id2: Optional[int] = None,
    db: Session = Depends(get_db)
):
    reviews = db.query(GitHubReview).order_by(GitHubReview.created_at.desc()).all()
    rev1 = db.query(GitHubReview).filter(GitHubReview.id == id1).first() if id1 else (reviews[0] if len(reviews) > 0 else None)
    rev2 = db.query(GitHubReview).filter(GitHubReview.id == id2).first() if id2 else (reviews[1] if len(reviews) > 1 else (reviews[0] if len(reviews) > 0 else None))
    context = get_common_context(db, active_tab="github")
    context.update({
        "reviews": reviews,
        "rev1": rev1,
        "rev2": rev2,
        "summary1": rev1.get_summary_dict() if rev1 else {},
        "summary2": rev2.get_summary_dict() if rev2 else {}
    })
    return templates.TemplateResponse(request=request, name="github_compare.html", context=context)


@app.post("/github/audit")
def audit_github_repo_endpoint(
    repo: str = Form("."),
    db: Session = Depends(get_db)
):
    target = repo.strip() or "."
    default_supervisor.github_agent.execute(f"Review repository {target}", db=db)
    return RedirectResponse(url="/github", status_code=303)


@app.post("/github/repurpose/{review_id}")
def repurpose_github_review_endpoint(review_id: int, db: Session = Depends(get_db)):
    rev = db.query(GitHubReview).filter(GitHubReview.id == review_id).first()
    if not rev:
        raise HTTPException(status_code=404, detail="Review not found")
    prompt = f"Technical architectural breakdown and key engineering insights from repository audit of {rev.repo}"
    context = {
        "github_summary": rev.human_summary,
        "telemetry": rev.summary_json,
        "repo": rev.repo,
        "source_url": f"https://github.com/{rev.repo}" if "/" in rev.repo else rev.repo
    }
    default_supervisor.content_agent.execute(prompt, context=context, db=db)
    return RedirectResponse(url="/drafts", status_code=303)


@app.get("/github/export/{review_id}")
def export_github_review_endpoint(review_id: int, db: Session = Depends(get_db)):
    rev = db.query(GitHubReview).filter(GitHubReview.id == review_id).first()
    if not rev:
        raise HTTPException(status_code=404, detail="Review not found")
    filename = f"github_review_{rev.id}.md"
    body = f"# GitHub Audit Review #{rev.id}: {rev.repo}\n\n"
    body += f"- **Date:** {rev.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
    body += f"## Architectural & Code Quality Review\n\n{rev.human_summary}\n\n"
    body += f"## Raw Telemetry & Manifests\n\n```json\n{rev.summary_json}\n```\n"
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.post("/github/delete/{review_id}")
def delete_github_review_endpoint(request: Request, review_id: int, db: Session = Depends(get_db)):
    rev = db.query(GitHubReview).filter(GitHubReview.id == review_id).first()
    if rev:
        db.delete(rev)
        db.commit()
    if request.headers.get("HX-Request"):
        return HTMLResponse("")
    return RedirectResponse(url="/github", status_code=303)


# ----------------------------------------------------------------------
# 6. Approval Queue & Safety Center
# ----------------------------------------------------------------------
@app.get("/approvals", response_class=HTMLResponse)
def approvals_page(
    request: Request,
    status: Optional[str] = None,
    action_type: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db)
):
    pending_query = db.query(Approval).filter(Approval.status == "pending")
    query = db.query(Approval)
    if status and status != "all":
        query = query.filter(Approval.status == status.lower())
    if action_type and action_type != "all":
        query = query.filter(Approval.action_type == action_type.lower())
        pending_query = pending_query.filter(Approval.action_type == action_type.lower())
    if q and q.strip():
        search_term = f"%{q.strip()}%"
        query = query.filter(Approval.description.ilike(search_term) | Approval.requested_by_agent.ilike(search_term))
        pending_query = pending_query.filter(Approval.description.ilike(search_term) | Approval.requested_by_agent.ilike(search_term))
    all_apps = query.order_by(Approval.created_at.desc()).limit(100).all()
    pending = pending_query.order_by(Approval.created_at.asc()).all()
    context = get_common_context(db, active_tab="approvals")
    context.update({
        "pending_approvals": pending,
        "all_approvals": all_apps,
        "selected_status": status or "all",
        "selected_action_type": action_type or "all",
        "search_query": q or ""
    })
    return templates.TemplateResponse(request=request, name="approvals.html", context=context)


@app.get("/approvals/export")
def export_approvals_endpoint(
    status: Optional[str] = None,
    action_type: Optional[str] = None,
    q: Optional[str] = None,
    format: Optional[str] = "md",
    db: Session = Depends(get_db)
):
    query = db.query(Approval)
    if status and status != "all":
        query = query.filter(Approval.status == status.lower())
    if action_type and action_type != "all":
        query = query.filter(Approval.action_type == action_type.lower())
    if q and q.strip():
        search_term = f"%{q.strip()}%"
        query = query.filter(Approval.description.ilike(search_term) | Approval.requested_by_agent.ilike(search_term))
    approvals = query.order_by(Approval.created_at.desc()).all()

    if format and format.lower() == "csv":
        import io, csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "action_type", "requested_by_agent", "description", "status", "created_at", "resolved_at"])
        for a in approvals:
            writer.writerow([
                a.id,
                a.action_type,
                a.requested_by_agent,
                a.description,
                a.status,
                a.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                a.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if a.resolved_at else ""
            ])
        filename = f"approvals_audit_{status or 'all'}.csv"
        return Response(
            content=output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    filename = f"approvals_audit_{status or 'all'}.md"
    body = f"# Human Approval & Safety Audit\n\n"
    body += f"- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
    body += f"- Filter: Status={status or 'all'}, Action={action_type or 'all'}, Query='{q or ''}'\n"
    body += f"- Total Records: {len(approvals)}\n\n---\n\n"

    for a in approvals:
        body += f"## Approval #{a.id} - {a.status.upper()}\n\n"
        body += f"- **Action Type:** `{a.action_type}`\n"
        body += f"- **Requested By:** {a.requested_by_agent}\n"
        body += f"- **Description:** {a.description}\n"
        body += f"- **Created At:** {a.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        if a.resolved_at:
            body += f"- **Resolved At:** {a.resolved_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        body += f"\n```json\n{a.payload_json}\n```\n\n---\n\n"

    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.post("/approvals/resolve/{approval_id}")
def resolve_approval_endpoint(
    request: Request,
    approval_id: int,
    decision: str = Form(...),
    db: Session = Depends(get_db)
):
    ApprovalManager.resolve_approval(approval_id, decision=decision, db=db)
    if request.headers.get("HX-Request"):
        status_color = "#059669" if decision == "approved" else "#DC2626"
        icon = "✅" if decision == "approved" else "❌"
        return HTMLResponse(f"""
        <div style="border: 1px solid {status_color}; background: #F8FAFC; padding: 1rem 1.25rem; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <div>
                <strong>{icon} Action #{approval_id} Resolved:</strong> Marked as <span style="font-weight: 700; color: {status_color}; text-transform: uppercase;">{decision}</span>.
            </div>
            <span style="font-size: 0.8rem; color: var(--text-muted);">{datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC</span>
        </div>
        """)
    return RedirectResponse(url="/approvals", status_code=303)


@app.post("/approvals/bulk-resolve")
def bulk_resolve_approvals_endpoint(
    decision: str = Form(...),
    db: Session = Depends(get_db)
):
    """Resolves all pending approvals in one click."""
    count = ApprovalManager.resolve_all_pending(decision=decision, db=db)
    logger.info(f"Bulk resolved {count} pending approvals as {decision.upper()}")
    return RedirectResponse(url="/approvals", status_code=303)


# ----------------------------------------------------------------------
# 7. Logs Viewer
# ----------------------------------------------------------------------
@app.get("/logs", response_class=HTMLResponse)
def logs_page(
    request: Request,
    agent: Optional[str] = None,
    level: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Log)
    if agent and agent != "all":
        query = query.filter(Log.agent_name == agent)
    if level and level != "all":
        query = query.filter(Log.level == level.upper())
    if q and q.strip():
        query = query.filter(Log.message.ilike(f"%{q.strip()}%"))
    logs = query.order_by(Log.created_at.desc()).limit(150).all()

    context = get_common_context(db, active_tab="logs")
    context.update({
        "logs": logs,
        "selected_agent": agent or "all",
        "selected_level": level or "all",
        "search_query": q or ""
    })
    return templates.TemplateResponse(request=request, name="logs.html", context=context)


@app.get("/logs/export")
def export_logs_endpoint(
    agent: Optional[str] = None,
    level: Optional[str] = None,
    q: Optional[str] = None,
    format: Optional[str] = "txt",
    db: Session = Depends(get_db)
):
    query = db.query(Log)
    if agent and agent != "all":
        query = query.filter(Log.agent_name == agent)
    if level and level != "all":
        query = query.filter(Log.level == level.upper())
    if q and q.strip():
        query = query.filter(Log.message.ilike(f"%{q.strip()}%"))
    logs = query.order_by(Log.created_at.desc()).limit(1000).all()

    if format and format.lower() == "csv":
        import io, csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "created_at", "level", "agent_name", "message"])
        for l in logs:
            writer.writerow([l.id, l.created_at.strftime('%Y-%m-%d %H:%M:%S'), l.level, l.agent_name, l.message])
        filename = f"agent_logs_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
        return Response(
            content=output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    filename = f"agent_logs_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt"
    lines = [
        f"[{l.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}] [{l.level:<7}] [{l.agent_name:<18}] {l.message}"
        for l in logs
    ]
    body = "\n".join(lines)
    return Response(
        content=body,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.post("/logs/clear")
def clear_logs_endpoint(db: Session = Depends(get_db)):
    db.query(Log).delete()
    db.commit()
    return RedirectResponse(url="/logs", status_code=303)


# ----------------------------------------------------------------------
# 8. System Settings & Runtime Model Diagnostics
# ----------------------------------------------------------------------
@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)):
    import os
    llm_info = default_provider.check_status()
    db_display = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL

    db_size_kb = 0
    db_path = "data/prince_ai_team.db"
    if os.path.exists(db_path):
        db_size_kb = round(os.path.getsize(db_path) / 1024, 2)

    db_stats = {
        "file_size_kb": db_size_kb,
        "tasks_count": db.query(Task).count(),
        "drafts_count": db.query(Draft).count(),
        "work_items_count": db.query(WorkItem).count(),
        "approvals_count": db.query(Approval).count(),
        "reviews_count": db.query(GitHubReview).count(),
        "logs_count": db.query(Log).count(),
    }

    context = get_common_context(db, active_tab="settings")
    context.update({
        "llm_info": llm_info,
        "db_stats": db_stats,
        "ollama_host": OLLAMA_HOST,
        "github_username": GITHUB_USERNAME,
        "log_level": LOG_LEVEL,
        "db_display": db_display,
        "tech_niches": TECH_NICHES,
        "project_tags": PROJECT_TAGS,
        "scheduler_running": scheduler.running
    })
    return templates.TemplateResponse(request=request, name="settings.html", context=context)


@app.post("/settings/request-model-change")
def request_model_change_endpoint(
    new_model: str = Form(...),
    db: Session = Depends(get_db)
):
    target_model = new_model.strip()
    if not target_model:
        raise HTTPException(status_code=400, detail="Model name cannot be empty")
    current_model = getattr(default_provider, "model", OLLAMA_MODEL)
    ApprovalManager.request_approval(
        action_type="modify_system",
        description=f"Switch active runtime LLM model from '{current_model}' to '{target_model}'",
        payload={"setting": "llm_model", "old_model": current_model, "new_model": target_model},
        requested_by_agent="SystemSettings",
        db=db
    )
    return RedirectResponse(url="/approvals", status_code=303)


@app.get("/settings/backup")
def backup_database_endpoint():
    """Download a snapshot of the local SQLite database for disaster recovery and portability."""
    from pathlib import Path
    db_path = BASE_DIR / "data" / "prince_ai_team.db"
    if not db_path.exists():
        local_path = Path("data/prince_ai_team.db")
        if local_path.exists():
            db_path = local_path
        else:
            raise HTTPException(status_code=404, detail="Database file not found on disk.")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_filename = f"prince_ai_team_backup_{timestamp}.db"
    return FileResponse(
        path=str(db_path),
        filename=backup_filename,
        media_type="application/x-sqlite3"
    )


@app.post("/settings/self-test", response_class=HTMLResponse)
def run_system_self_test(request: Request, db: Session = Depends(get_db)):
    """Executes non-destructive diagnostics across SQLite, LLM provider, log files, and safety gate."""
    import time
    results = []

    # 1. Database latency test
    try:
        t0 = time.perf_counter()
        count = db.query(Task).count()
        db_ms = round((time.perf_counter() - t0) * 1000, 2)
        results.append({
            "subsystem": "SQLite Database",
            "status": "PASS",
            "latency": f"{db_ms} ms",
            "detail": f"Queried {count} task record(s) successfully"
        })
    except Exception as e:
        results.append({
            "subsystem": "SQLite Database",
            "status": "FAIL",
            "latency": "N/A",
            "detail": str(e)
        })

    # 2. Local LLM Provider check
    try:
        t0 = time.perf_counter()
        status = default_provider.check_status()
        llm_ms = round((time.perf_counter() - t0) * 1000, 2)
        if status.get("online"):
            results.append({
                "subsystem": f"LLM Engine ({status.get('provider', 'ollama').upper()})",
                "status": "PASS",
                "latency": f"{llm_ms} ms",
                "detail": f"Model: {status.get('model', 'llama3.2')} ({status.get('host', 'local')})"
            })
        else:
            results.append({
                "subsystem": f"LLM Engine ({status.get('provider', 'ollama').upper()})",
                "status": "WARN",
                "latency": f"{llm_ms} ms",
                "detail": status.get("message", "Offline")
            })
    except Exception as e:
        results.append({
            "subsystem": "LLM Engine",
            "status": "FAIL",
            "latency": "N/A",
            "detail": str(e)
        })

    # 3. Local file storage & logging I/O test
    try:
        test_file = BASE_DIR / "data" / ".health_check"
        t0 = time.perf_counter()
        test_file.write_text("health_ok", encoding="utf-8")
        read_back = test_file.read_text(encoding="utf-8")
        test_file.unlink(missing_ok=True)
        io_ms = round((time.perf_counter() - t0) * 1000, 2)
        results.append({
            "subsystem": "Storage & I/O",
            "status": "PASS",
            "latency": f"{io_ms} ms",
            "detail": "Data directory is read/write accessible"
        })
    except Exception as e:
        results.append({
            "subsystem": "Storage & I/O",
            "status": "FAIL",
            "latency": "N/A",
            "detail": str(e)
        })

    # 4. Human Approval Safety Gate integrity
    try:
        t0 = time.perf_counter()
        pending = ApprovalManager.get_pending_approvals(db=db)
        safety_ms = round((time.perf_counter() - t0) * 1000, 2)
        results.append({
            "subsystem": "Safety Gate (§11)",
            "status": "PASS",
            "latency": f"{safety_ms} ms",
            "detail": f"{len(pending)} pending approval(s) in queue"
        })
    except Exception as e:
        results.append({
            "subsystem": "Safety Gate (§11)",
            "status": "FAIL",
            "latency": "N/A",
            "detail": str(e)
        })

    rows = ""
    for r in results:
        badge_cls = "badge-content" if r["status"] == "PASS" else ("badge-daily" if r["status"] == "WARN" else "badge-automation")
        icon = "🟢" if r["status"] == "PASS" else ("🟡" if r["status"] == "WARN" else "🔴")
        rows += f"""
        <tr>
            <td style="font-weight: 600;">{r['subsystem']}</td>
            <td><span class="badge {badge_cls}">{icon} {r['status']}</span></td>
            <td><code>{r['latency']}</code></td>
            <td style="color: var(--text-muted); font-size: 0.85rem;">{r['detail']}</td>
        </tr>
        """

    return HTMLResponse(f"""
    <div id="self-test-container" style="margin-top: 1rem; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
            <strong>🧪 System Diagnostics Report</strong>
            <span style="font-size: 0.8rem; color: var(--text-muted);">{datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}</span>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Subsystem</th>
                    <th>Status</th>
                    <th>Latency</th>
                    <th>Details</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
    </div>
    """)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
