"""Main FastAPI application for Prince AI Team (per SPEC.md v2).

Serves server-rendered Jinja2 + HTMX dashboard on 127.0.0.1:8000.
Orchestrates SQLite database, Supervisor workflows, and safety approval queue.
"""

from typing import Optional
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from config import BASE_DIR
from db.models import Task, AgentRun, Draft, GitHubReview, WorkItem, Reminder, Approval, Log
from db.session import init_db, get_db
from agents.supervisor import default_supervisor
from approvals.manager import ApprovalManager
from logging_utils.logger import get_logger

logger = get_logger("MainApp")

# Initialize FastAPI application
app = FastAPI(title="Prince AI Team", description="Personal Multi-Agent AI Assistant")

# Mount static files and Jinja2 templates
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "dashboard" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "dashboard" / "templates"))


@app.on_event("startup")
def on_startup():
    """Initializes SQLite database tables and logger."""
    init_db()
    logger.info("Prince AI Team FastAPI server started on http://127.0.0.1:8000")


def get_common_context(db: Session, active_tab: str = "chat") -> dict:
    """Helper providing global variables to templates like approval badge counters."""
    pending_count = len(ApprovalManager.get_pending_approvals(db=db))
    return {
        "active_tab": active_tab,
        "pending_approvals_count": pending_count
    }


# ----------------------------------------------------------------------
# 1. Console / Home (Task Submission & Workflow Live View)
# ----------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    latest_task = db.query(Task).order_by(Task.created_at.desc()).first()
    context = get_common_context(db, active_tab="chat")
    context.update({
        "latest_task": latest_task,
        "executive_summary": None
    })
    return templates.TemplateResponse(request=request, name="index.html", context=context)


@app.post("/submit-task", response_class=HTMLResponse)
def submit_task(
    request: Request,
    prompt: str = Form(...),
    db: Session = Depends(get_db)
):
    # Execute workflow through Supervisor
    result = default_supervisor.execute_workflow(raw_input=prompt.strip(), db=db)
    
    # Reload latest task to show on page
    latest_task = db.query(Task).filter(Task.id == result["task_id"]).first()
    context = get_common_context(db, active_tab="chat")
    context.update({
        "latest_task": latest_task,
        "executive_summary": result.get("final_summary")
    })
    return templates.TemplateResponse(request=request, name="index.html", context=context)


# ----------------------------------------------------------------------
# 2. Tasks History
# ----------------------------------------------------------------------
@app.get("/tasks", response_class=HTMLResponse)
def tasks_page(request: Request, db: Session = Depends(get_db)):
    tasks = db.query(Task).order_by(Task.created_at.desc()).limit(50).all()
    context = get_common_context(db, active_tab="tasks")
    context.update({
        "tasks": tasks
    })
    return templates.TemplateResponse(request=request, name="tasks.html", context=context)


# ----------------------------------------------------------------------
# 3. Content Drafts
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


# ----------------------------------------------------------------------
# 4. Daily Work & Reminders
# ----------------------------------------------------------------------
@app.get("/work", response_class=HTMLResponse)
def work_page(request: Request, tag: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(WorkItem)
    if tag and tag != "all":
        query = query.filter(WorkItem.project_tag == tag.lower())
    work_items = query.order_by(WorkItem.created_at.desc()).all()
    reminders = db.query(Reminder).filter(Reminder.fired == False).order_by(Reminder.remind_at.asc()).all()

    context = get_common_context(db, active_tab="work")
    context.update({
        "work_items": work_items,
        "reminders": reminders,
        "selected_tag": tag or "all"
    })
    return templates.TemplateResponse(request=request, name="work.html", context=context)


@app.post("/work/toggle/{item_id}")
def toggle_work_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(WorkItem).filter(WorkItem.id == item_id).first()
    if item:
        item.status = "done" if item.status != "done" else "todo"
        db.commit()
    return RedirectResponse(url="/work", status_code=303)


# ----------------------------------------------------------------------
# 5. GitHub Reviews
# ----------------------------------------------------------------------
@app.get("/github", response_class=HTMLResponse)
def github_page(request: Request, db: Session = Depends(get_db)):
    reviews = db.query(GitHubReview).order_by(GitHubReview.created_at.desc()).all()
    context = get_common_context(db, active_tab="github")
    context.update({
        "reviews": reviews
    })
    return templates.TemplateResponse(request=request, name="github.html", context=context)


# ----------------------------------------------------------------------
# 6. Approval Queue & Safety Center
# ----------------------------------------------------------------------
@app.get("/approvals", response_class=HTMLResponse)
def approvals_page(request: Request, db: Session = Depends(get_db)):
    pending = ApprovalManager.get_pending_approvals(db=db)
    all_apps = ApprovalManager.get_all_approvals(limit=50, db=db)
    context = get_common_context(db, active_tab="approvals")
    context.update({
        "pending_approvals": pending,
        "all_approvals": all_apps
    })
    return templates.TemplateResponse(request=request, name="approvals.html", context=context)


@app.post("/approvals/resolve/{approval_id}")
def resolve_approval_endpoint(
    approval_id: int,
    decision: str = Form(...),
    db: Session = Depends(get_db)
):
    ApprovalManager.resolve_approval(approval_id, decision=decision, db=db)
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
