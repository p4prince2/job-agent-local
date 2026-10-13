"""One-Click Launcher for Prince AI Team (SPEC.md v2).

Runs pre-flight checks on SQLite database and local Ollama model,
then starts the FastAPI + HTMX dashboard on http://127.0.0.1:8000.
"""

import sys
import uvicorn
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import init_db
from llm import default_provider


import argparse


def banner():
    print("=" * 65)
    print("            [+] PRINCE AI TEAM - MULTI-AGENT ASSISTANT          ")
    print("        FastAPI + HTMX | SQLite | 100% Local Ollama        ")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="Prince AI Team Launcher")
    parser.add_argument("--check", action="store_true", help="Run pre-flight checks and exit")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the dashboard on (default: 8000)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    args = parser.parse_args()

    banner()
    print("\n[1/3] Initializing SQLite database...")
    init_db()
    print("  -> [OK] Database schema initialized (data/prince_ai_team.db)")

    print("\n[2/3] Verifying Local AI Provider (Ollama)...")
    status = default_provider.check_status()
    if status.get("online"):
        print(f"  -> [OK] Ollama is ONLINE at {status.get('host')}")
        print(f"  -> [OK] Active model: '{status.get('model')}' (Free, offline, private)")
    else:
        print(f"  -> [WARN] {status.get('message')}")
        print("  -> Ensure Ollama is running in the background: `ollama serve`")

    if args.check:
        print("\n[Pre-flight Checks Completed Successfully]")
        return

    print("\n[3/3] Launching FastAPI + HTMX Dashboard...")
    print(f"  -> Dashboard URL: http://{args.host}:{args.port}")
    print("=" * 65)
    print("Press Ctrl+C to stop the server.\n")

    uvicorn.run("main:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
