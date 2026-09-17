import time
import pytest
from core.auth import (
    evaluate_password_strength,
    signup_user,
    update_user_name,
    get_google_auth_url,
    create_user,
)


def test_password_strength_evaluation():
    # Empty
    empty = evaluate_password_strength("")
    assert empty["score"] == 0
    assert not empty["is_valid"]

    # Weak (only digits, length < 8)
    weak = evaluate_password_strength("12345")
    assert weak["score"] <= 2
    assert not weak["is_valid"]
    assert weak["color"] == "#ef4444"

    # Fair (length >= 8, upper, lower, digits, but no special)
    fair = evaluate_password_strength("Password12")
    assert fair["criteria"]["length"] is True
    assert fair["criteria"]["uppercase"] is True
    assert fair["criteria"]["lowercase"] is True
    assert fair["criteria"]["digit"] is True
    assert fair["criteria"]["special"] is False

    # Excellent (all 5 criteria)
    excellent = evaluate_password_strength("SuperSecret123!@")
    assert excellent["score"] == 5
    assert excellent["is_valid"] is True
    assert excellent["label"] == "Excellent"


def test_signup_user_stores_full_name():
    email = f"named_user_{int(time.time() * 1000)}@example.com"
    pwd = "SecurePass123!@"
    name = "Muhammad Bilal"

    user = signup_user(email, pwd, full_name=name)
    assert user["id"] is not None
    assert user["name"] == name
    assert user["email"] == email


def test_update_user_name():
    email = f"update_user_{int(time.time() * 1000)}@example.com"
    pwd = "SecurePass123!@"
    user = signup_user(email, pwd, full_name="Old Name")

    updated = update_user_name(user, "New Updated Name")
    assert updated is True


def test_google_auth_url():
    url = get_google_auth_url(redirect_uri="https://agentic-rag-chat.streamlit.app/")
    if url:
        assert "provider=google" in url
        assert "authorize" in url
