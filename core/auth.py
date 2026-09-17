"""Unified Authentication Service with Supabase Cloud Auth and Local SQLite fallback."""

import hashlib
import json
import logging
import os
import re
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any

import httpx

from core.config import get_runtime_config

logger = logging.getLogger("auth")

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "app.db"


# ---------------------------------------------------------------------------
# Local SQLite Storage (Fallback)
# ---------------------------------------------------------------------------

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
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


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()


def _generate_salt() -> str:
    return secrets.token_hex(16)


# ---------------------------------------------------------------------------
# Supabase Cloud Client
# ---------------------------------------------------------------------------

def is_supabase_configured() -> bool:
    config = get_runtime_config()
    return bool(config["supabase_url"] and config["supabase_key"])


class SupabaseAuth:
    """Lightweight, reliable HTTP client for Supabase Auth API."""

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

    def update_user(self, token: str, full_name: str) -> bool:
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
        endpoint = f"{self.url}/auth/v1/user"
        headers = dict(self.headers)
        headers["Authorization"] = f"Bearer {token}"
        try:
            with httpx.Client(timeout=6.0) as client:
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


def _get_supabase_client() -> SupabaseAuth | None:
    config = get_runtime_config()
    if config["supabase_url"] and config["supabase_key"]:
        return SupabaseAuth(config["supabase_url"], config["supabase_key"])
    return None


# ---------------------------------------------------------------------------
# Password Strength & Security Evaluation
# ---------------------------------------------------------------------------

