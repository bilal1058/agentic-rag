"""Unified FastAPI backend service with REST chat endpoints, authentication, and background worker."""

import asyncio
import logging
from typing import Any

from core.auth import login_user, signup_user, validate_token
from core.config import get_runtime_config

logger = logging.getLogger("api")

try:
    from fastapi import FastAPI, Header, HTTPException, status
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(title="Agentic RAG API", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    import time
    _START_TIME = time.time()

    @app.get("/health")
    async def health_check() -> dict[str, Any]:
        config = get_runtime_config()
        return {
            "status": "ok",
            "uptime_seconds": round(time.time() - _START_TIME, 1),
            "runtime": config["app_env"],
            "model": config["groq_model"],
            "supabase_configured": bool(config["supabase_url"] and config["supabase_key"]),
        }

    @app.get("/ping")
    @app.head("/ping")
    async def ping() -> dict[str, str]:
        """Lightweight endpoint for free-tier keep-alive pingers (UptimeRobot, cron-job.org)."""
        return {"status": "pong", "service": "agentic-rag"}

    @app.post("/api/auth/signup")
    async def signup_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        email = (payload or {}).get("email", "")
        password = (payload or {}).get("password", "")
        try:
            user = signup_user(email, password)
            return {"status": "success", "user": user}
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    @app.post("/api/auth/login")
    async def login_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        email = (payload or {}).get("email", "")
        password = (payload or {}).get("password", "")
        try:
            user = login_user(email, password)
            return {"status": "success", "user": user}
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    @app.post("/api/chat")
    async def chat_endpoint(
        payload: dict[str, Any], authorization: str | None = Header(default=None)
    ) -> dict[str, Any]:
        token = None
        if authorization:
            token = authorization.replace("Bearer ", "", 1).strip()

        user = validate_token(token) if token else None
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )

        message = (payload or {}).get("message", "")
        if not message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Message is required"
            )

        return {
            "answer": f"Hello {user['username']}, response for: {message}",
            "user": user["username"],
            "model": get_runtime_config()["groq_model"],
        }

except ImportError:
    app = None


# ---------------------------------------------------------------------------
# Background Worker Routines
# ---------------------------------------------------------------------------

def queue_background_task(task_name: str, payload: dict[str, Any]) -> None:
    logger.info("Queued task=%s payload=%s", task_name, payload)


async def process_background_queue() -> None:
    logger.info("Background worker starting...")
    while True:
        await asyncio.sleep(5)
        logger.debug("Background worker tick")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(process_background_queue())
    except KeyboardInterrupt:
        logger.info("Background worker stopped.")
