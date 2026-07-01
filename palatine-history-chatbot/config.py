"""Central configuration for the Palatine History Chatbot.

All settings can be overridden with environment variables (see .env.example).
"""
from __future__ import annotations

import os
from pathlib import Path

# Load a local .env file if python-dotenv is installed (optional convenience).
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional
    pass

# --- Paths -----------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
HISTORICAL_RECORDS_DIR = DATA_DIR / "historical_records"
HISTORICAL_SOCIETY_DIR = DATA_DIR / "historical_society"
MY_DOCUMENTS_DIR = DATA_DIR / "my_documents"
INDEX_PATH = DATA_DIR / "search_index.json"

# Every folder whose contents get indexed into the knowledge base.
CONTENT_DIRS = [
    HISTORICAL_RECORDS_DIR,
    HISTORICAL_SOCIETY_DIR,
    MY_DOCUMENTS_DIR,
]

# File extensions we know how to read as text (PDFs handled separately).
TEXT_EXTENSIONS = {".md", ".txt", ".text", ".markdown", ".csv"}
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".tif", ".tiff", ".bmp"}

# --- AI backend ------------------------------------------------------------
# Which provider powers chat answers and photo transcription.
# One of: "claude", "openai", "gemini", "local".
#   * gemini -> free tier (chat + photo transcription), needs a free API key
#   * If the chosen provider has no key, the app runs free "search-only" mode.
AI_PROVIDER = os.getenv("AI_PROVIDER", "claude").lower()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# Latest, most capable default; override with CLAUDE_MODEL if desired.
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-8")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# Google Gemini (free tier). Get a free key at https://aistudio.google.com/apikey
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# For AI_PROVIDER=local: a local Ollama-compatible endpoint + model.
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "llama3.2")
LOCAL_BASE_URL = os.getenv("LOCAL_BASE_URL", "http://localhost:11434")

# --- Retrieval -------------------------------------------------------------
# Approx. characters per chunk when splitting documents.
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1200"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
# How many chunks of context to feed the model per question.
TOP_K = int(os.getenv("TOP_K", "6"))

# --- Web app ---------------------------------------------------------------
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "5000"))

# Max size of an uploaded photo, in megabytes.
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))

# Rate limits for a public deployment (used if Flask-Limiter is installed).
# Format is Flask-Limiter syntax, e.g. "30 per hour" or "5 per minute".
RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "120 per hour")
RATE_LIMIT_ASK = os.getenv("RATE_LIMIT_ASK", "20 per minute;200 per day")
RATE_LIMIT_UPLOAD = os.getenv("RATE_LIMIT_UPLOAD", "5 per minute;30 per day")

# --- Scraper ---------------------------------------------------------------
HISTORICAL_SOCIETY_URL = os.getenv(
    "HISTORICAL_SOCIETY_URL", "https://palatinehistoricalsociety.com"
)
SCRAPER_USER_AGENT = os.getenv(
    "SCRAPER_USER_AGENT",
    "Mozilla/5.0 (compatible; PalatineHistoryBot/1.0; local research use)",
)
SCRAPER_DELAY_SECONDS = float(os.getenv("SCRAPER_DELAY_SECONDS", "1.0"))
SCRAPER_MAX_PAGES = int(os.getenv("SCRAPER_MAX_PAGES", "300"))
