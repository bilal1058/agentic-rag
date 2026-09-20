"""Assistant Pipeline Orchestrator.

Deep execution module encapsulating asynchronous file indexing, URL scraping,
and multi-hop LangGraph agent execution behind a synchronous interface with
observer progress callbacks.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("pipeline")


class AssistantPipeline:
    """Encapsulates execution of RAG ingestion and reasoning pipelines."""

    @staticmethod
    def ensure_vector_store(session_dir: Path | str, current_store=None):
        """Load the Qdrant vector store for a session if it exists on disk and not already in memory."""
        if current_store is not None:
            return current_store

        db_dir = Path(session_dir) / "qdrant_db" if not str(session_dir).endswith("qdrant_db") else Path(session_dir)
        if db_dir.exists():
            try:
                from core.rag import get_qdrant_vector_store
                return get_qdrant_vector_store(str(db_dir))
            except Exception as exc:
                logger.warning("Failed to load existing vector store at %s: %s", db_dir, exc)
        return None

    @staticmethod
    def ingest_files(
        files: list,
        session_dir: Path | str,
        existing_store=None,
        on_progress: Callable[[float, str], None] | None = None,
    ) -> tuple[Any, int]:
        """Ingest uploaded documents synchronously, updating status via progress callback."""
        from core.rag import process_uploaded_files

        db_path = str(Path(session_dir) / "qdrant_db" if not str(session_dir).endswith("qdrant_db") else session_dir)
        return asyncio.run(
            process_uploaded_files(
                files,
                existing_store=existing_store,
                persist_directory=db_path,
                progress_callback=on_progress,
            )
        )

    @staticmethod
    def ingest_url(
        url: str,
        session_dir: Path | str,
        existing_store=None,
        on_progress: Callable[[float, str], None] | None = None,
    ) -> tuple[Any, int]:
        """Fetch and index a web page synchronously, updating status via progress callback."""
        from core.rag import process_url

        db_path = str(Path(session_dir) / "qdrant_db" if not str(session_dir).endswith("qdrant_db") else session_dir)
        return asyncio.run(
            process_url(
                url,
                existing_store,
                persist_directory=db_path,
                progress_callback=on_progress,
            )
        )

    @staticmethod
    def query(
        prompt: str,
        messages: list[dict],
        vector_store,
        file_names: list[str],
        urls: list[str],
        session_dir: Path | str,
        on_step: Callable[[int, str], None] | None = None,
    ) -> tuple[str, dict]:
        """Execute the LangGraph multi-hop agent pipeline synchronously with step observers."""
        from core.rag import run_agent_pipeline

        history = [
            {
                "role": m["role"],
                "content": m["content"],
                "files": m.get("files", []),
            }
            for m in messages[:-1]
            if m.get("role") in {"user", "assistant"}
        ]
        history.append({
            "role": "user",
            "content": prompt,
            "files": messages[-1].get("files", []) if messages else [],
        })

        db_path = str(Path(session_dir))
        return asyncio.run(
            run_agent_pipeline(
                vector_store,
                history,
                file_names,
                urls,
                session_dir=db_path,
                on_step=on_step,
            )
        )
