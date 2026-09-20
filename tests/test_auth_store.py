"""Unit tests for core/auth_store.py AuthStore and adapters."""

import pytest
from pathlib import Path
from core.auth_store import SQLiteAuthAdapter, AuthStore


@pytest.fixture
def sqlite_adapter(tmp_path: Path):
    db_file = tmp_path / "test_auth.db"
    return SQLiteAuthAdapter(db_path=db_file)


def test_sqlite_adapter_signup_and_signin(sqlite_adapter: SQLiteAuthAdapter):
    user = sqlite_adapter.sign_up("alice@example.com", "Secret123!", full_name="Alice Smith")
    assert user["email"] == "alice@example.com"
    assert user["name"] == "Alice Smith"
    assert user["provider"] == "local"
    assert "token" in user

    # Attempt duplicate signup
    with pytest.raises(ValueError, match="already exists"):
        sqlite_adapter.sign_up("alice@example.com", "AnotherPwd!")

    # Valid sign in
    logged_in = sqlite_adapter.sign_in("alice@example.com", "Secret123!")
    assert logged_in["email"] == "alice@example.com"
    assert logged_in["name"] == "Alice Smith"

    # Invalid sign in
    with pytest.raises(ValueError, match="Invalid email or password"):
        sqlite_adapter.sign_in("alice@example.com", "WrongPassword")


def test_sqlite_adapter_token_validation_and_signout(sqlite_adapter: SQLiteAuthAdapter):
    user = sqlite_adapter.sign_up("bob@example.com", "Secret456!", full_name="Bob Jones")
    token = user["token"]

    fetched = sqlite_adapter.get_user(token)
    assert fetched is not None
    assert fetched["email"] == "bob@example.com"

    # Sign out
    sqlite_adapter.sign_out(token)
    assert sqlite_adapter.get_user(token) is None


def test_sqlite_adapter_update_user(sqlite_adapter: SQLiteAuthAdapter):
    user = sqlite_adapter.sign_up("charlie@example.com", "Secret789!", full_name="Charlie")
    assert sqlite_adapter.update_user(user["id"], "Charlie Brown") is True

    fetched = sqlite_adapter.get_user(user["token"])
    assert fetched["name"] == "Charlie Brown"
