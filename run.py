"""One-Click Launcher for Prince AI Team.

Initializes database, verifies local Ollama AI model, and starts
the interactive Streamlit dashboard.
"""

import sys
import subprocess
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.database import init_db
from core.llm import default_llm


def banner():
    print("=" * 65)
    print("           🤖 PRINCE AI TEAM - MULTI-AGENT ASSISTANT          ")
    print("      Personal AI Engineering, GATE Prep & Content Team      ")
    print("=" * 65)


def main():
    banner()
    print("\n[1/3] Initializing local SQLite database...")
    init_db()
    print("  -> Database tables initialized at data/prince_ai.db")

    print("\n[2/3] Checking local AI status (Ollama)...")
    status = default_llm.check_status()
    if status.get("online"):
        print(f"  -> [OK] Ollama is ONLINE at {status.get('host')}")
        print(f"  -> [OK] Model: '{default_llm.model}' (Free, offline, private)")
    else:
        print(f"  -> [WARN] {status.get('message')}")
        print("  -> To start Ollama in the background, run: `ollama serve`")

    print("\n[3/3] Launching Prince AI Team Dashboard...")
    print("  -> Opening browser at http://localhost:8501")
    print("=" * 65)
    print("Press Ctrl+C in this terminal to stop the application.\n")

    app_path = PROJECT_ROOT / "ui" / "app.py"
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        str(app_path),
        "--server.headless=false",
        "--theme.base=light"
    ])


if __name__ == "__main__":
    main()
