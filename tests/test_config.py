import os

import pytest


@pytest.fixture
def clean_env(monkeypatch):
    for key in [
        "GROQ_API_KEY",
        "GROQ_MODEL",
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "MAX_REQUESTS_PER_MINUTE",
        "APP_ENV",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_runtime_config_defaults_to_groq_model(clean_env):
    from core.config import get_runtime_config

    config = get_runtime_config()

    assert config["llm_provider"] == "groq"
    assert config["groq_model"] == "qwen/qwen3.8-27b"
    assert config["max_requests_per_minute"] == 8
    assert config["max_tokens"] == 700


def test_runtime_config_uses_environment_overrides(clean_env, monkeypatch):
    from core.config import get_runtime_config

    monkeypatch.setenv("GROQ_MODEL", "llama-3.1-8b-instant")
    monkeypatch.setenv("MAX_REQUESTS_PER_MINUTE", "5")
    monkeypatch.setenv("MAX_TOKENS", "500")
    monkeypatch.setenv("APP_ENV", "production")

    config = get_runtime_config()

    assert config["groq_model"] == "llama-3.1-8b-instant"
    assert config["max_requests_per_minute"] == 5
    assert config["max_tokens"] == 500
    assert config["app_env"] == "production"
