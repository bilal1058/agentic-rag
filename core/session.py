"""Session persistence and conversation management.

Provides a deep SessionStore module with dual adapters:
- LocalDiskAdapter: local filesystem JSON storage in sessions/<session_id>/
- SupabaseSessionAdapter: cloud synchronization via Supabase REST
"""

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger("session")

ROOT = Path(__file__).resolve().parent.parent
SESSIONS_DIR = ROOT / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)


class SessionAdapter(Protocol):
    """Protocol for session storage adapters."""

    def load(self, session_id: str) -> dict[str, Any]:
        ...

    def save(self, session_id: str, data: dict[str, Any]) -> bool:
        ...

    def delete(self, session_id: str) -> None:
        ...

    def list_conversations(self, user_id: str | None = None) -> list[dict[str, Any]]:
        ...


class LocalDiskAdapter:
    """Local filesystem adapter managing session folders and metadata.json files."""

    def __init__(self, base_dir: Path = SESSIONS_DIR):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def session_path(self, session_id: str) -> Path:
        """Return the directory for a session, creating it if needed."""
        path = self.base_dir / session_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def metadata_path(self, session_id: str) -> Path:
        """Return the path to a session's metadata.json."""
        return self.session_path(session_id) / "metadata.json"

    def load(self, session_id: str) -> dict[str, Any]:
        path = self.metadata_path(session_id)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        return {}

    def save(self, session_id: str, data: dict[str, Any]) -> bool:
        try:
            self.metadata_path(session_id).write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8"
            )
            return True
        except OSError as exc:
            logger.warning("Failed to save local session %s: %s", session_id, exc)
            return False

    def delete(self, session_id: str) -> None:
        session_dir = self.base_dir / session_id
        if session_dir.exists():
            try:
                shutil.rmtree(session_dir)
            except Exception as exc:
                logger.warning("Failed to delete local session dir %s: %s", session_id, exc)

    def list_conversations(self, user_id: str | None = None) -> list[dict[str, Any]]:
        conversations = []
        for file in self.base_dir.glob("*/metadata.json"):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                if user_id and data.get("user_id") and data.get("user_id") != user_id:
                    continue
                messages = data.get("messages", [])
                first_user = next(
                    (m.get("content", "") for m in messages if isinstance(m, dict) and m.get("role") == "user"),
                    "",
                ).strip()
                if not first_user:
                    continue
                last = messages[-1].get("content", "") if messages else ""
                updated = data.get("updated_at") or datetime.fromtimestamp(
                    file.stat().st_mtime
                ).isoformat()
                sid = file.parent.name
                conversations.append({
                    "id": sid,
                    "title": first_user[:30] + ("…" if len(first_user) > 30 else ""),
                    "preview": last[:55] + ("…" if len(last) > 55 else ""),
                    "updated": updated,
                })
            except (OSError, json.JSONDecodeError, ValueError):
                continue
        return conversations


class SupabaseSessionAdapter:
    """Supabase REST adapter for syncing conversations to the cloud PostgreSQL database."""

    def _get_headers(self) -> tuple[str, dict] | None:
        url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
        key = os.environ.get("SUPABASE_KEY", "").strip()
        if not url or not key:
            return None
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        return url, headers

    def is_available(self) -> bool:
        return self._get_headers() is not None

    def load(self, session_id: str) -> dict[str, Any]:
        config = self._get_headers()
        if not config:
            return {}
        url, headers = config
        try:
            import httpx
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(f"{url}/rest/v1/conversations?session_id=eq.{session_id}", headers=headers)
                if resp.status_code == 200:
                    items = resp.json()
                    if items and isinstance(items, list):
                        row = items[0]
                        return {
                            "user_id": row.get("user_id"),
                            "messages": row.get("messages", []),
                            "uploaded_file_names": row.get("files", []),
                            "ingested_urls": [],
                            "chunk_count": len(row.get("files", [])),
                            "updated_at": row.get("updated_at"),
                        }
        except Exception as exc:
            logger.debug("Supabase load session skipped: %s", exc)
        return {}

    def save(self, session_id: str, data: dict[str, Any]) -> bool:
        config = self._get_headers()
        if not config:
            return False
        url, headers = config

        user_id = data.get("user_id")
        if not user_id or len(str(user_id)) < 30:
            return False

        messages = data.get("messages", [])
        first_user = next(
            (m.get("content", "") for m in messages if isinstance(m, dict) and m.get("role") == "user"),
            "New Chat",
        ).strip()
        title = first_user[:40] + ("…" if len(first_user) > 40 else "")

        payload = {
            "session_id": session_id,
            "user_id": user_id,
            "title": title or "New Chat",
            "messages": messages,
            "files": data.get("uploaded_file_names", []),
            "updated_at": data.get("updated_at") or datetime.now().isoformat(),
        }

        try:
            import httpx
            post_headers = dict(headers)
            post_headers["Prefer"] = "resolution=merge-duplicates"
            with httpx.Client(timeout=3.0) as client:
                resp = client.post(f"{url}/rest/v1/conversations", json=payload, headers=post_headers)
                return resp.status_code in (200, 201, 204)
        except Exception as exc:
            logger.debug("Supabase session sync skipped: %s", exc)
            return False

    def delete(self, session_id: str) -> None:
        config = self._get_headers()
        if not config:
            return
        url, headers = config
        try:
            import httpx
            with httpx.Client(timeout=3.0) as client:
                client.delete(f"{url}/rest/v1/conversations?session_id=eq.{session_id}", headers=headers)
        except Exception:
            pass

    def list_conversations(self, user_id: str | None = None) -> list[dict[str, Any]]:
        if not user_id or len(str(user_id)) < 30:
            return []
        config = self._get_headers()
        if not config:
            return []
        url, headers = config
        try:
            import httpx
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(
                    f"{url}/rest/v1/conversations?user_id=eq.{user_id}&order=updated_at.desc&limit=25",
                    headers=headers,
                )
                if resp.status_code == 200:
                    rows = resp.json()
                    results = []
                    for row in rows:
                        messages = row.get("messages", [])
                        last = messages[-1].get("content", "") if messages else ""
                        results.append({
                            "id": row.get("session_id"),
                            "title": row.get("title", "New Chat"),
                            "preview": last[:55] + ("…" if len(last) > 55 else ""),
                            "updated": row.get("updated_at") or "",
                        })
                    return results
        except Exception as exc:
            logger.debug("Supabase list conversations skipped: %s", exc)
        return []


