"""Configuration module for Prince AI Team."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory is the project root
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env if it exists
load_dotenv(BASE_DIR / ".env")

# Model / Provider Config
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

# User Profile Config
USER_NAME = "Prince"
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "p4prince2")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# Specialization Niches
TECH_NICHES = [
    "AI",
    "Machine Learning",
    "LLMs",
    "AI Agents",
    "AI Safety",
    "MLOps"
]

TASK_CATEGORIES = [
    "GATE Prep",
    "AI/ML Projects",
    "GitHub Work",
    "Content Creation",
    "System / General"
]

# Database Path
DB_RELATIVE_PATH = os.getenv("DATABASE_PATH", "data/prince_ai.db")
DATABASE_PATH = BASE_DIR / DB_RELATIVE_PATH

# Ensure data directory exists
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