def evaluate_password_strength(password: str) -> dict[str, Any]:
    """Evaluate password strength across length, upper, lower, digit, special characters."""
    pwd = password or ""
    has_length = len(pwd) >= 8
    has_upper = bool(re.search(r"[A-Z]", pwd))
    has_lower = bool(re.search(r"[a-z]", pwd))
    has_digit = bool(re.search(r"\d", pwd))
    has_special = bool(re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?`~]", pwd))

    criteria = {
        "length": has_length,
        "uppercase": has_upper,
        "lowercase": has_lower,
        "digit": has_digit,
        "special": has_special,
    }

    score = sum(criteria.values())
    if len(pwd) == 0:
        return {
            "score": 0,
            "percent": 0,
            "label": "Enter a password",
            "color": "#71717a",
            "criteria": criteria,
            "is_valid": False,
        }
    elif score <= 2:
        return {
            "score": score,
            "percent": 30,
            "label": "Weak",
            "color": "#ef4444",
            "criteria": criteria,
            "is_valid": False,
        }
    elif score == 3:
        return {
            "score": score,
            "percent": 60,
            "label": "Fair",
            "color": "#f59e0b",
            "criteria": criteria,
            "is_valid": False,
        }
    elif score == 4:
        return {
            "score": score,
            "percent": 85,
            "label": "Strong",
            "color": "#10b981",
            "criteria": criteria,
            "is_valid": True,
        }
    else:
        return {
            "score": 5,
            "percent": 100,
            "label": "Excellent",
            "color": "#059669",
            "criteria": criteria,
            "is_valid": True,
        }


# ---------------------------------------------------------------------------
# High-Level Authentication Functions
# ---------------------------------------------------------------------------

def signup_user(
    email: str,
    password: str,
    full_name: str = "",
    enforce_strength: bool = False,
) -> dict[str, Any]:
    """Register a new user via Supabase (if configured) or local SQLite."""
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("A valid email address is required.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")

    if enforce_strength:
        strength = evaluate_password_strength(password)
        if not strength["is_valid"]:
            raise ValueError("Password is too weak. Please meet at least 4 security requirements.")

    client = _get_supabase_client()
    if client:
        return client.sign_up(email, password, full_name=full_name)

    # Local fallback
    salt = _generate_salt()
    pwd_hash = _hash_password(password, salt)
    display_name = (full_name or "").strip() or email.split("@")[0].capitalize()
    with _connect() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO users (username, email, full_name, password_hash, password_salt) VALUES (?, ?, ?, ?, ?)",
                (email, email, display_name, pwd_hash, salt),
            )
            user_id = cursor.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError("An account with this email already exists.")

    token = issue_token(user_id)
    return {
        "id": str(user_id),
        "email": email,
        "name": display_name,
        "token": token,
        "provider": "local",
    }


def login_user(email: str, password: str) -> dict[str, Any]:
    """Authenticate a user via Supabase (if configured) or local SQLite."""
    email = (email or "").strip().lower()
    if not email or not password:
        raise ValueError("Email and password are required.")

    client = _get_supabase_client()
    if client:
        return client.sign_in(email, password)

    # Local fallback
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (email, email),
        ).fetchone()

    if row is None or _hash_password(password, row["password_salt"]) != row["password_hash"]:
        raise ValueError("Invalid email or password.")

    token = issue_token(row["id"])
    row_dict = dict(row)
    display_name = row_dict.get("full_name") or (row["email"] or row["username"]).split("@")[0].capitalize()
    return {
        "id": str(row["id"]),
        "email": row["email"] or row["username"],
        "name": display_name,
        "token": token,
        "provider": "local",
    }


def update_user_name(user_info: dict[str, Any], new_name: str) -> bool:
    """Update user display name in Supabase or local SQLite."""
    new_name = (new_name or "").strip()
    if not new_name or not user_info:
        return False

    if user_info.get("provider") == "supabase":
        client = _get_supabase_client()
        if client and user_info.get("token"):
            return client.update_user(user_info["token"], new_name)

    uid = user_info.get("id")
    if uid:
        try:
            with _connect() as conn:
                conn.execute(
                    "UPDATE users SET full_name = ? WHERE id = ? OR username = ? OR email = ?",
                    (new_name, uid, str(uid), str(user_info.get("email", ""))),
                )
                conn.commit()
            return True
        except Exception as exc:
            logger.warning("Failed to update local user name: %s", exc)
    return False


def get_google_auth_url(redirect_uri: str = "") -> str:
    """Return Supabase Google OAuth authorization URL."""
    client = _get_supabase_client()
    if client:
        return client.get_oauth_url("google", redirect_to=redirect_uri)
    return ""


def logout_user(token: str) -> None:
    client = _get_supabase_client()
    if client:
        client.sign_out(token)
    logout_token(token)


# ---------------------------------------------------------------------------
# Backward Compatibility for Tests & Internal Tokens
# ---------------------------------------------------------------------------

def create_user(username: str, password: str) -> dict[str, Any]:
    username = (username or "").strip()
    if not username or not password:
        raise ValueError("Username and password are required.")
    salt = _generate_salt()
    password_hash = _hash_password(password, salt)
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, email, password_hash, password_salt) VALUES (?, ?, ?, ?)",
            (username, username if "@" in username else None, password_hash, salt),
        )
        user_id = cursor.lastrowid
        conn.commit()
    return {"id": user_id, "username": username}


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (username.strip(), username.strip()),
        ).fetchone()
    if row is None:
        return None
    if _hash_password(password, row["password_salt"]) != row["password_hash"]:
        return None
    return {"id": row["id"], "username": row["username"]}


def issue_token(user_id: int, expiry_seconds: int = 86400) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = str(int((time.time() + expiry_seconds) * 1000))
    with _connect() as conn:
        conn.execute(
            "INSERT INTO user_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user_id, token, expires_at),
        )
        conn.commit()
    return token


def validate_token(token: str) -> dict[str, Any] | None:
    if not token:
        return None

    # 1. Try Supabase token verification first if configured
    sb_client = _get_supabase_client()
    if sb_client:
        sb_user = sb_client.get_user(token)
        if sb_user:
            return sb_user

    # 2. Fallback to local SQLite token validation
    with _connect() as conn:
        row = conn.execute(
            "SELECT u.id, u.username, u.full_name, ut.token, ut.expires_at FROM user_tokens ut JOIN users u ON u.id = ut.user_id WHERE ut.token = ?",
            (token,),
        ).fetchone()
    if row is None:
        return None
    try:
        expires_at = int(row["expires_at"])
    except (TypeError, ValueError):
        return None
    if expires_at and expires_at < int(time.time() * 1000):
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["username"],
        "name": row["full_name"] or row["username"],
        "token": row["token"],
        "provider": "local",
    }


def logout_token(token: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM user_tokens WHERE token = ?", (token,))
        conn.commit()


def get_user_storage_dir(user_id: str | int) -> Path:
    user_dir = ROOT / "sessions" / f"user_{user_id}"
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


init_db()
