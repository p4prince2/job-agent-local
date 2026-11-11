# 🤖 Prince AI Team - Personal Multi-Agent AI Assistant

**Prince AI Team** is a local-first multi-agent AI assistant built according to [SPEC.md](file:///c:/Users/p4pri/prince-ai-team/SPEC.md) for **Prince** ([@p4prince2](https://github.com/p4prince2)).

It coordinates a squad of specialized AI agents across daily engineering work, GATE preparation, GitHub repository audits, and high-impact technical content creation.

Built with **FastAPI**, **Jinja2 + HTMX**, and **SQLAlchemy + SQLite**, running **100% locally and privately for free** using **Ollama** (`llama3.2` / `qwen3` / `llama3.3`) with zero required API keys.

---

## 🏛️ System Architecture

```
                                  ┌───────────────────────────────┐
                                  │     FastAPI + HTMX Dashboard  │
                                  │ (Chat, Tasks, Drafts, Repos,  │
                                  │      Logs & Safety Queue)     │
                                  └───────────────┬───────────────┘
                                                  │
                                                  ▼
                                  ┌───────────────────────────────┐
                                  │       Supervisor Agent        │
                                  │  (Intent Planning, Routing &  │
                                  │      Executive Synthesis)     │
                                  └───────────────┬───────────────┘
                                                  │
                 ┌────────────────────────────────┼───────────────────────────────┐
                 ▼                                ▼                               ▼
      ┌─────────────────────┐          ┌─────────────────────┐         ┌─────────────────────┐
      │    Content Agent    │          │    GitHub Agent     │         │  Daily Work Agent   │
      │  (Original 6-part   │          │  (Structure Audit,  │         │   (GATE Prep & AI   │
      │   Posts & Replies)  │          │  Tests & CI Review) │         │  Tasks & Reminders) │
      └──────────┬──────────┘          └──────────┬──────────┘         └──────────┬──────────┘
                 │                                │                               │
                 └────────────────────────────────┼───────────────────────────────┘
                                                  │
                                  ┌───────────────┴───────────────┐
                                  ▼                               ▼
                   ┌─────────────────────────────┐  ┌─────────────────────────────┐
                   │  Computer Automation Agent  │  │   Human Approval Guardrail  │
                   │    (Phase 2 Stub - §10)     │  │  (Confirms sensitive tasks) │
                   └──────────────┬──────────────┘  └─────────────┬───────────────┘
                                  │                               │
                                  └───────────────┬───────────────┘
                                                  │
                                                  ▼
                                  ┌───────────────────────────────┐
                                  │   SQLite Database Engine      │
                                  │   (data/prince_ai_team.db)    │
                                  └───────────────────────────────┘
```

---

## 👥 Specialized Agents (§6–§10)

### 1. 👑 Supervisor Agent (`agents/supervisor.py`)
- Fast keyword/intent pass to shortlist candidate agents (instant, no LLM call).
- Small LLM call to confirm shortlist and extract sub-instructions.
- Chained context passed forward as structured data (e.g. GitHub review $\rightarrow$ Content Agent).
- Computer Automation requests return a clear "agent not implemented yet" notice per §10.
- Executive synthesis with direct references to created drafts, work items, and reports.

### 2. ✍️ Content Agent (`agents/content_agent.py`)
- **Niche Focus:** AI, Machine Learning, LLMs, AI Agents, AI Safety, MLOps.
- **Original Posts:** 6-part structure (Hook, Context, Explanation, Personal Take, Forward Implication, Closing Question) generating:
  - Professional LinkedIn post
  - Expanded Medium article
  - Condensed X (Twitter) post
  - Cover image prompt
- **Replies & Comments:** Analyzes target post, verifies claims, finds 1 non-obvious angle, produces up to 3 ranked drafts.
- **Quality Gate:** Strict ban on generic praise, generic summaries, forced questions, hashtags, and decorative emojis.
- All outputs saved to SQLite `drafts` table with `status="draft"`. Never auto-published.

### 3. 🐙 GitHub Agent (`agents/github_agent.py`)
- Read-only inspection of [`p4prince2`](https://github.com/p4prince2) or local repos.
- Scrapes repo tree, README, test suites, CI workflows, dependency manifests (`requirements.txt`, `pyproject.toml`, etc.), and code layout.
- Saves structured JSON report and human summary to `github_reviews`.

### 4. 📋 Daily Work Agent (`agents/daily_work_agent.py`)
- Manages `work_items` tagged by `gate_prep`, `ai_ml`, `github`, and `content`.
- Decomposes high-level goals into prioritized subtasks (`parent_id`).
- In-app reminders stored in `reminders` table and displayed on the dashboard.

### 5. 💻 Computer Automation Agent (`agents/automation_agent.py`)
- Phase 2 stub per §10. Fails clearly with an explicit message explaining Phase 2 availability rather than failing silently.

---

## 🛡️ Approval & Safety Gate (§11)

Managed by `approvals/manager.py` with persistent queue in `approvals` table.
The following actions **always require human confirmation**:
- Sending messages
- Publishing content to LinkedIn, Medium, or X
- Deleting files or folders
- Financial purchases
- System modifications
- GitHub branch creation, commits, or pull requests

---

## 🚀 Quickstart & How to Run

### 1. Prerequisites
- Python 3.10+ (Tested on Python 3.12)
- Ollama with `llama3.2` (or `qwen3` / `llama3.3`):
  ```bash
  ollama pull llama3.2
  ```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Start the Server
Run the one-click launcher:
```bash
python run.py
```
Or start Uvicorn directly:
```bash
uvicorn main:app --reload
```

Open your browser at:
👉 **`http://127.0.0.1:8000`**

---

## 🖥️ Dashboard Navigation (§13)

Features a responsive **Dark/Light Mode Toggle**, global **In-App Reminder Banners** (with 1-hour Snooze & Dismiss), and one-click **Markdown / Log Exporters** across all views.

| Route | View | Description |
|---|---|---|
| `/` | 💬 Console | Task input, quick templates (including X URL ingestion), live metrics strip, Supervisor pipeline trace, and HTMX polling. |
| `/tasks` | 📋 Tasks | Full task history table with status filtering, expandable agent trace accordions, **Re-run**, and `.md` audit export. |
| `/drafts` | ✍️ Drafts | Saved drafts filterable by platform (`linkedin`, `medium`, `x`, `image_prompt`), approval status, keyword search, publish-approval gating, and bulk `.md` digest export. |
| `/work` | 📅 Daily Work | Tasks & subtasks filterable by tag (`gate_prep`, `ai_ml`, `github`, `content`) & title search, AI **Decompose**, reminder scheduler/snoozer, and checklist `.md` export. |
| `/github` | 🐙 GitHub | Interactive repository audit runner, structured telemetry inspector, one-click **Repurpose into Drafts**, and `.md` export. |
| `/approvals` | 🛡️ Approvals | Safety gate queue with HTMX **Approve / Reject** (auto-cascading to linked drafts), status filters, and audit `.md` export. |
| `/logs` | 📜 Logs | Structured activity trail filterable by agent, severity level, and text search, with `.txt` export and cleanup. |

---

## 🧪 Testing

Run all automated test suites cleanly with:

```bash
python -m unittest discover tests
```

Or run individual test modules:

```bash
# Approval Gate & Draft Cascade Tests
python -m unittest tests/test_approvals.py

# Supervisor Routing, Compound Sub-Instructions & Automation Stub Tests
python -m unittest tests/test_supervisor.py

# Content Agent Dual Pipelines & Quality Gate Tests
python -m unittest tests/test_content_agent.py

# GitHub Agent Read-Only Audit & Local Telemetry Tests
python -m unittest tests/test_github_agent.py

# FastAPI HTTP Routes, HTMX, Exporters & Reminder Tests
python -m unittest tests/test_routes.py
```
