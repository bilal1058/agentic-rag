"""Central runtime configuration, environment validation, rate limiting, and observability telemetry."""

import json
import logging
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("rag_app")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)

os.environ.setdefault("USER_AGENT", "rag-chatbot/1.0")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

def sync_streamlit_secrets() -> None:
    """Sync Streamlit Cloud secrets into os.environ if present."""
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            for key, val in st.secrets.items():
                if isinstance(val, str) and (key not in os.environ or not os.environ[key]):
                    os.environ[key] = val
    except Exception:
        pass

sync_streamlit_secrets()

DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"
DEFAULT_OPENROUTER_MODEL = "inclusionai/ling-3.0-flash-vl:free"
DEFAULT_MAX_REQUESTS_PER_MINUTE = 8
DEFAULT_MAX_TOKENS = 700


def _get_int_env(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _get_bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name, str(default)).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def get_runtime_config() -> dict[str, Any]:
    """Return runtime configuration with safe defaults and env overrides."""
    groq_model = (os.environ.get("GROQ_MODEL") or "").strip() or DEFAULT_GROQ_MODEL
    openrouter_model = (os.environ.get("OPENROUTER_MODEL") or "").strip() or DEFAULT_OPENROUTER_MODEL
    app_env = (os.environ.get("APP_ENV") or "development").strip().lower() or "development"

    return {
        "app_env": app_env,
        "llm_provider": "groq",
        "groq_model": groq_model,
        "openrouter_model": openrouter_model,
        "max_tokens": _get_int_env("MAX_TOKENS", DEFAULT_MAX_TOKENS),
        "max_requests_per_minute": _get_int_env(
            "MAX_REQUESTS_PER_MINUTE",
            DEFAULT_MAX_REQUESTS_PER_MINUTE,
        ),
        "enable_ragas": _get_bool_env("ENABLE_RAGAS", True),
        "enable_guardrails": _get_bool_env("ENABLE_GUARDRAILS", True),
        "supabase_url": (os.environ.get("SUPABASE_URL") or "").strip(),
        "supabase_key": (os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_ANON_KEY") or "").strip(),
    }


# ---------------------------------------------------------------------------
# Request Governance & Rate Limiting (Delegated to core.governance)
# ---------------------------------------------------------------------------
from core.governance import (
    validate_runtime_environment,
    startup_health_check,
    check_rate_limit,
    rate_limit_remaining,
    reset_rate_limit,
    RedisRateLimiter,
)



# ---------------------------------------------------------------------------
# Observability & Structured Telemetry
# ---------------------------------------------------------------------------

def log_request(
    user_id: str | None,
    endpoint: str,
    latency_ms: float,
    status: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    payload = {
        "user_id": user_id,
        "endpoint": endpoint,
        "latency_ms": round(latency_ms, 2),
        "status": status,
        "metadata": metadata or {},
    }
    logger.info(json.dumps(payload, ensure_ascii=False))


def measure_latency(endpoint: str):
    """Decorator to measure and log execution latency for async functions."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                latency_ms = (time.perf_counter() - start) * 1000
                log_request(None, endpoint, latency_ms, "success")
                return result
            except Exception as exc:
                latency_ms = (time.perf_counter() - start) * 1000
                log_request(None, endpoint, latency_ms, "error", {"error": str(exc)})
                raise

        return wrapper

    return decorator
