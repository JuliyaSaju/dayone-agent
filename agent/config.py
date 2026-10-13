"""Settings come from environment variables (see .env.example)."""
import os

from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "")

MM_URL = os.getenv("MM_URL", "http://localhost:8065")
MM_ADMIN_EMAIL = os.getenv("MM_ADMIN_EMAIL", "admin@example.test")
MM_ADMIN_PASSWORD = os.getenv("MM_ADMIN_PASSWORD", "Admin-Pass-12345!")
MM_TEAM = os.getenv("MM_TEAM", "acme")

GITEA_URL = os.getenv("GITEA_URL", "http://localhost:3000")
GITEA_TOKEN = os.getenv("GITEA_TOKEN", "")
GITEA_OWNER = os.getenv("GITEA_OWNER", "dayone-admin")

DEMO_USER_PASSWORD = os.getenv("DEMO_USER_PASSWORD", "Welcome-Pass-2026!x")
FAULTS = os.getenv("FAULTS", "")
