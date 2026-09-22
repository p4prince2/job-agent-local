# 🤖 Prince AI Team - Personal Multi-Agent AI Assistant

**Prince AI Team** is an autonomous personal AI assistant built for **Prince** ([@p4prince2](https://github.com/p4prince2)). It coordinates a squad of specialized AI agents to handle daily engineering work, GATE preparation, GitHub repository reviews, and high-impact technical content creation.

Built to run **100% locally and privately for free** using **Ollama** and **`llama3.2`** (with zero API costs), backed by a persistent SQLite database, a safety-first human approval guardrail, and an interactive Streamlit web dashboard.

---

## 🏛️ System Architecture

```
                                  ┌───────────────────────────────┐
                                  │    Streamlit Web Dashboard    │
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
      │  (LinkedIn/X Posts, │          │  (Structure Audit,  │         │   (GATE Prep & AI   │
      │   Hooks & Drafts)   │          │  Tests & CI Review) │         │  Tasks & Reminders) │
      └──────────┬──────────┘          └──────────┬──────────┘         └──────────┬──────────┘
                 │                                │                               │
                 └────────────────────────────────┼───────────────────────────────┘
                                                  │
                                  ┌───────────────┴───────────────┐
                                  ▼                               ▼
                   ┌─────────────────────────────┐  ┌─────────────────────────────┐
                   │  Computer Automation Agent  │  │   Human Approval Guardrail  │
                   │ (Windows Files & Execution) │  │  (Confirms sensitive tasks) │
                   └──────────────┬──────────────┘  └─────────────┬───────────────┘
                                  │                               │
                                  └───────────────┬───────────────┘
                                                  │
                                                  ▼
                                  ┌───────────────────────────────┐
                                  │    SQLite Database & Engine   │
                                  │    (data/prince_ai.db)        │
                                  └───────────────────────────────┘
```

---

## 👥 The 4 Specialized Agents (+ Supervisor)

### 1. 👑 Supervisor Agent (`SupervisorAgent`)
- Coordinates the team, breaks down natural language goals, selects required agents, passes shared context between agents, and delivers a unified executive summary.
- Supports single-agent requests and compound workflows (e.g. *"Review my GitHub repo and write a LinkedIn post about it"*).

### 2. ✍️ Content Agent (`ContentAgent`)
- **Niche Focus:** AI, Machine Learning, LLMs, AI Agents, AI Safety, MLOps.
- Formulates high-impact LinkedIn posts and X (Twitter) threads.
- Generates 3 distinct hook variations (Contrarian, Behind-the-Scenes, Actionable).
- Persists drafts locally in SQLite with `#ID`.
- **Safety Guarantee:** Never publishes directly to social media without human approval.

### 3. 🐙 GitHub Agent (`GitHubAgent`)
- Audits public repositories for [`p4prince2`](https://github.com/p4prince2) or local projects.
- Inspects repository structure, dependency hygiene (`requirements.txt`, `pyproject.toml`), README clarity, tests, and CI/CD workflows.
- Recommends concrete architecture improvements and proposes clean Git branch names (`improvements/code-quality-and-tests`).
- **Safety Guarantee:** Never deletes repositories, pushes to main, or merges PRs without approval.

### 4. 📋 Daily Work Agent (`DailyWorkAgent`)
- Manages tasks across **GATE Prep**, **AI/ML Projects**, **GitHub Work**, and **Content Creation**.
- Decomposes high-level goals into concrete, bite-sized daily tasks with priorities (`high`, `medium`, `low`).
- Stores verified reminders in SQLite.
- **Safety Guarantee:** Never claims a reminder was created unless a real database entry was made.

### 5. 💻 Computer Automation Agent (`ComputerAgent`)
- Inspects project files and directories safely on Windows.
- Explains planned actions transparently before doing them.
- Quarantines destructive or system-modifying actions into the **Human Approval Center**.

---

## 🚀 Quickstart Guide

### Prerequisites
1. **Python 3.10+** (Tested on Python 3.12).
2. **Ollama** installed with `llama3.2` model:
   ```bash
   ollama pull llama3.2
   ```

### 1. Clone & Setup
```bash
git clone https://github.com/p4prince2/prince-ai-team.git
cd prince-ai-team
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure (Optional)
The application works immediately out-of-the-box with local Ollama! If you want to customize settings or add optional API keys, review `.env`:
```bash
cp .env.example .env
```

### 4. Launch the Dashboard
Run the one-click launcher:
```bash
python run.py
```
Or run Streamlit directly:
```bash
streamlit run ui/app.py
```

The web dashboard will automatically open at:
👉 **`http://localhost:8501`**

---

## 🖥️ Dashboard Features

| Tab | Description |
|---|---|
| **💬 Team Workspace** | Chat with the Supervisor, view real-time multi-agent execution steps, and review the final response. |
| **📋 Daily Work & GATE** | Filterable task board (GATE, AI/ML, GitHub, Content), toggle completion, create new tasks, and view active reminders. |
| **✍️ Content Lab** | Browse saved LinkedIn and X drafts, compare hook variations, edit draft content, and copy to clipboard. |
| **🐙 GitHub Inspector** | Audit any repo on `github.com/p4prince2` or local paths, view code structure, test health, and architectural suggestions. |
| **🛡️ Approval Center** | Review pending sensitive/external actions with single-click **Approve** or **Reject** buttons. |
| **📜 Activity Logs** | Real-time audit log of every thought, decision, and tool call made by any agent. |
| **⚙️ Settings** | Verify AI connectivity, switch LLM models, and view system configurations. |

---

## 🧪 Testing

Run the automated test suites:

```bash
# Test Core Agents & Database Persistence
python -m unittest tests/test_agents.py

# Test Compound Multi-Agent Workflow (GitHub -> Content -> Supervisor)
python -m unittest tests/test_workflow.py
```

---

## 🗺️ What Remains for Future Phases

With the Phase 1 MVP fully operational, here is the technical roadmap for upcoming integrations:

### 1. 🖥️ Computer Automation (Expanded OS Control)
- **What remains:** Add `pyautogui` and Windows UI Automation (`pywinauto`) to safely control application windows and automate repetitive desktop steps.
- **Safeguard:** Every automated macro will require confirmation in the Human Approval Center before executing.

### 2. 🌐 Browser Automation
- **What remains:** Integrate **Playwright** (`playwright-python`) in headless or headed mode to automate web forms, research scraping, and documentation searches.
- **Safeguard:** Explicit domain whitelist so agents only browse approved sites.

### 3. 🐙 GitHub Write Access
- **What remains:** Configure a GitHub Personal Access Token (`GITHUB_TOKEN` in `.env`) with `repo` scope to enable:
  - Creating new branches automatically.
  - Committing refactored code and unit test additions.
  - Opening Pull Requests for Prince's review.

### 4. 🔔 System Notifications & Reminders
- **What remains:** Integrate `win10toast` or `plyer` to trigger native Windows notification toasts when reminders fire or when an agent requests approval.
- **Background scheduler:** A lightweight background thread (`APScheduler`) to monitor SQLite `reminders` table and trigger toast notifications at exact timestamps.

### 5. 📢 Direct Social Media Publishing
- **What remains:**
  - **LinkedIn:** Official LinkedIn REST API v2 using OAuth2 tokens to publish approved drafts with 1-click.
  - **X (Twitter):** Tweepy / Twitter API v2 integration for automated posting of approved threads.
  - **Safeguard:** Approval Center button: "Approve & Publish Live".

---

## 🛡️ Privacy & Security
- **No data leaks:** All data, logs, drafts, and tasks remain strictly in `data/prince_ai.db` on your local disk.
- **Local AI:** All inferences run through your local Ollama instance on `localhost:11434`.
- **Zero API keys required:** Runs completely free of charge.
