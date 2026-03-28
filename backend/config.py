import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"
SESSIONS_DIR = BASE_DIR / "sessions"
UPLOADS_DIR = BASE_DIR / "uploads"

SESSIONS_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)

TENSORIX_API_KEY = os.getenv("TENSORIX_API_KEY", "")
TENSORIX_BASE_URL = "https://api.tensorix.ai/v1"
REASONING_MODEL = "deepseek/deepseek-r1-0528"
CHAT_MODEL = "deepseek/deepseek-chat-v3.1"

CHROMA_PERSIST_DIR = str(BASE_DIR / "chroma_db")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
