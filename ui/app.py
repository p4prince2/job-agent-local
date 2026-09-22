"""Prince AI Team - Streamlit Dashboard.

Personal multi-agent AI assistant dashboard for Prince:
- Supervisor Agent (Orchestration & Workflow Synthesis)
- Content Agent (LinkedIn & X Posts, Hooks, Local Drafts)
- GitHub Agent (Repo inspection, architecture, code quality, test audit)
- Daily Work Agent (GATE prep, AI/ML tasks, day planner, persistent SQLite tasks)
- Computer Automation Agent (Safe system actions, human approval guardrails)
"""

import streamlit as st
import json
import time
from datetime import datetime
from typing import Dict, Any, List

# Core modules
from core.config import USER_NAME, GITHUB_USERNAME, OLLAMA_MODEL, TECH_NICHES, TASK_CATEGORIES
from core.database import (
    init_db, list_tasks, update_task_status, create_task, delete_task,
    list_drafts, update_draft, list_github_reviews,
    list_pending_approvals, decide_approval, list_all_approvals,
    get_recent_logs, get_chat_history, list_reminders, create_reminder
)
from core.llm import default_llm
from agents.supervisor import default_supervisor
from agents.github_agent import GitHubAgent
from agents.content_agent import ContentAgent
from agents.daily_work_agent import DailyWorkAgent
from tools.github_tools import default_github_tools

