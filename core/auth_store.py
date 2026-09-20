"""Deep AuthStore Module with Dual Adapters for Local SQLite and Cloud Supabase.

Ports & Adapters pattern isolating SQL schemas, password hashing salts, and
Supabase HTTP REST interactions behind an abstract protocol seam.
"""

import base64
import hashlib
import json
import logging
import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional, Protocol

import httpx

from core.config import get_runtime_config

logger = logging.getLogger("auth_store")

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "app.db"


class AuthPersistenceAdapter(Protocol):
    """Abstract protocol seam defining authentication storage operations."""

    def sign_up(self, email: str, password: str, full_name: str = "") -> dict[str, Any]:
        ...

    def sign_in(self, email: str, password: str) -> dict[str, Any]:
        ...

    def get_user(self, token: str) -> dict[str, Any] | None:
        ...

    def update_user(self, identifier: Any, full_name: str, token: str = "") -> bool:
        ...

    def sign_out(self, token: str) -> None:
        ...


class SQLiteAuthAdapter:
    """Local SQLite adapter managing users, password salts, and session tokens."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Initialize user and user_tokens tables and run schema migrations."""
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT,
                    full_name TEXT,
                    password_hash TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            columns = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
            if "email" not in columns:
                try:
                    conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
                except Exception:
                    pass
            if "full_name" not in columns:
                try:
                    conn.execute("ALTER TABLE users ADD COLUMN full_name TEXT")
                except Exception:
                    pass

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token TEXT UNIQUE NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """
            )
            conn.commit()

    @staticmethod
    def hash_password(password: str, salt: str) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100_000,
        ).hex()

    @staticmethod
    def generate_salt() -> str:
        return secrets.token_hex(16)

    def sign_up(self, email: str, password: str, full_name: str = "") -> dict[str, Any]:
        salt = self.generate_salt()
        pwd_hash = self.hash_password(password, salt)
        display_name = (full_name or "").strip() or email.split("@")[0].capitalize()
        with self._connect() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO users (username, email, full_name, password_hash, password_salt) VALUES (?, ?, ?, ?, ?)",
                    (email, email, display_name, pwd_hash, salt),
                )
                user_id = cursor.lastrowid
                conn.commit()
            except sqlite3.IntegrityError:
                raise ValueError("An account with this email already exists.")

        token = self.issue_token(user_id)
        return {
            "id": str(user_id),
            "email": email,
            "name": display_name,
            "token": token,
            "provider": "local",
        }

    def sign_in(self, email: str, password: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ? OR email = ?",
                (email, email),
            ).fetchone()

        if row is None or self.hash_password(password, row["password_salt"]) != row["password_hash"]:
            raise ValueError("Invalid email or password.")

        token = self.issue_token(row["id"])
        row_dict = dict(row)
        display_name = row_dict.get("full_name") or (row["email"] or row["username"]).split("@")[0].capitalize()
        return {
            "id": str(row["id"]),
            "email": row["email"] or row["username"],
            "name": display_name,
            "token": token,
            "provider": "local",
        }

    def issue_token(self, user_id: int, expiry_seconds: int = 86400) -> str:
        token = secrets.token_urlsafe(32)
        expires_at = str(int((time.time() + expiry_seconds) * 1000))
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO user_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
                (user_id, token, expires_at),
            )
            conn.commit()
        return token

    def get_user(self, token: str) -> dict[str, Any] | None:
        if not token:
            return None
        now_ms = str(int(time.time() * 1000))
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT u.id, u.username, u.email, u.full_name
                FROM users u
                JOIN user_tokens t ON u.id = t.user_id
                WHERE t.token = ? AND CAST(t.expires_at AS INTEGER) > CAST(? AS INTEGER)
                """,
                (token, now_ms),
            ).fetchone()
        if row is None:
            return None
        name = row["full_name"] or (row["email"] or row["username"]).split("@")[0].capitalize()
        return {
            "id": str(row["id"]),
            "username": row["username"],
            "email": row["email"] or row["username"],
            "name": name,
            "token": token,
            "provider": "local",
        }

    def update_user(self, identifier: Any, full_name: str, token: str = "") -> bool:
        uid = str(identifier)
        try:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE users SET full_name = ? WHERE id = ? OR username = ? OR email = ?",
                    (full_name, uid, uid, uid),
                )
                conn.commit()
            return True
        except Exception as exc:
            logger.warning("Failed to update local user name: %s", exc)
            return False

    def sign_out(self, token: str) -> None:
        if not token:
            return
        with self._connect() as conn:
            conn.execute("DELETE FROM user_tokens WHERE token = ?", (token,))
            conn.commit()


