"""Main FastAPI application for Prince AI Team (per SPEC.md v2).

Serves server-rendered Jinja2 + HTMX dashboard on 127.0.0.1:8000.
Supports asynchronous background agent runs with HTMX live polling,
in-process APScheduler reminders, and safety approval management.
"""

from typing import Optional
from datetime import datetime, timezone
from fastapi import FastAPI, Request, Form, Depends, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler

from config import BASE_DIR
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


def check_due_reminders():
    """Background check for due in-app reminders (§3)."""
    db = SessionLocal()
    try:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        due_reminders = db.query(Reminder).filter(
            Reminder.fired == False,
            Reminder.remind_at <= now_str
        ).all()

        for rem in due_reminders:
            rem.fired = True
            db.commit()
            task_title = rem.work_item.title if hasattr(rem, 'work_item') and rem.work_item else "Scheduled Check-in"
            msg = f"🔔 IN-APP REMINDER: Check-in due for '{task_title}' (Scheduled: {rem.remind_at})"
            log_event("DailyWorkAgent", msg, level="INFO")
            logger.info(msg)
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
    """Helper providing global variables to templates like approval badge counters."""
    pending_count = len(ApprovalManager.get_pending_approvals(db=db))
    return {
        "active_tab": active_tab,
        "pending_approvals_count": pending_count
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


# ----------------------------------------------------------------------
# 2. Tasks History
# ----------------------------------------------------------------------
@app.get("/tasks", response_class=HTMLResponse)
def tasks_page(request: Request, status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Task)
    if status and status != "all":
        query = query.filter(Task.status == status.lower())
    tasks = query.order_by(Task.created_at.desc()).limit(50).all()
    context = get_common_context(db, active_tab="tasks")
    context.update({
        "tasks": tasks,
        "selected_status": status or "all"
    })
    return templates.TemplateResponse(request=request, name="tasks.html", context=context)


# ----------------------------------------------------------------------
# 3. Content Drafts (CRUD)
# ----------------------------------------------------------------------
@app.get("/drafts", response_class=HTMLResponse)
def drafts_page(request: Request, platform: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Draft)
    if platform and platform != "all":
        query = query.filter(Draft.platform == platform.lower())
    drafts = query.order_by(Draft.created_at.desc()).all()

    context = get_common_context(db, active_tab="drafts")
    context.update({
        "drafts": drafts,
        "selected_platform": platform or "all"
    })
    return templates.TemplateResponse(request=request, name="drafts.html", context=context)


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


# ----------------------------------------------------------------------
# 4. Daily Work & Reminders (CRUD)
# ----------------------------------------------------------------------
@app.get("/work", response_class=HTMLResponse)
def work_page(request: Request, tag: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(WorkItem)
    if tag and tag != "all":
        query = query.filter(WorkItem.project_tag == tag.lower())
    work_items = query.order_by(WorkItem.created_at.desc()).all()
    reminders = db.query(Reminder).order_by(Reminder.remind_at.asc()).all()

    context = get_common_context(db, active_tab="work")
    context.update({
        "work_items": work_items,
        "reminders": reminders,
        "selected_tag": tag or "all"
    })
    return templates.TemplateResponse(request=request, name="work.html", context=context)


@app.post("/work/create")
def create_work_item_endpoint(
    title: str = Form(...),
    project_tag: str = Form("general"),
    priority: str = Form("medium"),
    due_date: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    item = WorkItem(
        title=title.strip(),
        project_tag=project_tag,
        priority=priority,
        due_date=due_date,
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
        db.commit()
        db.refresh(item)
    if request.headers.get("HX-Request") and item:
        is_done = item.status == "done"
        checked = "checked" if is_done else ""
        line_style = "text-decoration: line-through; color: var(--text-muted);" if is_done else "font-weight: 600;"
        bg_style = "#F8FAFC" if is_done else "var(--surface)"
        badge_cls = "badge-content" if is_done else "badge-daily"
        subtask_style = "margin-left: 1.5rem; border-left: 3px solid var(--primary);" if item.parent_id else ""
        subtask_prefix = '<span style="color: var(--primary); font-size: 0.85rem; margin-right: 0.2rem;">↳</span>' if item.parent_id else ""
        subtask_note = f'<span style="font-size: 0.7rem; color: var(--primary); margin-left: 0.4rem;">[Subtask of #{item.parent_id}]</span>' if item.parent_id else ""
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


# ----------------------------------------------------------------------
# 5. GitHub Reviews
# ----------------------------------------------------------------------
@app.get("/github", response_class=HTMLResponse)
def github_page(request: Request, db: Session = Depends(get_db)):
    reviews = db.query(GitHubReview).order_by(GitHubReview.created_at.desc()).all()
    context = get_common_context(db, active_tab="github")
    context.update({"reviews": reviews})
    return templates.TemplateResponse(request=request, name="github.html", context=context)


# ----------------------------------------------------------------------
# 6. Approval Queue & Safety Center
# ----------------------------------------------------------------------
@app.get("/approvals", response_class=HTMLResponse)
def approvals_page(request: Request, status: Optional[str] = None, db: Session = Depends(get_db)):
    pending = ApprovalManager.get_pending_approvals(db=db)
    query = db.query(Approval)
    if status and status != "all":
        query = query.filter(Approval.status == status.lower())
    all_apps = query.order_by(Approval.created_at.desc()).limit(50).all()
    context = get_common_context(db, active_tab="approvals")
    context.update({
        "pending_approvals": pending,
        "all_approvals": all_apps,
        "selected_status": status or "all"
    })
    return templates.TemplateResponse(request=request, name="approvals.html", context=context)


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


# ----------------------------------------------------------------------
# 7. Logs Viewer
# ----------------------------------------------------------------------
@app.get("/logs", response_class=HTMLResponse)
def logs_page(request: Request, agent: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Log)
    if agent and agent != "all":
        query = query.filter(Log.agent_name == agent)
    logs = query.order_by(Log.created_at.desc()).limit(100).all()

    context = get_common_context(db, active_tab="logs")
    context.update({
        "logs": logs,
        "selected_agent": agent or "all"
    })
    return templates.TemplateResponse(request=request, name="logs.html", context=context)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
