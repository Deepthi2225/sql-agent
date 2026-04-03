"""
LLM Client — supports multiple providers via a single chat() interface.
Switch providers by changing LLM_PROVIDER in your .env file:
  - "ollama"  → local, free, requires Ollama running
  - "groq"    → cloud, free tier, get key at console.groq.com
  - "openai"  → cloud, paid, requires OpenAI key
"""
import requests
from config import (
    LLM_PROVIDER,
    OLLAMA_BASE_URL, OLLAMA_MODEL,
    GROQ_API_KEY, GROQ_MODEL,
    OPENAI_API_KEY, OPENAI_MODEL,
)


def chat(system_prompt: str, user_message: str, temperature: float = 0.1) -> str:
    """
    Unified chat interface. Routes to the configured LLM provider.
    All providers return a plain string response.
    """
    if LLM_PROVIDER == "ollama":
        return _chat_ollama(system_prompt, user_message, temperature)
    elif LLM_PROVIDER == "groq":
        return _chat_groq(system_prompt, user_message, temperature)
    elif LLM_PROVIDER == "openai":
        return _chat_openai(system_prompt, user_message, temperature)
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{LLM_PROVIDER}'. "
            "Choose 'ollama', 'groq', or 'openai' in your .env"
        )


def is_llm_available() -> bool:
    """Check if the configured LLM provider is reachable."""
    if LLM_PROVIDER == "ollama":
        return _check_ollama()
    elif LLM_PROVIDER == "groq":
        return bool(GROQ_API_KEY and not GROQ_API_KEY.startswith("your_"))
    elif LLM_PROVIDER == "openai":
        return bool(OPENAI_API_KEY and not OPENAI_API_KEY.startswith("your_"))
    return False


def get_provider_label() -> str:
    """Human-readable label for the current provider."""
    labels = {
        "ollama": f"Ollama ({OLLAMA_MODEL}) — local",
        "groq":   f"Groq ({GROQ_MODEL}) — free cloud",
        "openai": f"OpenAI ({OPENAI_MODEL}) — paid cloud",
    }
    return labels.get(LLM_PROVIDER, LLM_PROVIDER)


# ── Provider implementations ──────────────────────────────────────────────────

def _chat_ollama(system_prompt: str, user_message: str, temperature: float) -> str:
    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        "stream": False,
        "options": {"temperature": temperature},
    }
    try:
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Cannot reach Ollama. Run `ollama serve` in a terminal first."
        )
    except requests.exceptions.Timeout:
        raise RuntimeError("Ollama timed out — model may still be loading, try again.")
    except Exception as e:
        raise RuntimeError(f"Ollama error: {e}")


def _chat_groq(system_prompt: str, user_message: str, temperature: float) -> str:
    if not GROQ_API_KEY or GROQ_API_KEY.startswith("your_"):
        raise RuntimeError(
            "GROQ_API_KEY not set. Get a free key at https://console.groq.com"
        )
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        "temperature": temperature,
        "max_tokens": 1024,
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"Groq API error: {e.response.status_code} — {e.response.text}")
    except Exception as e:
        raise RuntimeError(f"Groq error: {e}")


def _chat_openai(system_prompt: str, user_message: str, temperature: float) -> str:
    if not OPENAI_API_KEY or OPENAI_API_KEY.startswith("your_"):
        raise RuntimeError("OPENAI_API_KEY not set in your .env file.")
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        "temperature": temperature,
        "max_tokens": 1024,
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"OpenAI API error: {e.response.status_code} — {e.response.text}")
    except Exception as e:
        raise RuntimeError(f"OpenAI error: {e}")


def _check_ollama() -> bool:
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


# Keep backward-compat alias used in app.py
def is_ollama_running() -> bool:
    return is_llm_available()