# Page Configuration
st.set_page_config(
    page_title="Prince AI Team | Personal Multi-Agent Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database
init_db()

# Custom CSS for polished, clean UI
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #4F46E5, #06B6D4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #6B7280;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .agent-badge {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-right: 0.4rem;
        margin-bottom: 0.4rem;
    }
    .badge-supervisor { background-color: #EDE9FE; color: #6D28D9; border: 1px solid #DDD6FE; }
    .badge-content { background-color: #ECFDF5; color: #047857; border: 1px solid #A7F3D0; }
    .badge-github { background-color: #EFF6FF; color: #1D4ED8; border: 1px solid #BFDBFE; }
    .badge-daily { background-color: #FEF3C7; color: #B45309; border: 1px solid #FDE68A; }
    .badge-computer { background-color: #FEE2E2; color: #B91C1C; border: 1px solid #FECACA; }
    .stat-box {
        background-color: #F9FAFB;
        border: 1px solid #E5E7EB;
        border-radius: 0.5rem;
        padding: 1rem;
        text-align: center;
    }
    .approval-alert {
        background-color: #FEF2F2;
        border: 1px solid #F87171;
        border-radius: 0.5rem;
        padding: 0.75rem;
        margin-bottom: 1rem;
        color: #991B1B;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------------------------
# Sidebar: System Health, Stats & Roster
# ----------------------------------------------------------------------

with st.sidebar:
    st.markdown("### 👑 Prince AI Team")
    st.markdown(f"**Operator:** {USER_NAME} (`{GITHUB_USERNAME}`)")
    
    # Check LLM status
    llm_status = default_llm.check_status()
    if llm_status.get("online"):
        st.success(f"🟢 Local AI Online ({default_llm.model})")
    else:
        st.error(f"🔴 AI Offline ({llm_status.get('message', 'Check Ollama')})")

    st.markdown("---")
    
    # Quick Metrics
    pending_tasks = len(list_tasks(status="pending"))
    saved_drafts = len(list_drafts())
    pending_approvals = len(list_pending_approvals())
    reviews_count = len(list_github_reviews())

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.metric("Tasks", pending_tasks)
        st.metric("Drafts", saved_drafts)
    with col_s2:
        st.metric("Reviews", reviews_count)
        st.metric("Approvals", pending_approvals, delta=f"{pending_approvals} pending" if pending_approvals else None, delta_color="inverse")

    if pending_approvals > 0:
        st.warning(f"⚠️ {pending_approvals} action(s) require your human approval!")

    st.markdown("---")
    st.markdown("#### 🤖 Agent Roster")
    st.markdown("""
    - 👑 **Supervisor**: Multi-agent Orchestrator
    - ✍️ **Content Agent**: LinkedIn & X Posts
    - 🐙 **GitHub Agent**: Repo Review & Quality
    - 📋 **Daily Work**: GATE & AI/ML Planner
    - 💻 **Computer Agent**: Safe OS Automation
    """)
    
    st.markdown("---")
    st.markdown("#### 🎯 Technical Focus")
    for niche in TECH_NICHES:
        st.caption(f"• {niche}")

# ----------------------------------------------------------------------
# Main Dashboard Tabs
# ----------------------------------------------------------------------

st.markdown('<div class="main-header">Prince AI Team</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Personal Multi-Agent AI Assistant for AI/ML Engineering, GATE Prep, GitHub, & Content</div>', unsafe_allow_html=True)

tabs = st.tabs([
    "💬 Team Workspace",
    "📋 Daily Work & GATE",
    "✍️ Content Lab & Drafts",
    "🐙 GitHub Inspector",
    "🛡️ Human Approval Center",
    "📜 Agent Activity Logs",
    "⚙️ Settings"
])

# ----------------------------------------------------------------------
# TAB 1: Team Workspace (Chat & Multi-Agent Orchestrator)
# ----------------------------------------------------------------------
with tabs[0]:
    st.markdown("#### 💬 Multi-Agent Command Center")
    st.info("💡 Type any request. The Supervisor Agent will automatically analyze your goal, select the appropriate specialized agents, execute the workflow, and save all results to your local database.")

    # Preset prompt suggestions
    st.markdown("**Quick Prompts:**")
    col_p1, col_p2, col_p3 = st.columns(3)
    quick_prompt = None
    with col_p1:
        if st.button("🐙 Review GitHub & Write LinkedIn Post", use_container_width=True):
            quick_prompt = "Review my GitHub project prince-ai-team and create an engaging LinkedIn post about the architecture and improvements."
    with col_p2:
        if st.button("📋 Plan Today: GATE + AI/ML", use_container_width=True):
            quick_prompt = "Help me plan my day: 3 hours of GATE algorithms preparation and 2 hours of LLM fine-tuning experiment."
    with col_p3:
        if st.button("✍️ Write X Thread on AI Agents", use_container_width=True):
            quick_prompt = "Write an insightful X (Twitter) post explaining the difference between simple LLM chaining and autonomous AI agent architectures."

    # Task input form
    user_input = st.text_area(
        "Enter your instruction or goal for the team:",
        value=quick_prompt or "",
        height=90,
        placeholder="e.g. Review my GitHub project and create a LinkedIn post about the improvements."
    )

    col_btn, col_clear = st.columns([1, 5])
    with col_btn:
        run_submitted = st.button("🚀 Execute Task", type="primary", use_container_width=True)

    if run_submitted and user_input.strip():
        with st.spinner("🤖 Supervisor is planning and executing the multi-agent workflow with local Ollama..."):
            start_time = time.time()
            result = default_supervisor.execute_workflow(user_input.strip())
            elapsed = time.time() - start_time

        st.success(f"✅ Workflow completed in {elapsed:.1f}s!")

        # Display Pipeline Execution
        st.markdown("##### 🗺️ Execution Pipeline")
        pipeline_cols = st.columns(len(result["pipeline"]) + 1)
        with pipeline_cols[0]:
            st.markdown('<span class="agent-badge badge-supervisor">👑 Supervisor</span>', unsafe_allow_html=True)
            st.caption("Planned Workflow")

        for idx, agent_name in enumerate(result["pipeline"]):
            with pipeline_cols[idx + 1]:
                if agent_name == "GitHubAgent":
                    st.markdown('<span class="agent-badge badge-github">🐙 GitHub Agent</span>', unsafe_allow_html=True)
                elif agent_name == "ContentAgent":
                    st.markdown('<span class="agent-badge badge-content">✍️ Content Agent</span>', unsafe_allow_html=True)
                elif agent_name == "DailyWorkAgent":
                    st.markdown('<span class="agent-badge badge-daily">📋 Daily Work</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="agent-badge badge-computer">💻 Computer Agent</span>', unsafe_allow_html=True)
                st.caption(f"Step {idx+1}")

        # Step by step details
        st.markdown("---")
        st.markdown("##### 🔍 Step-by-Step Agent Results")
        for step in result.get("steps", []):
            with st.expander(f"📌 {step['agent']}: {step['summary']}", expanded=True):
                details = step["details"]
                if step["agent"] == "ContentAgent":
                    st.markdown(f"**Platform:** {details.get('platform', 'N/A').upper()} | **Draft ID:** #{details.get('draft_id')}")
                    st.markdown("**Hooks Suggested:**")
                    for h in details.get("hooks", []):
                        st.markdown(f"- *{h}*")
                    st.markdown("**Full Post Preview:**")
                    st.text_area("Content", value=details.get("content", ""), height=200, key=f"chat_content_{step['agent']}_{details.get('draft_id')}")
                elif step["agent"] == "GitHubAgent":
                    st.markdown(f"**Repository:** [{details.get('repo_name')}]({details.get('repo_url')})")
                    st.markdown(details.get("review", ""))
                elif step["agent"] == "DailyWorkAgent":
                    st.markdown(details.get("plan", ""))
                    if details.get("tasks_created"):
                        st.markdown("**Tasks Saved to Database:**")
                        for t in details["tasks_created"]:
                            st.markdown(f"- `#{t['id']}` **{t['title']}** ({t['category']}, Priority: {t['priority']})")
                elif step["agent"] == "ComputerAgent":
                    st.markdown(details.get("analysis", ""))
                    if details.get("approval_required"):
                        st.warning("⚠️ Action requires human confirmation in the Approval Center!")

        # Final Supervisor Executive Summary
        st.markdown("---")
        st.markdown("##### 👑 Supervisor Executive Summary")
        st.markdown(result["final_response"])

# ----------------------------------------------------------------------
# TAB 2: Daily Work & GATE Prep
# ----------------------------------------------------------------------
with tabs[1]:
    st.markdown("#### 📋 Daily Work & Task Management")
    st.caption("Organize your daily study and engineering routines across GATE, AI/ML Projects, and GitHub.")

    # Add task form
    with st.expander("➕ Add New Task", expanded=False):
        with st.form("new_task_form"):
            col_t1, col_t2, col_t3 = st.columns([3, 2, 1])
            with col_t1:
                t_title = st.text_input("Task Title", placeholder="e.g. Solve 20 GATE CS Algorithm PYQs")
            with col_t2:
                t_category = st.selectbox("Category", TASK_CATEGORIES)
            with col_t3:
                t_priority = st.selectbox("Priority", ["high", "medium", "low"])
            t_desc = st.text_area("Description (Optional)", placeholder="Notes or specific topics to cover")
            submit_task = st.form_submit_button("Create Task", type="primary")

            if submit_task and t_title.strip():
                new_id = create_task(title=t_title.strip(), description=t_desc, category=t_category, priority=t_priority)
                st.success(f"Task #{new_id} added successfully!")
                st.rerun()

    # Filters
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        cat_filter = st.selectbox("Filter by Category", ["All"] + TASK_CATEGORIES)
    with col_f2:
        status_filter = st.selectbox("Filter by Status", ["All", "pending", "completed"])

    tasks = list_tasks(category=cat_filter, status=status_filter)

    if not tasks:
        st.info("No tasks found matching current filter.")
    else:
        for t in tasks:
            col_check, col_info, col_del = st.columns([1, 10, 1])
            with col_check:
                is_done = t["status"] == "completed"
                checked = st.checkbox("", value=is_done, key=f"task_done_{t['id']}")
                if checked != is_done:
                    update_task_status(t["id"], "completed" if checked else "pending")
                    st.rerun()
            with col_info:
                priority_color = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t["priority"], "⚪")
                title_style = f"~~{t['title']}~~" if t["status"] == "completed" else f"**{t['title']}**"
                st.markdown(f"{priority_color} {title_style} `{t['category']}`")
                if t.get("description"):
                    st.caption(t["description"])
            with col_del:
                if st.button("🗑️", key=f"del_task_{t['id']}", help="Delete task"):
                    delete_task(t["id"])
                    st.rerun()

    # Active Reminders
    st.markdown("---")
    st.markdown("##### ⏰ Verified Reminders")
    reminders = list_reminders(status="active")
    if reminders:
        for r in reminders:
            st.markdown(f"🔔 **{r['title']}** — *Remind at:* `{r['remind_at']}`")
    else:
        st.caption("No active reminders. Ask DailyWorkAgent to set one when planning your schedule.")

# ----------------------------------------------------------------------
# TAB 3: Content Lab & Saved Drafts
# ----------------------------------------------------------------------
with tabs[2]:
    st.markdown("#### ✍️ Technical Content Lab")
    st.caption("Saved drafts for LinkedIn and X/Twitter. Content is stored locally and never published without approval.")

    # Generator quick action
    with st.expander("✨ Generate New Post Draft", expanded=False):
        with st.form("new_draft_form"):
            c_platform = st.selectbox("Platform", ["LinkedIn", "Twitter / X"])
            c_topic = st.text_area("Topic or Project Insight", placeholder="e.g. Why evaluations are the hardest part of building production AI agents.")
            c_submit = st.form_submit_button("Generate Draft", type="primary")

            if c_submit and c_topic.strip():
                with st.spinner("Generating draft with local Ollama..."):
                    c_agent = ContentAgent()
                    res = c_agent.execute(f"Write a {c_platform} post about: {c_topic.strip()}")
                st.success(f"Created Draft #{res['draft_id']}!")
                st.rerun()

    # Filter drafts
    draft_filter = st.selectbox("Filter Drafts", ["All", "linkedin", "twitter_x"])
    drafts = list_drafts(platform=draft_filter)

    if not drafts:
        st.info("No content drafts saved yet. Ask ContentAgent to generate one!")
    else:
        for d in drafts:
            badge_class = "badge-content" if d["platform"] == "linkedin" else "badge-github"
            with st.container():
                st.markdown(f"### {d['title']}")
                st.markdown(f"<span class='agent-badge {badge_class}'>{d['platform'].upper()}</span> `Draft #{d['id']}` • Created: {d['created_at'][:16]}", unsafe_allow_html=True)
                
                # Hooks
                if d.get("hook_variations"):
                    with st.expander("🎣 Hook Variations", expanded=False):
                        for idx, h in enumerate(d["hook_variations"], 1):
                            st.markdown(f"**Option {idx}:** *{h}*")

                # Content editor
                updated_content = st.text_area("Post Content", value=d["content"], height=200, key=f"draft_txt_{d['id']}")
                col_save, col_copy = st.columns([1, 4])
                with col_save:
                    if st.button("💾 Save Edits", key=f"save_draft_{d['id']}"):
                        update_draft(d["id"], updated_content)
                        st.success("Draft updated!")
                with col_copy:
                    st.caption("Ready to copy-paste when you decide to post manually.")
                st.markdown("---")

# ----------------------------------------------------------------------
# TAB 4: GitHub Inspector
# ----------------------------------------------------------------------
with tabs[3]:
    st.markdown("#### 🐙 GitHub Repository Inspector")
    st.caption(f"Auditing code structure, tests, dependencies, and architecture for `https://github.com/{GITHUB_USERNAME}`.")

    # Review Launcher
    with st.form("github_review_form"):
        col_g1, col_g2 = st.columns([3, 1])
        with col_g1:
            target_repo = st.text_input("Repository Name or Path", value="prince-ai-team", placeholder="e.g. prince-ai-team or owner/repo or local path")
        with col_g2:
            st.markdown("<br>", unsafe_allow_html=True)
            launch_review = st.form_submit_button("🔍 Run Full Review", type="primary")

        if launch_review and target_repo.strip():
            with st.spinner("Inspecting repository and generating architectural audit with local Ollama..."):
                gh_agent = GitHubAgent()
                gh_res = gh_agent.execute(f"Review repository {target_repo.strip()}")
            st.success(f"Review #{gh_res['review_id']} completed!")
            st.rerun()

    # List past reviews
    past_reviews = list_github_reviews(limit=5)
    if past_reviews:
        st.markdown("##### 📜 Recent Repository Reviews")
        for r in past_reviews:
            with st.expander(f"📁 {r['repo_name']} — Review #{r['id']} ({r['created_at'][:16]})", expanded=True):
                st.markdown(f"**Repository URL:** [{r['repo_url']}]({r['repo_url']})")
                if r.get("structure_analysis"):
                    st.markdown("**Structural Telemetry:**")
                    st.code(r["structure_analysis"])
                st.markdown("**Architectural Review:**")
                st.markdown(r["summary"])
                if r.get("recommendations"):
                    st.markdown("**Actionable Recommendations:**")
                    for rec in r["recommendations"]:
                        st.markdown(f"- ✅ {rec}")
    else:
        st.info("No repository reviews recorded yet. Run a review above!")

# ----------------------------------------------------------------------
# TAB 5: Human Approval Center (Safety Guardrail)
# ----------------------------------------------------------------------
with tabs[4]:
    st.markdown("#### 🛡️ Human Approval Center")
    st.caption("Safety guardrail: No agent is allowed to delete files, publish to social media, or alter systems without your explicit permission.")

    pending_list = list_pending_approvals()

    if pending_list:
        st.markdown(f'<div class="approval-alert">⚠️ <b>{len(pending_list)} Action(s) Waiting For Prince\'s Approval</b></div>', unsafe_allow_html=True)
        for req in pending_list:
            with st.container():
                st.markdown(f"##### Request #{req['id']}: `{req['action_type']}` by `{req['agent_name']}`")
                st.markdown(f"**Description:** {req['description']}")
                if req.get("payload"):
                    st.json(req["payload"])
                col_app, col_rej = st.columns([1, 4])
                with col_app:
                    if st.button("✅ Approve Action", key=f"app_{req['id']}", type="primary"):
                        decide_approval(req["id"], "approved")
                        st.success(f"Request #{req['id']} Approved.")
                        st.rerun()
                with col_rej:
                    if st.button("❌ Reject Action", key=f"rej_{req['id']}"):
                        decide_approval(req["id"], "rejected")
                        st.error(f"Request #{req['id']} Rejected.")
                        st.rerun()
                st.markdown("---")
    else:
        st.success("✅ All clear. No pending approval requests.")

    # Past approval decisions
    st.markdown("##### 📜 Decision History")
    all_approvals = list_all_approvals(limit=10)
    if all_approvals:
        for a in all_approvals:
            status_emoji = "✅" if a["status"] == "approved" else "❌" if a["status"] == "rejected" else "⏳"
            st.markdown(f"{status_emoji} **Request #{a['id']}** `{a['action_type']}` — *Status:* **{a['status'].upper()}** (Decided: {a.get('decided_at', 'Pending')[:16]})")
    else:
        st.caption("No past approval decisions recorded yet.")

# ----------------------------------------------------------------------
# TAB 6: Agent Activity Logs
# ----------------------------------------------------------------------
with tabs[5]:
    st.markdown("#### 📜 Live Agent Audit Trail")
    st.caption("Every thought, action, tool call, and decision made by any agent is logged here.")

    col_l1, col_l2 = st.columns(2)
    with col_l1:
        log_agent = st.selectbox("Filter by Agent", ["All", "SupervisorAgent", "ContentAgent", "GitHubAgent", "DailyWorkAgent", "ComputerAgent"])
    with col_l2:
        log_limit = st.slider("Max Logs to Show", min_value=20, max_value=200, value=50, step=10)

    logs = get_recent_logs(limit=log_limit, agent_name=log_agent)

    if logs:
        for l in logs:
            level_color = {
                "INFO": "blue",
                "WARNING": "orange",
                "ERROR": "red",
                "DEBUG": "gray"
            }.get(l["level"], "gray")
            timestamp = l["created_at"][11:19]
            st.markdown(f"`{timestamp}` :{level_color}[**[{l['level']}]**] **{l['agent_name']}**: {l['message']}")
            if l.get("details_json") and l["details_json"] != "{}":
                with st.expander("View Details", expanded=False):
                    st.code(l["details_json"], language="json")
    else:
        st.info("No logs found.")

# ----------------------------------------------------------------------
# TAB 7: Settings
# ----------------------------------------------------------------------
with tabs[6]:
    st.markdown("#### ⚙️ System Settings & AI Configuration")
    
    st.markdown("##### 🧠 AI Model Engine")
    st.markdown(f"- **Current Active Provider:** `{default_llm.provider.upper()}`")
    st.markdown(f"- **Current Model:** `{default_llm.model}`")
    st.markdown(f"- **Local Ollama Host:** `{default_llm.ollama_host}`")
    st.markdown("- **API Cost:** **$0.00** (Running 100% locally and privately)")

    if st.button("🔄 Test AI Connectivity"):
        status = default_llm.check_status()
        st.json(status)

    st.markdown("---")
    st.markdown("##### 👤 User Profile")
    st.markdown(f"- **Operator Name:** {USER_NAME}")
    st.markdown(f"- **GitHub:** [https://github.com/{GITHUB_USERNAME}](https://github.com/{GITHUB_USERNAME})")
    st.markdown(f"- **Local Database Path:** `{default_llm.model}` $\\rightarrow$ `data/prince_ai.db`")
