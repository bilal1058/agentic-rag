"""Unified Authentication Service with Supabase Cloud Auth and Local SQLite fallback."""

import base64
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

from core.auth_store import (
    AuthStore,
    SQLiteAuthAdapter,
    SupabaseAuthAdapter as SupabaseAuth,
    DB_PATH,
)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

# ---------------------------------------------------------------------------
# Storage Adapters (Delegated to deep core.auth_store module)
# ---------------------------------------------------------------------------

def _connect() -> sqlite3.Connection:
    return AuthStore.get_sqlite_adapter()._connect()


def init_db() -> None:
    AuthStore.get_sqlite_adapter().init_db()


def _hash_password(password: str, salt: str) -> str:
    return SQLiteAuthAdapter.hash_password(password, salt)


def _generate_salt() -> str:
    return SQLiteAuthAdapter.generate_salt()


def is_supabase_configured() -> bool:
    return AuthStore.is_supabase_active()


def _get_supabase_client() -> SupabaseAuth | None:
    return AuthStore.get_supabase_adapter()



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

    # 1. Fast local JWT claim extraction (0ms latency for Supabase JWTs)
    if token.count(".") == 2:
        try:
            parts = token.split(".")
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

    # 2. Try Supabase client verification endpoint if configured
    sb_client = _get_supabase_client()
    if sb_client:
        sb_user = sb_client.get_user(token)
        if sb_user:
            return sb_user

    # 3. Fallback to local SQLite token validation
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
