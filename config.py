import os
from dotenv import load_dotenv

load_dotenv()


def _as_bool(name: str, default: bool = False) -> bool:
	val = os.getenv(name)
	if val is None:
		return default
	return val.strip().lower() in {"1", "true", "yes", "on"}

# ── Database ──────────────────────────────────────────────
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "")

# ── LLM Provider ("ollama" | "groq" | "openai") ───────────
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()

# ── Ollama (local) ────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

# ── Groq (free cloud) ─────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")

# ── OpenAI (paid cloud) ───────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ── App behaviour ─────────────────────────────────────────
MAX_CORRECTION_ATTEMPTS = int(os.getenv("MAX_CORRECTION_ATTEMPTS", 3))
APP_ROLE = os.getenv("APP_ROLE", "admin").lower()

# ── SQL safety controls ────────────────────────────────────
# Keep DDL blocked by default for safety in NL-to-SQL workflows.
ALLOW_DDL = _as_bool("ALLOW_DDL", False)
ALLOW_MULTI_STATEMENTS = _as_bool("ALLOW_MULTI_STATEMENTS", False)
# If enabled, simple table-read intents may use SELECT * for full-row retrieval requests.
ALLOW_SELECT_STAR_SIMPLE_READS = _as_bool("ALLOW_SELECT_STAR_SIMPLE_READS", True)