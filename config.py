"""Central configuration module for Prince AI Team (per SPEC.md v2)."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory is the project root
BASE_DIR = Path(__file__).resolve().parent

# Load .env file
load_dotenv(BASE_DIR / ".env")

# Database (SQLAlchemy connection string)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/prince_ai_team.db")

# LLM Provider Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# User Profile & GitHub Settings
USER_NAME = "Prince"
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "p4prince2")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# Technical Niches (Domain Constants)
TECH_NICHES = [
    "AI",
    "Machine Learning",
    "LLMs",
    "AI Agents",
    "AI Safety",
    "MLOps"
]

# Daily Work Categories / Tags (§9)
PROJECT_TAGS = [
    "gate_prep",
    "ai_ml",
    "github",
    "content"
]

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = BASE_DIR / os.getenv("LOG_DIR", "data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Ensure data directory exists
if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    Path(db_path).resolve().parent.mkdir(parents=True, exist_ok=True)