class SessionStore:
    """Deep module managing conversation sessions across local disk and cloud database."""

    def __init__(
        self,
        local_adapter: LocalDiskAdapter | None = None,
        remote_adapter: SupabaseSessionAdapter | None = None,
    ):
        self.local = local_adapter or LocalDiskAdapter()
        self.remote = remote_adapter or SupabaseSessionAdapter()

    def path(self, session_id: str) -> Path:
        return self.local.session_path(session_id)

    def metadata_path(self, session_id: str) -> Path:
        return self.local.metadata_path(session_id)

    def load(self, session_id: str) -> dict[str, Any]:
        """Read session data from local disk, falling back to Supabase cloud if missing."""
        data = self.local.load(session_id)
        if data:
            return data

        if self.remote.is_available():
            cloud_data = self.remote.load(session_id)
            if cloud_data:
                self.local.save(session_id, cloud_data)
                return cloud_data
        return {}

    def save(
        self,
        session_id: str,
        messages: list,
        uploaded_file_names: list,
        ingested_urls: list,
        chunk_count: int,
        user_id: str | None = None,
    ) -> None:
        """Persist session data locally and synchronize to Supabase cloud."""
        data = {
            "user_id": user_id,
            "messages": messages,
            "uploaded_file_names": uploaded_file_names,
            "ingested_urls": ingested_urls,
            "chunk_count": chunk_count,
            "updated_at": datetime.now().isoformat(),
        }
        self.local.save(session_id, data)
        if self.remote.is_available():
            self.remote.save(session_id, data)

    def delete(self, session_id: str) -> None:
        """Delete session locally and from cloud."""
        self.local.delete(session_id)
        if self.remote.is_available():
            self.remote.delete(session_id)

    def list_history(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """Return merged and deduplicated conversation history sorted by update time."""
        conversations_map: dict[str, dict[str, Any]] = {}

        for item in self.local.list_conversations(user_id=user_id):
            conversations_map[item["id"]] = item

        if user_id and self.remote.is_available():
            cloud_convs = self.remote.list_conversations(user_id=user_id)
            for c in cloud_convs:
                cid = c.get("id")
                if cid and cid not in conversations_map:
                    conversations_map[cid] = c

        return sorted(conversations_map.values(), key=lambda item: item["updated"], reverse=True)


_global_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    global _global_store
    if _global_store is None:
        _global_store = SessionStore()
    return _global_store


# ---------------------------------------------------------------------------
# High-level convenience functions
# ---------------------------------------------------------------------------

def session_path(session_id: str) -> Path:
    return get_session_store().path(session_id)


def session_metadata_path(session_id: str) -> Path:
    return get_session_store().metadata_path(session_id)


def load_session(session_id: str) -> dict[str, Any]:
    return get_session_store().load(session_id)


def save_session(
    session_id: str,
    messages: list,
    uploaded_file_names: list,
    ingested_urls: list,
    chunk_count: int,
    user_id: str | None = None,
) -> None:
    get_session_store().save(
        session_id, messages, uploaded_file_names, ingested_urls, chunk_count, user_id=user_id
    )


def delete_session(session_id: str) -> None:
    get_session_store().delete(session_id)


def conversation_history(user_id: str | None = None) -> list[dict[str, Any]]:
    return get_session_store().list_history(user_id=user_id)