class SupabaseAuthAdapter:
    """Cloud adapter communicating with Supabase GoTrue Auth REST endpoints."""

    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.key = key
        self.headers = {
            "apikey": self.key,
            "Content-Type": "application/json",
        }

    def sign_up(self, email: str, password: str, full_name: str = "") -> dict[str, Any]:
        endpoint = f"{self.url}/auth/v1/signup"
        payload = {"email": email, "password": password}
        if full_name:
            payload["data"] = {"full_name": full_name, "name": full_name}

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(endpoint, headers=self.headers, json=payload)
                data = resp.json()
                if resp.status_code >= 400:
                    err_msg = data.get("msg") or data.get("error_description") or data.get("message") or "Sign up failed"
                    raise ValueError(err_msg)

                user = data.get("user") or {}
                token = data.get("access_token") or ""
                meta = user.get("user_metadata") or {}
                display_name = meta.get("full_name") or meta.get("name") or full_name or email.split("@")[0].capitalize()
                return {
                    "id": user.get("id", str(secrets.token_hex(8))),
                    "email": user.get("email", email),
                    "name": display_name,
                    "token": token,
                    "provider": "supabase",
                }
        except httpx.RequestError as exc:
            logger.error("Supabase sign_up network error: %s", exc)
            raise ValueError(f"Could not connect to Supabase: {exc}")

    def sign_in(self, email: str, password: str) -> dict[str, Any]:
        endpoint = f"{self.url}/auth/v1/token?grant_type=password"
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    endpoint,
                    headers=self.headers,
                    json={"email": email, "password": password},
                )
                data = resp.json()
                if resp.status_code >= 400:
                    err_msg = data.get("msg") or data.get("error_description") or data.get("error") or "Invalid login credentials"
                    raise ValueError(err_msg)

                user = data.get("user") or {}
                meta = user.get("user_metadata") or {}
                display_name = meta.get("full_name") or meta.get("name") or email.split("@")[0].capitalize()
                return {
                    "id": user.get("id", str(secrets.token_hex(8))),
                    "email": user.get("email", email),
                    "name": display_name,
                    "token": data.get("access_token", ""),
                    "provider": "supabase",
                }
        except httpx.RequestError as exc:
            logger.error("Supabase sign_in network error: %s", exc)
            raise ValueError(f"Could not connect to Supabase: {exc}")

    def update_user(self, identifier: Any, full_name: str, token: str = "") -> bool:
        if not token:
            return False
        endpoint = f"{self.url}/auth/v1/user"
        headers = dict(self.headers)
        headers["Authorization"] = f"Bearer {token}"
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.put(endpoint, headers=headers, json={"data": {"full_name": full_name, "name": full_name}})
                return resp.status_code < 400
        except Exception as exc:
            logger.warning("Supabase update_user error: %s", exc)
            return False

    def get_user(self, token: str) -> dict[str, Any] | None:
        if not token:
            return None

        # 1. Fast local JWT claim extraction (0ms latency)
        try:
            parts = token.split(".")
            if len(parts) == 3:
                payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
                claims = json.loads(base64.urlsafe_b64decode(payload_b64.encode("utf-8")))
                exp = claims.get("exp")
                if exp and exp < time.time():
                    return None
                user_id = claims.get("sub")
                email = claims.get("email", "")
                meta = claims.get("user_metadata") or {}
                display_name = meta.get("full_name") or meta.get("name") or (email.split("@")[0].capitalize() if email else "User")
                avatar_url = meta.get("avatar_url") or meta.get("picture") or ""
                if user_id and email:
                    return {
                        "id": user_id,
                        "username": email,
                        "email": email,
                        "name": display_name,
                        "avatar_url": avatar_url,
                        "token": token,
                        "provider": "supabase",
                    }
        except Exception:
            pass

        # 2. Fallback to Supabase /auth/v1/user endpoint
        endpoint = f"{self.url}/auth/v1/user"
        headers = dict(self.headers)
        headers["Authorization"] = f"Bearer {token}"
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(endpoint, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    meta = data.get("user_metadata") or {}
                    display_name = meta.get("full_name") or meta.get("name") or (data.get("email") or "").split("@")[0].capitalize()
                    return {
                        "id": data.get("id"),
                        "username": data.get("email"),
                        "email": data.get("email"),
                        "name": display_name,
                        "avatar_url": meta.get("avatar_url") or "",
                        "token": token,
                        "provider": "supabase",
                    }
        except Exception as exc:
            logger.warning("Supabase get_user error: %s", exc)
        return None

    def get_oauth_url(self, provider: str = "google", redirect_to: str = "") -> str:
        query = f"provider={provider}"
        if redirect_to:
            import urllib.parse
            query += f"&redirect_to={urllib.parse.quote(redirect_to, safe='')}"
        return f"{self.url}/auth/v1/authorize?{query}"

    def sign_out(self, token: str) -> None:
        if not token:
            return
        endpoint = f"{self.url}/auth/v1/logout"
        headers = dict(self.headers)
        headers["Authorization"] = f"Bearer {token}"
        try:
            with httpx.Client(timeout=5.0) as client:
                client.post(endpoint, headers=headers)
        except Exception as exc:
            logger.warning("Supabase sign_out error: %s", exc)


class AuthStore:
    """Deep facade routing identity operations to SQLite or Supabase."""

    _sqlite_adapter: Optional[SQLiteAuthAdapter] = None

    @classmethod
    def get_sqlite_adapter(cls) -> SQLiteAuthAdapter:
        if cls._sqlite_adapter is None:
            cls._sqlite_adapter = SQLiteAuthAdapter()
        return cls._sqlite_adapter

    @classmethod
    def get_supabase_adapter(cls) -> Optional[SupabaseAuthAdapter]:
        config = get_runtime_config()
        if config["supabase_url"] and config["supabase_key"]:
            return SupabaseAuthAdapter(config["supabase_url"], config["supabase_key"])
        return None

    @classmethod
    def is_supabase_active(cls) -> bool:
        return cls.get_supabase_adapter() is not None

    @classmethod
    def get_active_adapter(cls) -> AuthPersistenceAdapter:
        supabase = cls.get_supabase_adapter()
        if supabase is not None:
            return supabase
        return cls.get_sqlite_adapter()


# Convenience re-exports
get_auth_store = AuthStore
