"""Tests for core.auth user management and token validation."""

import time
import pytest
from core.auth import create_user, authenticate_user, issue_token, validate_token, logout_token


def test_create_and_authenticate_user():
    username = f"test_user_{int(time.time() * 1000)}"
    password = "SuperSecretPassword123!"

    user = create_user(username, password)
    assert user["id"] is not None
    assert user["username"] == username

    # Authenticate with correct password
    authed = authenticate_user(username, password)
    assert authed is not None
    assert authed["id"] == user["id"]

    # Authenticate with wrong password
    assert authenticate_user(username, "WrongPassword") is None


def test_issue_token_validates_successfully():
    """Verify that issued token is valid immediately and not expired."""
    username = f"token_user_{int(time.time() * 1000)}"
    user = create_user(username, "pass123")

    # Issue token with standard 1-hour expiration
    token = issue_token(user["id"], expiry_seconds=3600)
    assert token is not None

    # Must validate successfully
    validated = validate_token(token)
    assert validated is not None
    assert validated["id"] == user["id"]
    assert validated["username"] == username

    # Logout token
    logout_token(token)
    assert validate_token(token) is None


def test_token_expiration_behavior():
    """Verify that an expired token fails validation."""
    username = f"exp_user_{int(time.time() * 1000)}"
    user = create_user(username, "pass123")

    # Issue an already-expired token (-10 seconds)
    token = issue_token(user["id"], expiry_seconds=-10)

    # Must be expired
    assert validate_token(token) is None


def test_signup_and_login_user():
    email = f"user_{int(time.time() * 1000)}@example.com"
    pwd = "password123"

    from core.auth import signup_user, login_user

    created = signup_user(email, pwd)
    assert created["email"] == email
    assert created["token"] != ""

    logged_in = login_user(email, pwd)
    assert logged_in["email"] == email
    assert logged_in["token"] != ""

    with pytest.raises(ValueError):
        login_user(email, "wrong_password")
