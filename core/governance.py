"""Request governance, rate limiting, and runtime health check enforcement.

Encapsulates stateful client throttling, sliding-window request tracking,
and startup environment safety verification.
"""

import logging
import os
import time
from collections import defaultdict
from typing import Any

from core.config import get_runtime_config

logger = logging.getLogger("governance")


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------

class SlidingWindowRateLimiter:
    """Encapsulates sliding-window request rate limiting for sessions and users."""

    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        self._history: dict[str, list[float]] = defaultdict(list)

    def _get_max_requests(self) -> int:
        config = get_runtime_config()
        return max(int(config.get("max_requests_per_minute", 8)), 1)

    def _prune(self, key: str, now: float) -> None:
        cutoff = now - self.window_seconds
        self._history[key] = [t for t in self._history[key] if t > cutoff]

    def check(self, key: str) -> tuple[bool, float]:
        """Check request limit for key. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        self._prune(key, now)
        timestamps = self._history[key]
        max_requests = self._get_max_requests()

        if len(timestamps) >= max_requests:
            retry_after = self.window_seconds - (now - timestamps[0])
            return False, max(retry_after, 1.0)

        timestamps.append(now)
        return True, 0.0

    def remaining(self, key: str) -> int:
        """Return remaining allowed prompts in current window."""
        self._prune(key, time.monotonic())
        max_requests = self._get_max_requests()
        return max(0, max_requests - len(self._history[key]))

    def reset(self, key: str) -> None:
        """Clear rate limit history for key."""
        self._history.pop(key, None)


_global_limiter = SlidingWindowRateLimiter()


def check_rate_limit(session_id: str) -> tuple[bool, float]:
    """Check request limit for session. Returns (allowed, retry_after_seconds)."""
    return _global_limiter.check(session_id)


def rate_limit_remaining(session_id: str) -> int:
    """Return remaining allowed prompts in the current window."""
    return _global_limiter.remaining(session_id)


def reset_rate_limit(session_id: str) -> None:
    """Clear rate limit history for a session."""
    _global_limiter.reset(session_id)


class RedisRateLimiter:
    """In-memory placeholder for Redis-backed rate limiting."""

    def __init__(self, window_seconds: int = 60, max_requests: int = 8):
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self._history: dict[str, list[float]] = defaultdict(list)

    def check(self, user_key: str) -> tuple[bool, float]:
        now = time.monotonic()
        window_start = now - self.window_seconds
        self._history[user_key] = [ts for ts in self._history.get(user_key, []) if ts > window_start]

        if len(self._history[user_key]) >= self.max_requests:
            retry_after = self.window_seconds - (now - self._history[user_key][0])
            return False, max(retry_after, 1.0)

        self._history[user_key].append(now)
        return True, 0.0


# ---------------------------------------------------------------------------
# Health Checking & Safety Verification
# ---------------------------------------------------------------------------

def validate_runtime_environment() -> list[str]:
    """Return a list of missing production safety warnings."""
    config = get_runtime_config()
    warnings: list[str] = []

    if config["app_env"] == "production":
        if not os.environ.get("GROQ_API_KEY"):
            warnings.append("Production requires GROQ_API_KEY to be set.")
        if not os.environ.get("OPENROUTER_API_KEY"):
            warnings.append("Production should configure OPENROUTER_API_KEY as a fallback provider.")
        if not os.environ.get("APP_SECRET_KEY"):
            warnings.append("Production requires APP_SECRET_KEY to sign session state.")

    if config["max_requests_per_minute"] <= 0:
        warnings.append("MAX_REQUESTS_PER_MINUTE must be greater than zero.")

    if not config["enable_guardrails"]:
        warnings.append("Guardrails are disabled; this is unsafe for untrusted user input.")

    return warnings


def startup_health_check() -> list[str]:
    """Run runtime checks at app startup and log/return warnings."""
    config = get_runtime_config()
    warnings = validate_runtime_environment()

    if config["app_env"] == "production":
        logger.warning("Production runtime config loaded: %s", config)

    if warnings:
        logger.warning("Runtime warnings: %s", warnings)
    else:
        logger.info("Runtime config passed startup checks.")

    return warnings
