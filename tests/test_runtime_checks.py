import os

import pytest


@pytest.fixture
def clean_env(monkeypatch):
    for key in [
        "GROQ_API_KEY",
        "GROQ_MODEL",
        "APP_ENV",
        "MAX_REQUESTS_PER_MINUTE",
        "ENABLE_GUARDRAILS",
        "ENABLE_RAGAS",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_validate_runtime_environment_accepts_missing_env_in_dev(clean_env, monkeypatch):
    from core.config import validate_runtime_environment

    monkeypatch.setenv("APP_ENV", "development")
    warnings = validate_runtime_environment()

    assert warnings == []


def test_validate_runtime_environment_rejects_missing_key_in_production(clean_env, monkeypatch):
    from core.config import validate_runtime_environment

    monkeypatch.setenv("APP_ENV", "production")
    warnings = validate_runtime_environment()

    assert any("GROQ_API_KEY" in warning for warning in warnings)
